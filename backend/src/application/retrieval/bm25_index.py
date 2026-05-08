"""BM25 in-memory index over chunks. Rebuilt at startup (corpus chico).

Productivo: persist en Redis/Elasticsearch o usar SPLADE para sparse vectors.
"""

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.domain.entities.document import Chunk

WORD_RE = re.compile(r"[a-záéíóúñü0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


@dataclass
class BM25Index:
    chunks: list[Chunk]
    _bm25: BM25Okapi | None = None

    def __init__(self) -> None:
        self.chunks = []
        self._bm25 = None

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        if not self.chunks:
            self._bm25 = None
            return
        corpus = [_tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_role: str | None = None,
        filter_domain: str | None = None,
    ) -> list[tuple[Chunk, float]]:
        if not self._bm25 or not self.chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda kv: kv[1], reverse=True)
        out: list[tuple[Chunk, float]] = []
        for ch, sc in ranked:
            if filter_role and filter_role.lower() not in {r.lower() for r in ch.allowed_roles}:
                continue
            if filter_domain and ch.domain != filter_domain:
                continue
            out.append((ch, float(sc)))
            if len(out) >= top_k:
                break
        return out
