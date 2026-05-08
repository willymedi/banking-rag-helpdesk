from pydantic import BaseModel, Field


class CitationDTO(BaseModel):
    """Pydantic mirror of domain Citation. LLM-facing for structured output."""

    chunk_id: str = Field(description="Identificador exacto del chunk usado, ej. doc01_s02_c01")
    section_title: str = Field(description="Título exacto de la sección citada")
    snippet: str = Field(max_length=800, description="Fragmento textual literal del chunk")


class AgentResponseDTO(BaseModel):
    """Schema que el LLM debe producir. Validado por structured output."""

    answer: str = Field(max_length=2000, description="Respuesta en español, basada SOLO en contexto")
    citations: list[CitationDTO] = Field(
        default_factory=list,
        description="Citas a chunks usados. Vacío si sufficient_context=False",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    sufficient_context: bool = Field(
        description="True si los chunks contienen información directa para responder"
    )
    reasoning: str = Field(
        max_length=500, description="Justificación corta de cómo se llegó a la respuesta"
    )


class ConsolidatedResponseDTO(BaseModel):
    answer: str = Field(max_length=4000)
    citations: list[CitationDTO] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    sufficient_context: bool
    participating_agents: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="", max_length=600)


class RouterDecisionDTO(BaseModel):
    intent: str = Field(description="Categoría: architecture | security | production | mixed | out_of_scope")
    selected_agents: list[str] = Field(
        description="Lista de agent names a invocar. Vacío si out_of_scope"
    )
    reasoning: str = Field(max_length=300)


class InjectionVerdictDTO(BaseModel):
    is_attack: bool
    attack_type: str = Field(default="", description="ej. instruction_override, role_hijacking, prompt_leak")
    confidence: float = Field(ge=0.0, le=1.0)
