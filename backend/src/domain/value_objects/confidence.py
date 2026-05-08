from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Confidence:
    value: float
    reasoning: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence out of range [0,1]: {self.value}")

    def passes(self, threshold: float) -> bool:
        return self.value >= threshold
