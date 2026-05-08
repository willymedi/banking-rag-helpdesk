from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Citation:
    doc_id: str
    doc_title: str
    section_title: str
    chunk_id: str
    offset_start: int
    offset_end: int
    snippet: str

    def to_display(self) -> str:
        return f"{self.doc_title} :: {self.section_title} (#{self.chunk_id})"
