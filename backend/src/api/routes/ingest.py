from pathlib import Path

from fastapi import APIRouter, Depends

from src.api.container import Container
from src.api.dependencies import authed, container_dep
from src.application.use_cases.ingest_documents import IngestDocuments

router = APIRouter()


@router.post("/admin/ingest", dependencies=[Depends(authed)])
async def admin_ingest(c: Container = Depends(container_dep)) -> dict:
    uc = IngestDocuments(c.vector_store, c.embeddings, c.bm25_index)
    stats = await uc.run(Path(c.settings.docs_path), skip_if_populated=False)
    return {
        "docs_loaded": stats.docs_loaded,
        "chunks_indexed": stats.chunks_indexed,
        "skipped_files": stats.skipped_files,
    }
