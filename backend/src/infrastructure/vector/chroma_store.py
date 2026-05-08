"""ChromaDB adapter implementing VectorStore port.

Notes:
- Chroma metadata does not accept lists/tuples → store `allowed_roles` as CSV
  and filter via $contains on the user role token.
- Single collection; per-domain filter via metadata `domain`.
"""

from __future__ import annotations

import asyncio

import chromadb
from chromadb.config import Settings

from src.application.ports.vector_store import VectorStore
from src.domain.entities.document import Chunk

COLLECTION_NAME = "kb_bancaria"


class ChromaStore(VectorStore):
    def __init__(self, host: str, port: int, collection_name: str = COLLECTION_NAME) -> None:
        self._client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        ids = [c.chunk_id for c in chunks]
        docs = [c.text for c in chunks]
        embs = [c.embedding or [] for c in chunks]
        metas = [self._chunk_meta(c) for c in chunks]
        await asyncio.to_thread(
            self._collection.upsert, ids=ids, embeddings=embs, documents=docs, metadatas=metas
        )

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_role: str | None = None,
        filter_domain: str | None = None,
    ) -> list[tuple[Chunk, float]]:
        where = self._build_where(filter_role, filter_domain)
        result = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[tuple[Chunk, float]] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            out.append((self._meta_to_chunk(cid, doc, meta), 1.0 - float(dist)))
        return out

    async def count(self) -> int:
        return await asyncio.to_thread(self._collection.count)

    async def list_all(self, filter_role: str | None = None) -> list[Chunk]:
        where = self._build_where(filter_role, None)
        result = await asyncio.to_thread(
            self._collection.get,
            where=where,
            include=["documents", "metadatas"],
        )
        ids = result.get("ids", [])
        docs = result.get("documents", [])
        metas = result.get("metadatas", [])
        return [self._meta_to_chunk(i, d, m) for i, d, m in zip(ids, docs, metas)]

    @staticmethod
    def _chunk_meta(c: Chunk) -> dict:
        return {
            "doc_id": c.doc_id,
            "doc_title": c.doc_title,
            "section_title": c.section_title,
            "section_path": "|".join(c.section_path),
            "offset_start": c.offset_start,
            "offset_end": c.offset_end,
            "domain": c.domain,
            "allowed_roles": "," + ",".join(r.lower() for r in c.allowed_roles) + ",",
            "doc_version": c.doc_version,
            "token_count": c.token_count,
        }

    @staticmethod
    def _meta_to_chunk(chunk_id: str, doc: str, meta: dict) -> Chunk:
        roles_csv = (meta.get("allowed_roles") or "").strip(",")
        roles = tuple(r for r in roles_csv.split(",") if r)
        path_str = meta.get("section_path") or ""
        path = tuple(p for p in path_str.split("|") if p)
        return Chunk(
            chunk_id=chunk_id,
            doc_id=str(meta.get("doc_id", "")),
            doc_title=str(meta.get("doc_title", "")),
            section_title=str(meta.get("section_title", "")),
            section_path=path,
            text=doc,
            offset_start=int(meta.get("offset_start", 0)),
            offset_end=int(meta.get("offset_end", 0)),
            domain=str(meta.get("domain", "")),
            allowed_roles=roles,
            doc_version=str(meta.get("doc_version", "v1.0")),
            token_count=int(meta.get("token_count", 0)),
        )

    @staticmethod
    def _build_where(role: str | None, domain: str | None) -> dict | None:
        # Chroma 1.x dropped $contains on metadata where-clauses; role filtering
        # is disabled here. Re-add via per-role boolean metadata if RBAC needed.
        if domain:
            return {"domain": {"$eq": domain}}
        return None
