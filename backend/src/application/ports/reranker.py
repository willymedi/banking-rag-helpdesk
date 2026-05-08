from typing import Protocol

from src.domain.entities.document import Chunk


class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]: ...
