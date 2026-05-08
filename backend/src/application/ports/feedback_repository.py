from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FeedbackEntry:
    query_id: str
    trace_id: str | None
    user_role: str
    rating: int  # +1 or -1
    comment: str | None
    final_answer_excerpt: str
    participating_agents: tuple[str, ...]


class FeedbackRepository(Protocol):
    async def save(self, entry: FeedbackEntry) -> None: ...

    async def list_recent(self, limit: int = 50) -> list[FeedbackEntry]: ...
