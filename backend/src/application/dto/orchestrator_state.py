from operator import add
from typing import Annotated, TypedDict

from src.application.dto.agent_response import AgentResponseDTO, ConsolidatedResponseDTO
from src.domain.entities.document import Chunk
from src.domain.entities.response import Citation


class OrchestratorState(TypedDict, total=False):
    # Input
    query_text: str
    user_role: str
    query_id: str

    # Sanitization
    sanitized_query: str
    spotlight_query: str
    pii_redacted: bool

    # Injection check
    injection_blocked: bool
    injection_attack_type: str

    # Routing
    routed_agents: list[str]
    routing_reasoning: str

    # Retrieval per agent
    retrieved_chunks: dict[str, list[Chunk]]

    # Agent responses (parallel reducer via add)
    agent_responses: Annotated[list[AgentResponseDTO], add]

    # Consolidation
    consolidated: ConsolidatedResponseDTO | None

    # Validation
    output_valid: bool
    output_violation: str

    # Final
    final_answer: str
    final_citations: list[Citation]
    confidence_passed: bool
    trace_id: str
    blocked_reason: str
