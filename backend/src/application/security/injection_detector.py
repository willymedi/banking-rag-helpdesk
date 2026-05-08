"""Two-stage prompt injection detector.

Stage 1: cheap regex heuristics (sub-millisecond).
Stage 2: LLM classifier as second filter (multilingual, semantic).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.application.ports.llm_provider import LLMProvider

ZERO_WIDTH = ("​", "‌", "‍", "﻿")

HEURISTIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(r"(?i)\b(ignor[aeáé][a-z]*|forget|olvid[aá])\s+(all|todas?|previous|anteriores|todo)\b")),
    ("instruction_override", re.compile(r"(?i)disregard\s+(all|the)\s+(previous|above|instructions)")),
    ("role_hijacking", re.compile(r"(?i)\b(you\s+are|sos|eres|act\s+as|actua\s+como|pretendé\s+ser|pretendé\s+que)\b.*\b(dan|jailbreak|developer\s+mode|sin\s+restricciones|unfiltered)\b")),
    ("role_hijacking", re.compile(r"(?i)\b(developer\s+mode|do\s+anything\s+now|jailbreak|opposite\s+mode)\b")),
    ("system_tag", re.compile(r"(?i)<\s*/?\s*(system|assistant|user)\s*>")),
    ("system_tag", re.compile(r"(?i)\bsystem\s*:\s*you\s+are")),
    ("prompt_leak", re.compile(r"(?i)(repite|repeat|print|show|reveal|imprim[ií]|mostr[aá])\s+(me\s+)?(your|tu)\s+(system\s+)?(prompt|instructions|instrucciones)")),
    ("prompt_leak", re.compile(r"(?i)(palabra\s+por\s+palabra|word\s+for\s+word|verbatim).*(prompt|instruction|instrucci[oó]n)")),
    ("base64_smuggling", re.compile(r"(?i)\b(decod[a-z]*|decode|base[\s-]?64)\b.*[A-Za-z0-9+/=]{20,}")),
    ("base64_smuggling", re.compile(r"^[A-Za-z0-9+/=\s]{40,}$")),
    ("data_exfiltration", re.compile(r"(?i)\blist[a-z]*\s+(all|todos?)\s+(doc|documents|documentos|chunks?|files?)\b")),
    ("data_exfiltration", re.compile(r"(?i)dame\s+(todos\s+)?los\s+(documentos|chunks?|ids?)")),
)


@dataclass(frozen=True, slots=True)
class InjectionVerdict:
    is_attack: bool
    attack_type: str
    confidence: float
    detector: str  # "heuristic" | "llm" | "none"


def normalize_input(text: str) -> str:
    """Defensa contra token smuggling: NFKC + strip zero-width."""
    norm = unicodedata.normalize("NFKC", text)
    for zw in ZERO_WIDTH:
        norm = norm.replace(zw, "")
    return norm


class InjectionDetector:
    def __init__(self, llm: LLMProvider, llm_threshold: float = 0.6) -> None:
        self._llm = llm
        self._llm_threshold = llm_threshold

    async def check(self, text: str) -> InjectionVerdict:
        normalized = normalize_input(text)

        for attack_type, pattern in HEURISTIC_PATTERNS:
            if pattern.search(normalized):
                return InjectionVerdict(
                    is_attack=True,
                    attack_type=attack_type,
                    confidence=0.95,
                    detector="heuristic",
                )

        try:
            is_attack, attack_type, confidence = await self._llm.classify_attack(normalized)
        except Exception:
            # Fail-safe: si el classifier falla, dejamos pasar (heurística ya filtró obvios)
            return InjectionVerdict(False, "", 0.0, "none")

        if is_attack and confidence >= self._llm_threshold:
            return InjectionVerdict(
                is_attack=True,
                attack_type=attack_type or "unknown",
                confidence=confidence,
                detector="llm",
            )
        return InjectionVerdict(False, "", confidence, "none")
