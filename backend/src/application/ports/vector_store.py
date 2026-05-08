from typing import Protocol

from src.domain.entities.document import Chunk


class VectorStore(Protocol):
    async def upsert(self, chunks: list[Chunk]) -> None: ...

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_role: str | None = None,
        filter_domain: str | None = None,
    ) -> list[tuple[Chunk, float]]: ...

    async def count(self) -> int: ...

    async def list_all(self, filter_role: str | None = None) -> list[Chunk]: ...
