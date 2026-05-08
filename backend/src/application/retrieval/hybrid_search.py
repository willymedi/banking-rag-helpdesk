"""Hybrid retrieval: BM25 + vector + RRF fusion + optional rerank.

RRF: Reciprocal Rank Fusion (Cormack et al. 2009). Combina rankings sin
normalizar scores. score(c) = sum_i 1/(k + rank_i(c)). k=60 estándar.
"""

from src.application.ports.embeddings_provider import EmbeddingsProvider
from src.application.ports.reranker import Reranker
from src.application.ports.vector_store import VectorStore
from src.application.retrieval.bm25_index import BM25Index
from src.domain.entities.document import Chunk

RRF_K = 60


class HybridSearch:
    def __init__(
        self,
        vector_store: VectorStore,
        embeddings: EmbeddingsProvider,
        bm25_index: BM25Index,
        reranker: Reranker | None = None,
    ) -> None:
        self._vs = vector_store
        self._emb = embeddings
        self._bm25 = bm25_index
        self._reranker = reranker

    async def search(
        self,
        query: str,
        *,
        user_role: str,
        agent_domain: str | None = None,
        top_k: int = 5,
        candidate_pool: int = 20,
    ) -> list[tuple[Chunk, float]]:
        emb = await self._emb.embed_one(query)
        vector_hits = await self._vs.search(
            emb, top_k=candidate_pool, filter_role=user_role, filter_domain=agent_domain
        )
        bm25_hits = self._bm25.search(
            query, top_k=candidate_pool, filter_role=user_role, filter_domain=agent_domain
        )

        fused = self._rrf([vector_hits, bm25_hits])
        if not fused:
            return []

        if self._reranker is not None and len(fused) > top_k:
            return await self._reranker.rerank(query, fused[:candidate_pool], top_k=top_k)
        return fused[:top_k]

    @staticmethod
    def _rrf(rankings: list[list[tuple[Chunk, float]]]) -> list[tuple[Chunk, float]]:
        scores: dict[str, float] = {}
        chunks: dict[str, Chunk] = {}
        for ranking in rankings:
            for rank, (chunk, _score) in enumerate(ranking, start=1):
                key = chunk.chunk_id
                scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
                chunks[key] = chunk
        merged = [(chunks[k], scores[k]) for k in scores]
        merged.sort(key=lambda kv: kv[1], reverse=True)
        return merged
