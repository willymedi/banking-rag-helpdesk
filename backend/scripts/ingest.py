"""CLI entrypoint: `python -m scripts.ingest [--skip-if-populated]`."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.api.container import build_container_for_ingest
from src.application.use_cases.ingest_documents import IngestDocuments


async def _run(docs_dir: Path, skip_if_populated: bool) -> int:
    container = build_container_for_ingest()
    uc = IngestDocuments(container.vector_store, container.embeddings, container.bm25_index)
    stats = await uc.run(docs_dir, skip_if_populated=skip_if_populated)
    print(f"[ingest] docs={stats.docs_loaded} chunks={stats.chunks_indexed} skipped={stats.skipped_files}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest docs_kb into vector store + BM25")
    parser.add_argument("--docs-dir", default="/app/docs_kb")
    parser.add_argument("--skip-if-populated", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(Path(args.docs_dir), args.skip_if_populated)))


if __name__ == "__main__":
    main()
