"""BGE cross-encoder reranker (CPU). Opt-in via ENABLE_RERANKER env.

For corpus chico (~21 chunks) está deshabilitado por default. Ver ADR-002.
"""

from __future__ import annotations

import asyncio

from src.application.ports.reranker import Reranker
from src.domain.entities.document import Chunk

MODEL_NAME = "BAAI/bge-reranker-v2-m3"


class BGEReranker(Reranker):
    def __init__(self, model_name: str = MODEL_NAME) -> None:
        # Lazy import: avoid loading sentence-transformers if reranker disabled
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name, max_length=512, device="cpu")

    async def rerank(
        self,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        if not candidates:
            return []
        pairs = [(query, c.text) for c, _ in candidates]
        scores = await asyncio.to_thread(self._model.predict, pairs)
        scored = list(zip([c for c, _ in candidates], [float(s) for s in scores]))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]
