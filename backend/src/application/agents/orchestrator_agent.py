"""Orchestrator: router (LLM) + consolidator (LLM).

Router classifies intent → selects agents.
Consolidator merges parallel agent responses into a single answer.
"""

from __future__ import annotations

from src.application.agents.base import BaseAgent
from src.application.dto.agent_response import (
    AgentResponseDTO,
    ConsolidatedResponseDTO,
    RouterDecisionDTO,
)
from src.application.ports.llm_provider import LLMProvider
from src.application.security.spotlight import (
    SPOTLIGHT_SYSTEM_RULES,
    wrap_context,
    wrap_user,
)


class OrchestratorAgent:
    def __init__(self, llm: LLMProvider, agents: list[BaseAgent]) -> None:
        self._llm = llm
        self._agents = {a.name: a for a in agents}

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())

    def get_agent(self, name: str) -> BaseAgent:
        return self._agents[name]

    async def route(self, query: str) -> RouterDecisionDTO:
        catalog = "\n".join(
            f"- {a.name} (dominio: {a.domain}): {a.persona[:400]}"
            for a in self._agents.values()
        )
        system = (
            f"{SPOTLIGHT_SYSTEM_RULES}\n\n"
            "Eres un router. Dada una consulta, determina qué agentes especializados "
            "deben responder. Reglas:\n"
            "- intent ∈ {architecture, security, production, mixed, out_of_scope}\n"
            "- selected_agents debe ser subconjunto de los disponibles\n"
            "- mixed → selecciona TODOS los que apliquen (puede ser 2 o 3)\n"
            "- out_of_scope → selected_agents=[] y reasoning explica por qué\n"
            "- Si la consulta menciona 'API interna', 'microservicio', 'exponer/publicar',\n"
            "  'controles técnicos', 'estándares', 'diseño' → SIEMPRE incluir ArchitectureAgent\n"
            "- Si menciona 'datos sensibles', 'PII', 'seguridad', 'autenticación', 'autorización',\n"
            "  'logs', 'cumplimiento' → incluir SecurityAgent\n"
            "- Si menciona 'producción', 'paso a productivo', 'despliegue', 'release',\n"
            "  'evidencias', 'checklist', 'rollback' → incluir ProductionAgent\n"
            "\n"
            "Ejemplos:\n"
            "- 'Necesito publicar una API interna con datos sensibles, ¿qué controles "
            "técnicos, de seguridad y de paso a producción aplican?' →\n"
            "  intent=mixed, selected=[ArchitectureAgent, SecurityAgent, ProductionAgent]\n"
            "- 'Qué debe cumplir un microservicio antes de exponerse' →\n"
            "  intent=architecture, selected=[ArchitectureAgent]\n"
            "- 'Cuál es la capital de Francia' → intent=out_of_scope, selected=[]\n"
            "\n"
            "Respondé SOLO JSON."
        )
        user = (
            f"Agentes disponibles:\n{catalog}\n\n"
            f"Consulta:\n{wrap_user(query)}\n\n"
            "Devolvé JSON con campos: intent, selected_agents, reasoning."
        )
        return await self._llm.complete_structured(
            system_prompt=system,
            user_prompt=user,
            response_schema=RouterDecisionDTO,
            model="gpt-4o-mini",
            temperature=0.0,
        )

    async def consolidate(
        self, query: str, agent_responses: list[AgentResponseDTO]
    ) -> ConsolidatedResponseDTO:
        if not agent_responses:
            return ConsolidatedResponseDTO(
                answer="",
                citations=[],
                confidence=0.0,
                sufficient_context=False,
                participating_agents=[],
                reasoning="No hubo respuestas de agentes.",
            )

        usable = [r for r in agent_responses if r.sufficient_context and r.answer.strip()]
        if not usable:
            return ConsolidatedResponseDTO(
                answer="",
                citations=[],
                confidence=max((r.confidence for r in agent_responses), default=0.0),
                sufficient_context=False,
                participating_agents=[],
                reasoning="Ningún agente encontró contexto suficiente.",
            )

        # Build LLM input
        partials = "\n\n".join(
            f"### Agente {i+1}\nReasoning: {r.reasoning}\nConfidence: {r.confidence}\n"
            f"Citations: {[c.model_dump() for c in r.citations]}\n"
            f"Respuesta:\n{r.answer}"
            for i, r in enumerate(usable)
        )

        system = (
            f"{SPOTLIGHT_SYSTEM_RULES}\n\n"
            "Eres el consolidador. Tomas respuestas parciales de agentes "
            "especializados y produces una respuesta unificada en español, "
            "técnica, clara y CITANDO. Reglas:\n"
            "- No inventes nada que no esté en las respuestas parciales.\n"
            "- Conserva todas las citas relevantes (chunk_id + section_title).\n"
            "- confidence = promedio de las confidences de las respuestas usadas, "
            "ajustado por consistencia (si se contradicen, reduce).\n"
            "- sufficient_context=true sólo si al menos una respuesta parcial lo era.\n"
            "- Responde SOLO JSON."
        )
        user = (
            f"Consulta original:\n{wrap_user(query)}\n\n"
            f"Respuestas parciales:\n{wrap_context(partials)}\n\n"
            "Devolvé JSON ConsolidatedResponseDTO."
        )

        consolidated = await self._llm.complete_structured(
            system_prompt=system,
            user_prompt=user,
            response_schema=ConsolidatedResponseDTO,
            model="gpt-4o-mini",
            temperature=0.2,
        )
        # Force participating_agents from input (don't trust LLM here)
        # We can't know agent names from DTO; caller fills this in.
        return consolidated
