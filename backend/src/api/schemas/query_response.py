from pydantic import BaseModel


class CitationOut(BaseModel):
    doc_id: str
    doc_title: str
    section_title: str
    chunk_id: str
    snippet: str
    offset_start: int
    offset_end: int


class QueryResponse(BaseModel):
    query_id: str
    trace_id: str
    answer: str
    citations: list[CitationOut]
    participating_agents: list[str]
    confidence: float
    sufficient_context: bool
    blocked_reason: str
    routing_reasoning: str
