"""PII redactor.

Tries presidio_analyzer if available, with a regex fallback for common
LATAM identifiers. Replaces matches with `[PII_<TYPE>]` tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
    ("CEDULA_CO", re.compile(r"\b\d{8,11}\b")),  # Colombia / EC ID
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
    ("IP", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    found: tuple[str, ...]


class PIIRedactor:
    def __init__(self, use_presidio: bool = True) -> None:
        self._presidio = None
        if use_presidio:
            try:
                from presidio_analyzer import AnalyzerEngine

                self._presidio = AnalyzerEngine()
            except Exception:
                self._presidio = None

    def redact(self, text: str) -> RedactionResult:
        out = text
        found: list[str] = []
        if self._presidio is not None:
            try:
                results = self._presidio.analyze(text=text, language="es")
                # Sort desc by start to replace without offset shifts
                for r in sorted(results, key=lambda x: x.start, reverse=True):
                    token = f"[PII_{r.entity_type}]"
                    out = out[: r.start] + token + out[r.end :]
                    found.append(r.entity_type)
            except Exception:
                pass
        # Always run regex fallback (catches LATAM patterns presidio misses)
        for label, pat in PATTERNS:
            new_out, n = pat.subn(f"[PII_{label}]", out)
            if n > 0:
                found.extend([label] * n)
                out = new_out
        return RedactionResult(text=out, found=tuple(found))
