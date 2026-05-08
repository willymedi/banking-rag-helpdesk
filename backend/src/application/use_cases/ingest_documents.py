"""Ingest pipeline: read .txt → chunk → embed → upsert vector store + bm25."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from src.application.ports.embeddings_provider import EmbeddingsProvider
from src.application.ports.vector_store import VectorStore
from src.application.retrieval.bm25_index import BM25Index
from src.application.retrieval.chunker import ChunkerConfig, chunk_document
from src.domain.entities.document import Chunk

log = structlog.get_logger(__name__)

DEFAULT_ALLOWED_ROLES: tuple[str, ...] = (
    "dev",
    "architect",
    "auditor",
    "security",
    "compliance",
    "sre",
)


@dataclass(frozen=True, slots=True)
class DocSpec:
    file_name: str
    doc_id: str
    title: str
    domain: str
    allowed_roles: tuple[str, ...]


def load_specs_from_manifest(docs_dir: Path) -> tuple[DocSpec, ...]:
    manifest = docs_dir / "manifest.json"
    if not manifest.exists():
        log.warning("ingest.manifest_missing", path=str(manifest))
        return ()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    specs = []
    for file_name, meta in data.items():
        roles = meta.get("allowed_roles") or DEFAULT_ALLOWED_ROLES
        specs.append(
            DocSpec(
                file_name=file_name,
                doc_id=meta["doc_id"],
                title=meta["title"],
                domain=meta["domain"],
                allowed_roles=tuple(roles),
            )
        )
    return tuple(specs)


@dataclass
class IngestStats:
    docs_loaded: int = 0
    chunks_created: int = 0
    chunks_indexed: int = 0
    skipped_files: list[str] = field(default_factory=list)


class IngestDocuments:
    def __init__(
        self,
        vector_store: VectorStore,
        embeddings: EmbeddingsProvider,
        bm25_index: BM25Index,
        config: ChunkerConfig | None = None,
    ) -> None:
        self._vs = vector_store
        self._emb = embeddings
        self._bm25 = bm25_index
        self._cfg = config or ChunkerConfig()

    async def run(self, docs_dir: Path, *, skip_if_populated: bool = False) -> IngestStats:
        stats = IngestStats()

        if skip_if_populated and await self._vs.count() > 0:
            log.info("ingest.skipped_already_populated", count=await self._vs.count())
            await self._rebuild_bm25()
            return stats

        specs = load_specs_from_manifest(docs_dir)
        if not specs:
            log.error("ingest.no_specs_in_manifest", docs_dir=str(docs_dir))
            return stats

        all_chunks: list[Chunk] = []
        for spec in specs:
            path = docs_dir / spec.file_name
            if not path.exists():
                log.warning("ingest.doc_missing", path=str(path))
                stats.skipped_files.append(spec.file_name)
                continue
            text = path.read_text(encoding="utf-8")
            chunks = chunk_document(
                doc_id=spec.doc_id,
                doc_title=spec.title,
                text=text,
                domain=spec.domain,
                allowed_roles=spec.allowed_roles,
                config=self._cfg,
            )
            all_chunks.extend(chunks)
            stats.docs_loaded += 1
            stats.chunks_created += len(chunks)
            log.info(
                "ingest.doc_chunked",
                doc_id=spec.doc_id,
                chunks=len(chunks),
            )

        if not all_chunks:
            log.error("ingest.no_chunks_produced")
            return stats

        # Embed in batches of 100 (we have ~21, fits in one)
        texts = [c.text for c in all_chunks]
        vectors = await self._emb.embed_many(texts)
        embedded = [
            Chunk(**{**c.__dict__, "embedding": v}) if False else Chunk(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                doc_title=c.doc_title,
                section_title=c.section_title,
                section_path=c.section_path,
                text=c.text,
                offset_start=c.offset_start,
                offset_end=c.offset_end,
                domain=c.domain,
                allowed_roles=c.allowed_roles,
                doc_version=c.doc_version,
                token_count=c.token_count,
                embedding=v,
            )
            for c, v in zip(all_chunks, vectors)
        ]
        await self._vs.upsert(embedded)
        self._bm25.build(embedded)
        stats.chunks_indexed = len(embedded)
        log.info("ingest.done", **stats.__dict__)
        return stats

    async def _rebuild_bm25(self) -> None:
        chunks = await self._vs.list_all()
        self._bm25.build(chunks)
        log.info("ingest.bm25_rebuilt", count=len(chunks))


async def main_cli(docs_dir: Path, *, skip_if_populated: bool) -> int:
    """Helper for CLI use; wires settings + adapters."""
    from src.api.container import build_container_for_ingest

    container = build_container_for_ingest()
    uc = IngestDocuments(container.vector_store, container.embeddings, container.bm25_index)
    stats = await uc.run(docs_dir, skip_if_populated=skip_if_populated)
    return 0 if stats.chunks_indexed >= 0 else 1


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", default="/app/docs_kb")
    parser.add_argument("--skip-if-populated", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_cli(Path(args.docs_dir), skip_if_populated=args.skip_if_populated)))
