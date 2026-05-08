from typing import Protocol


class EmbeddingsProvider(Protocol):
    async def embed_one(self, text: str) -> list[float]: ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...
