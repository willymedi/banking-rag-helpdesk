from fastapi import APIRouter, Depends

from src.api.container import Container
from src.api.dependencies import authed, container_dep, get_user_role
from src.api.schemas.query_request import FeedbackRequest
from src.application.ports.feedback_repository import FeedbackEntry

router = APIRouter()


@router.post("/feedback", dependencies=[Depends(authed)])
async def feedback(
    body: FeedbackRequest,
    user_role: str = Depends(get_user_role),
    c: Container = Depends(container_dep),
) -> dict:
    entry = FeedbackEntry(
        query_id=body.query_id,
        trace_id=body.trace_id,
        user_role=user_role,
        rating=body.rating,
        comment=body.comment,
        final_answer_excerpt=body.final_answer_excerpt,
        participating_agents=tuple(body.participating_agents),
    )
    await c.record_feedback_uc.execute(entry)
    return {"ok": True}


@router.get("/feedback/recent", dependencies=[Depends(authed)])
async def feedback_recent(c: Container = Depends(container_dep)) -> list[dict]:
    items = await c.feedback_repo.list_recent(50)
    return [
        {
            "query_id": e.query_id,
            "trace_id": e.trace_id,
            "user_role": e.user_role,
            "rating": e.rating,
            "comment": e.comment,
            "final_answer_excerpt": e.final_answer_excerpt,
            "participating_agents": list(e.participating_agents),
        }
        for e in items
    ]
