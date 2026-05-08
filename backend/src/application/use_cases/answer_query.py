"""Use case: answer a single user query end-to-end via LangGraph orchestrator."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from datetime import timezone
from typing import Any, AsyncIterator

import structlog

from src.application.dto.orchestrator_state import OrchestratorState
from src.application.ports.tracer import Tracer
from src.application.security.pii_redactor import PIIRedactor
from src.domain.entities.query import Query
from src.domain.entities.response import Citation

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StreamEvent:
    kind: str  # "step" | "result"
    node: str
    payload: dict


@dataclass(frozen=True, slots=True)
class AnswerResult:
    query_id: str
    trace_id: str
    answer: str
    citations: tuple[Citation, ...]
    participating_agents: tuple[str, ...]
    confidence: float
    sufficient_context: bool
    blocked_reason: str
    routing_intent: str
    routing_reasoning: str


class AnswerQuery:
    def __init__(self, graph: Any, tracer: Tracer, pii_redactor: PIIRedactor | None = None) -> None:
        self._graph = graph
        self._tracer = tracer
        self._pii_redactor = pii_redactor

    def _safe_query(self, text: str) -> str:
        if self._pii_redactor is None:
            return "[query_redacted]"
        return self._pii_redactor.redact(text).text

    async def execute(self, query: Query) -> AnswerResult:
        async with self._tracer.trace(
            name="answer_query",
            query_id=query.query_id,
            input={"query": self._safe_query(query.text), "user_role": query.user.role},
            user_role=query.user.role,
        ) as span:
            initial_state: OrchestratorState = {
                "query_text": query.text,
                "user_role": query.user.role,
                "query_id": query.query_id,
                "agent_responses": [],
            }
            final_state: OrchestratorState = await self._graph.ainvoke(initial_state)
            trace_id = self._tracer.get_trace_id(span)
            span.update(
                output=self._build_output(final_state),
            )

        return self._build_result(query, final_state, trace_id)

    async def execute_stream(self, query: Query) -> AsyncIterator[StreamEvent]:
        """Yield per-node progress events + final result. Wraps in tracer with per-node spans."""
        async with self._tracer.trace(
            name="answer_query_stream",
            query_id=query.query_id,
            input={"query": self._safe_query(query.text), "user_role": query.user.role},
            user_role=query.user.role,
        ) as span:
            initial_state: OrchestratorState = {
                "query_text": query.text,
                "user_role": query.user.role,
                "query_id": query.query_id,
                "agent_responses": [],
            }
            accumulated: dict = dict(initial_state)
            node_start = datetime.datetime.now(timezone.utc)
            async for chunk in self._graph.astream(initial_state, stream_mode="updates"):
                node_end = datetime.datetime.now(timezone.utc)
                for node_name, partial in chunk.items():
                    if isinstance(partial, dict):
                        accumulated.update(partial)
                    self._record_node_span(span, node_name, partial, node_start, node_end)
                    yield StreamEvent(kind="step", node=node_name, payload={"node": node_name})
                node_start = node_end
            final_state: OrchestratorState = accumulated  # type: ignore[assignment]
            trace_id = self._tracer.get_trace_id(span)
            span.update(
                output=self._build_output(final_state),
            )
        result = self._build_result(query, final_state, trace_id=trace_id)
        yield StreamEvent(
            kind="result",
            node="final",
            payload={
                "query_id": result.query_id,
                "trace_id": result.trace_id,
                "answer": result.answer,
                "citations": [
                    {
                        "doc_id": c.doc_id,
                        "doc_title": c.doc_title,
                        "section_title": c.section_title,
                        "chunk_id": c.chunk_id,
                        "snippet": c.snippet,
                        "offset_start": c.offset_start,
                        "offset_end": c.offset_end,
                    }
                    for c in result.citations
                ],
                "participating_agents": list(result.participating_agents),
                "confidence": result.confidence,
                "sufficient_context": result.sufficient_context,
                "blocked_reason": result.blocked_reason,
                "routing_reasoning": result.routing_reasoning,
            },
        )

    @staticmethod
    def _build_output(final_state: OrchestratorState) -> dict:
        return {
            "answer": final_state.get("final_answer", ""),
            "blocked_reason": final_state.get("blocked_reason", ""),
            "confidence_passed": bool(final_state.get("confidence_passed")),
            "routed_agents": list(final_state.get("routed_agents", []) or []),
            "citations": [
                {
                    "doc_id": c.doc_id,
                    "doc_title": c.doc_title,
                    "section_title": c.section_title,
                    "chunk_id": c.chunk_id,
                    "snippet": c.snippet,
                }
                for c in (final_state.get("final_citations") or [])
            ],
        }

    @staticmethod
    def _record_node_span(
        parent_span: Any,
        node_name: str,
        partial: Any,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> None:
        try:
            child = parent_span.span(
                name=node_name,
                output=partial if isinstance(partial, dict) else {},
                start_time=start_time,
                end_time=end_time,
            )
            child.end(end_time=end_time)
        except Exception:
            pass

    def _build_result(
        self, query: Query, final_state: OrchestratorState, trace_id: str
    ) -> AnswerResult:
        consolidated = final_state.get("consolidated")
        return AnswerResult(
            query_id=query.query_id,
            trace_id=trace_id,
            answer=final_state.get("final_answer", ""),
            citations=tuple(final_state.get("final_citations", [])),
            participating_agents=tuple(final_state.get("routed_agents", [])),
            confidence=consolidated.confidence if consolidated else 0.0,
            sufficient_context=bool(final_state.get("confidence_passed")),
            blocked_reason=final_state.get("blocked_reason", ""),
            routing_intent=consolidated.reasoning[:80] if consolidated else "",
            routing_reasoning=final_state.get("routing_reasoning", ""),
        )
