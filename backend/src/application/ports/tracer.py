from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol


class TraceSpan(Protocol):
    def update(self, **kwargs: Any) -> None: ...
    def event(self, name: str, **metadata: Any) -> None: ...


class Tracer(Protocol):
    def trace(
        self, name: str, query_id: str, **metadata: Any
    ) -> AbstractAsyncContextManager[TraceSpan]: ...

    def span(
        self, parent: TraceSpan, name: str, **metadata: Any
    ) -> AbstractAsyncContextManager[TraceSpan]: ...

    def get_trace_id(self, span: TraceSpan) -> str: ...
