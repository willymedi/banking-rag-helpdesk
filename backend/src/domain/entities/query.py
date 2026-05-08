from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class UserContext:
    role: str
    api_key_id: str = "anonymous"


@dataclass(frozen=True, slots=True)
class Query:
    text: str
    user: UserContext
    query_id: str = field(default_factory=lambda: uuid4().hex)
