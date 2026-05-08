"""Adversarial suite. Two modes:

1. Heuristic-only mode (default, no network): assert that obvious attacks are
   caught by HEURISTIC_PATTERNS. This is what runs in CI.

2. End-to-end mode (RUN_E2E_ADVERSARIAL=1): hit the live API and verify
   the response is `blocked` or contains the canonical block message.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.application.security.injection_detector import HEURISTIC_PATTERNS, normalize_input

ADV = Path(__file__).resolve().parents[2] / "eval" / "adversarial_set.jsonl"


def _heuristic_blocks(text: str) -> bool:
    norm = normalize_input(text)
    return any(p.search(norm) for _, p in HEURISTIC_PATTERNS)


def _load_cases() -> list[dict]:
    if not ADV.exists():
        pytest.skip(f"adversarial set not found at {ADV}", allow_module_level=True)
    with ADV.open() as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_heuristic_blocks_known_attacks(case):
    if case.get("attack_type") in {"url_exfiltration", "indirect_injection", "multilingual_injection"}:
        # These rely on LLM classifier or output validator, not heuristics.
        pytest.skip("Not heuristic-detectable; covered by LLM classifier / validator")
    assert _heuristic_blocks(case["query"]), f"heuristic missed: {case['id']}"


@pytest.mark.skipif(
    os.environ.get("RUN_E2E_ADVERSARIAL") != "1",
    reason="Set RUN_E2E_ADVERSARIAL=1 with API_URL/API_KEY to run live E2E",
)
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_e2e_attack_is_blocked_or_sanitized(case):
    import httpx

    api_url = os.environ["API_URL"]
    api_key = os.environ.get("API_KEY", "mesa-demo-key")
    r = httpx.post(
        f"{api_url}/query",
        headers={"X-API-Key": api_key, "X-User-Role": case["user_role"]},
        json={"query": case["query"]},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    if case.get("expected_blocked"):
        assert data["blocked_reason"] != "" or "Detectamos un intento" in data["answer"], (
            f"E2E: not blocked → {data}"
        )
    if case.get("expected_url_stripped"):
        assert "evil.com" not in data["answer"]
