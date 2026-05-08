"""Context variable for propagating Langfuse trace_id across async boundaries."""

from contextvars import ContextVar

current_trace_id: ContextVar[str] = ContextVar("current_trace_id", default="")
