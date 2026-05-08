from fastapi import APIRouter, Depends

from src.api.container import Container
from src.api.dependencies import container_dep

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(c: Container = Depends(container_dep)) -> dict:
    try:
        n = await c.vector_store.count()
        return {"status": "ready", "vector_chunks": n, "agents": c.orchestrator.agent_names}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}
