"""Langfuse tracer adapter implementing Tracer port.

Falls back to a NullTracer if Langfuse keys are missing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog

from src.infrastructure.observability.trace_context import current_trace_id

log = structlog.get_logger(__name__)


class _NullSpan:
    def update(self, **kwargs: Any) -> None:
        pass

    def event(self, name: str, **metadata: Any) -> None:
        pass


class NullTracer:
    @asynccontextmanager
    async def trace(self, name: str, query_id: str, **metadata: Any):
        yield _NullSpan()

    @asynccontextmanager
    async def span(self, parent: Any, name: str, **metadata: Any):
        yield _NullSpan()

    def get_trace_id(self, span: Any) -> str:  # noqa: ARG002
        return ""

    def get_callback_handler(self, trace_id: str) -> Any:  # noqa: ARG002
        return None


class LangfuseTracer:
    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host
        try:
            from langfuse import Langfuse

            self._client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
            self._enabled = True
        except Exception as exc:
            log.warning("langfuse.init_failed", err=str(exc))
            self._client = None
            self._enabled = False

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        query_id: str,
        input: Any = None,
        **metadata: Any,
    ):
        if not self._enabled:
            yield _NullSpan()
            return
        token = current_trace_id.set(query_id)
        try:
            tr = self._client.trace(
                name=name, id=query_id, input=input, metadata=metadata
            )
            yield tr
        finally:
            current_trace_id.reset(token)
            try:
                self._client.flush()
            except Exception:
                pass

    @asynccontextmanager
    async def span(self, parent: Any, name: str, input: Any = None, **metadata: Any):
        if not self._enabled:
            yield _NullSpan()
            return
        sp = parent.span(name=name, input=input, metadata=metadata)
        try:
            yield sp
        finally:
            try:
                sp.end()
            except Exception:
                pass

    def get_trace_id(self, span: Any) -> str:
        try:
            return getattr(span, "id", "") or ""
        except Exception:
            return ""

    def get_callback_handler(self, trace_id: str) -> Any:  # noqa: ARG002
        return None
