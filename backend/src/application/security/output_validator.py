"""Post-LLM output validation.

Three checks:
1. Leak detection: rolling 30-char hash overlap with system prompt fragments.
2. URL whitelist: strip URLs not in allowlist (anti exfiltration via markdown links).
3. Claim ↔ citation match: at least one citation must be present when sufficient_context=True
   and the answer makes substantive claims (heuristic: > 80 chars).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.application.dto.agent_response import ConsolidatedResponseDTO

URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
ALLOWED_URL_HOSTS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "mesa.local",
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    violation: str
    sanitized_answer: str


class OutputValidator:
    def __init__(self, system_prompt_fragments: tuple[str, ...] = ()) -> None:
        # Fragments to detect leaks. Provided at wiring time.
        self._fragments = tuple(f.strip() for f in system_prompt_fragments if len(f.strip()) >= 30)

    def validate(self, response: ConsolidatedResponseDTO) -> ValidationResult:
        answer = response.answer

        # 1. Leak detection
        for frag in self._fragments:
            for i in range(0, len(frag) - 30):
                window = frag[i : i + 30]
                if window in answer:
                    return ValidationResult(False, "system_prompt_leak", answer)

        # 2. URL whitelist
        sanitized = answer
        for url in URL_RE.findall(answer):
            if not any(host in url for host in ALLOWED_URL_HOSTS):
                sanitized = sanitized.replace(url, "[URL_BLOCKED]")
        if sanitized != answer:
            answer = sanitized

        # 3. Claim ↔ citation
        if response.sufficient_context and len(answer) > 80 and not response.citations:
            return ValidationResult(False, "missing_citations", answer)

        return ValidationResult(True, "", answer)
