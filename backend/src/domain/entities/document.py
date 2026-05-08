from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Document:
    doc_id: str
    title: str
    text: str
    domain: str
    allowed_roles: tuple[str, ...]
    version: str = "v1.0"


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    section_title: str
    section_path: tuple[str, ...]
    text: str
    offset_start: int
    offset_end: int
    domain: str
    allowed_roles: tuple[str, ...]
    doc_version: str
    token_count: int
    embedding: list[float] | None = field(default=None, repr=False)
