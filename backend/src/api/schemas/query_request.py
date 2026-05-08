from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)


class FeedbackRequest(BaseModel):
    query_id: str
    trace_id: str | None = None
    rating: int = Field(ge=-1, le=1)  # -1 down, +1 up
    comment: str | None = Field(default=None, max_length=1000)
    final_answer_excerpt: str = Field(default="", max_length=400)
    participating_agents: list[str] = Field(default_factory=list)
