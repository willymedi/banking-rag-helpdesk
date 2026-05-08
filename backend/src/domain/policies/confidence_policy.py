from dataclasses import dataclass

from src.domain.value_objects.confidence import Confidence

CANONICAL_INSUFFICIENT = (
    "No encontré información suficiente en la base documental proporcionada "
    "para responder con precisión esta consulta."
)


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    threshold: float = 0.65

    def is_sufficient(self, confidence: Confidence, sufficient_context: bool) -> bool:
        return sufficient_context and confidence.passes(self.threshold)
