from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("document_id cannot be empty")

    def __str__(self) -> str:
        return self.value
