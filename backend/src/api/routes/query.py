from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.api.container import Container
from src.api.dependencies import authed, container_dep, get_user_role
from src.api.schemas.query_request import QueryRequest
from src.api.schemas.query_response import CitationOut, QueryResponse
from src.domain.entities.query import Query, UserContext

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(authed)])
async def query_sync(
    body: QueryRequest,
    user_role: str = Depends(get_user_role),
    c: Container = Depends(container_dep),
) -> QueryResponse:
    q = Query(text=body.query, user=UserContext(role=user_role))
    log.info("query.received", query_id=q.query_id, role=user_role)
    result = await c.answer_query_uc.execute(q)
    return QueryResponse(
        query_id=result.query_id,
        trace_id=result.trace_id,
        answer=result.answer,
        citations=[
            CitationOut(
                doc_id=cit.doc_id,
                doc_title=cit.doc_title,
                section_title=cit.section_title,
                chunk_id=cit.chunk_id,
                snippet=cit.snippet,
                offset_start=cit.offset_start,
                offset_end=cit.offset_end,
            )
            for cit in result.citations
        ],
        participating_agents=list(result.participating_agents),
        confidence=result.confidence,
        sufficient_context=result.sufficient_context,
        blocked_reason=result.blocked_reason,
        routing_reasoning=result.routing_reasoning,
    )


NODE_LABELS: dict[str, str] = {
    "sanitize": "Verificando consulta y redactando datos sensibles",
    "injection_check": "Detectando intentos de manipulación",
    "router": "Seleccionando agentes especializados",
    "agent__ArchitectureAgent": "Consultando ArchitectureAgent",
    "agent__SecurityAgent": "Consultando SecurityAgent",
    "agent__ProductionAgent": "Consultando ProductionAgent",
    "consolidator": "Consolidando respuesta",
    "output_validator": "Validando salida",
    "finalize": "Finalizando",
    "blocked": "Consulta bloqueada",
    "insufficient": "Información insuficiente",
}


@router.post("/query/stream", dependencies=[Depends(authed)])
async def query_stream(
    request: Request,
    body: QueryRequest,
    user_role: str = Depends(get_user_role),
    c: Container = Depends(container_dep),
):
    """SSE: per-node progress events + final result."""

    q = Query(text=body.query, user=UserContext(role=user_role))

    async def gen():
        yield {"event": "start", "data": json.dumps({"query_id": q.query_id})}
        try:
            async for ev in c.answer_query_uc.execute_stream(q):
                if ev.kind == "step":
                    label = NODE_LABELS.get(ev.node, ev.node)
                    yield {
                        "event": "step",
                        "data": json.dumps({"node": ev.node, "label": label}),
                    }
                elif ev.kind == "result":
                    yield {"event": "result", "data": json.dumps(ev.payload)}
        except Exception as exc:  # noqa: BLE001
            log.exception("query_stream.failed", err=str(exc))
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(gen())
