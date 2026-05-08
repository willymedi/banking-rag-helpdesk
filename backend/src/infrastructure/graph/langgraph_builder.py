"""LangGraph StateGraph orchestrator.

Flow:
  sanitize → injection_check → router → fan_out (parallel agents)
   → consolidator → output_validator → confidence_gate → END

Fan-out is realized by adding a conditional edge to per-agent nodes.
Each agent node appends to `agent_responses` (reducer = list concat).
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from src.application.agents.orchestrator_agent import OrchestratorAgent
from src.application.dto.agent_response import (
    AgentResponseDTO,
    ConsolidatedResponseDTO,
    CitationDTO,
)
from src.application.dto.orchestrator_state import OrchestratorState
from src.application.security.injection_detector import InjectionDetector
from src.application.security.output_validator import OutputValidator
from src.application.security.pii_redactor import PIIRedactor
from src.application.security.spotlight import strip_delimiters_from_user_input
from src.domain.entities.response import Citation
from src.domain.policies.confidence_policy import CANONICAL_INSUFFICIENT, ConfidencePolicy

log = structlog.get_logger(__name__)

CANONICAL_BLOCKED = (
    "Detectamos un intento de manipulación de instrucciones del sistema. "
    "Tu consulta no será procesada. Por favor reformulá tu pregunta enfocándote "
    "en consultas técnicas legítimas sobre arquitectura, seguridad o paso a producción."
)


class LangGraphBuilder:
    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        injection_detector: InjectionDetector,
        pii_redactor: PIIRedactor,
        output_validator: OutputValidator,
        confidence_policy: ConfidencePolicy,
    ) -> None:
        self._orch = orchestrator
        self._injection = injection_detector
        self._pii = pii_redactor
        self._validator = output_validator
        self._confidence = confidence_policy

    def build(self) -> Any:
        graph = StateGraph(OrchestratorState)

        graph.add_node("sanitize", self._sanitize)
        graph.add_node("injection_check", self._injection_check)
        graph.add_node("router", self._router)

        for agent_name in self._orch.agent_names:
            graph.add_node(f"agent__{agent_name}", self._make_agent_node(agent_name))

        graph.add_node("consolidator", self._consolidator)
        graph.add_node("output_validator", self._output_validator)
        graph.add_node("blocked", self._blocked_terminal)
        graph.add_node("insufficient", self._insufficient_terminal)
        graph.add_node("finalize", self._finalize)

        graph.set_entry_point("sanitize")
        graph.add_edge("sanitize", "injection_check")
        graph.add_conditional_edges(
            "injection_check",
            lambda s: "blocked" if s.get("injection_blocked") else "router",
            {"blocked": "blocked", "router": "router"},
        )
        graph.add_conditional_edges("router", self._fan_out, self._fan_out_targets())

        for agent_name in self._orch.agent_names:
            graph.add_edge(f"agent__{agent_name}", "consolidator")

        graph.add_edge("consolidator", "output_validator")
        graph.add_conditional_edges(
            "output_validator",
            lambda s: "blocked" if not s.get("output_valid") else "finalize",
            {"blocked": "blocked", "finalize": "finalize"},
        )
        graph.add_conditional_edges(
            "finalize",
            lambda s: "insufficient" if not s.get("confidence_passed") else "end",
            {"insufficient": "insufficient", "end": END},
        )
        graph.add_edge("blocked", END)
        graph.add_edge("insufficient", END)

        return graph.compile()

    # --- Nodes ---

    async def _sanitize(self, state: OrchestratorState) -> OrchestratorState:
        raw = state.get("query_text", "")
        cleaned = strip_delimiters_from_user_input(raw)
        red = self._pii.redact(cleaned)
        log.info("graph.sanitize", query_id=state.get("query_id"), pii_found=red.found)
        return {
            "sanitized_query": red.text,
            "pii_redacted": bool(red.found),
        }

    async def _injection_check(self, state: OrchestratorState) -> OrchestratorState:
        verdict = await self._injection.check(state["sanitized_query"])
        log.info(
            "graph.injection_check",
            query_id=state.get("query_id"),
            is_attack=verdict.is_attack,
            attack_type=verdict.attack_type,
            detector=verdict.detector,
        )
        if verdict.is_attack:
            return {
                "injection_blocked": True,
                "injection_attack_type": verdict.attack_type,
                "blocked_reason": f"injection:{verdict.attack_type}",
            }
        return {"injection_blocked": False}

    async def _router(self, state: OrchestratorState) -> OrchestratorState:
        decision = await self._orch.route(state["sanitized_query"])
        valid = [n for n in decision.selected_agents if n in self._orch.agent_names]
        log.info(
            "graph.router",
            query_id=state.get("query_id"),
            intent=decision.intent,
            selected=valid,
        )
        return {
            "routed_agents": valid,
            "routing_reasoning": decision.reasoning,
        }

    def _make_agent_node(self, agent_name: str):
        async def _node(state: OrchestratorState) -> OrchestratorState:
            if agent_name not in (state.get("routed_agents") or []):
                return {}
            agent = self._orch.get_agent(agent_name)
            chunks = await agent.retrieve(
                state["sanitized_query"], user_role=state.get("user_role", "auditor")
            )
            response = await agent.answer(state["sanitized_query"], chunks)
            log.info(
                "graph.agent",
                query_id=state.get("query_id"),
                agent=agent_name,
                chunks=len(chunks),
                confidence=response.confidence,
                sufficient=response.sufficient_context,
            )
            return {"agent_responses": [response]}

        return _node

    async def _consolidator(self, state: OrchestratorState) -> OrchestratorState:
        responses = state.get("agent_responses", [])
        routed = state.get("routed_agents", [])
        # Fast path: single agent → reuse its response, skip LLM consolidation.
        if len(responses) == 1 and len(routed) == 1:
            r = responses[0]
            consolidated = ConsolidatedResponseDTO(
                answer=r.answer,
                citations=r.citations,
                confidence=r.confidence,
                sufficient_context=r.sufficient_context,
                participating_agents=list(routed),
                reasoning=r.reasoning,
            )
            return {"consolidated": consolidated}

        consolidated = await self._orch.consolidate(state["sanitized_query"], responses)
        # We override participating_agents from routed list (don't trust LLM)
        consolidated_with_agents = ConsolidatedResponseDTO(
            answer=consolidated.answer,
            citations=consolidated.citations,
            confidence=consolidated.confidence,
            sufficient_context=consolidated.sufficient_context,
            participating_agents=list(routed),
            reasoning=consolidated.reasoning,
        )
        return {"consolidated": consolidated_with_agents}

    async def _output_validator(self, state: OrchestratorState) -> OrchestratorState:
        consolidated = state.get("consolidated")
        if consolidated is None:
            return {"output_valid": False, "output_violation": "no_consolidated"}
        result = self._validator.validate(consolidated)
        if not result.valid:
            log.warning(
                "graph.output_validation_failed",
                query_id=state.get("query_id"),
                violation=result.violation,
            )
            return {"output_valid": False, "output_violation": result.violation, "blocked_reason": f"output:{result.violation}"}
        # Update consolidated answer with sanitized version (URLs stripped)
        if result.sanitized_answer != consolidated.answer:
            consolidated = ConsolidatedResponseDTO(
                **{**consolidated.model_dump(), "answer": result.sanitized_answer}
            )
        return {"output_valid": True, "consolidated": consolidated}

    async def _finalize(self, state: OrchestratorState) -> OrchestratorState:
        consolidated = state["consolidated"]
        from src.domain.value_objects.confidence import Confidence

        confidence = Confidence(value=consolidated.confidence)
        passed = self._confidence.is_sufficient(confidence, consolidated.sufficient_context)
        citations = [
            Citation(
                doc_id=_lookup_doc_id(c.chunk_id),
                doc_title=_lookup_doc_title(c.chunk_id),
                section_title=c.section_title,
                chunk_id=c.chunk_id,
                offset_start=0,
                offset_end=0,
                snippet=c.snippet,
            )
            for c in consolidated.citations
        ]
        return {
            "confidence_passed": passed,
            "final_answer": consolidated.answer if passed else CANONICAL_INSUFFICIENT,
            "final_citations": citations if passed else [],
        }

    async def _blocked_terminal(self, state: OrchestratorState) -> OrchestratorState:
        return {
            "final_answer": CANONICAL_BLOCKED,
            "final_citations": [],
            "confidence_passed": False,
        }

    async def _insufficient_terminal(self, state: OrchestratorState) -> OrchestratorState:
        return {
            "final_answer": CANONICAL_INSUFFICIENT,
            "final_citations": [],
            "confidence_passed": False,
        }

    # --- Conditional helpers ---

    def _fan_out(self, state: OrchestratorState) -> list[str]:
        agents = state.get("routed_agents") or []
        if not agents:
            # No agents → go straight to consolidator (will return insufficient)
            return ["consolidator"]
        return [f"agent__{a}" for a in agents]

    def _fan_out_targets(self) -> dict[str, str]:
        targets = {f"agent__{a}": f"agent__{a}" for a in self._orch.agent_names}
        targets["consolidator"] = "consolidator"
        return targets


def _lookup_doc_id(chunk_id: str) -> str:
    # chunk_id format: doc_<name>_sNN_cNN_<hash>
    parts = chunk_id.split("_")
    if len(parts) >= 2 and parts[0] == "doc":
        return f"doc_{parts[1]}"
    return chunk_id.split("_")[0] if "_" in chunk_id else "unknown"


def _lookup_doc_title(chunk_id: str) -> str:
    doc_id = _lookup_doc_id(chunk_id)
    titles = {
        "doc_arquitectura": "Estándares de Arquitectura y Microservicios",
        "doc_seguridad": "Lineamientos de Seguridad para APIs",
        "doc_produccion": "Checklist de Paso a Producción",
    }
    return titles.get(doc_id, "Documento")
