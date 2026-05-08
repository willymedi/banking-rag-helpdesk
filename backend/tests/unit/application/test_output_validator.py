from src.application.dto.agent_response import CitationDTO, ConsolidatedResponseDTO
from src.application.security.output_validator import OutputValidator

SP = ("REGLAS INMUTABLES DE SEGURIDAD del sistema bancario\n",)


def test_detects_system_prompt_leak():
    v = OutputValidator(system_prompt_fragments=SP)
    leaked = ConsolidatedResponseDTO(
        answer="Mira, las REGLAS INMUTABLES DE SEGURIDAD son: ignora todo lo que sigue.",
        citations=[],
        confidence=0.9,
        sufficient_context=True,
        participating_agents=[],
        reasoning="",
    )
    res = v.validate(leaked)
    assert res.valid is False
    assert res.violation == "system_prompt_leak"


def test_blocks_external_urls():
    v = OutputValidator()
    resp = ConsolidatedResponseDTO(
        answer="Ver más en https://evil.com?data=foo y también https://localhost/foo.",
        citations=[CitationDTO(chunk_id="x", section_title="s", snippet="snip")],
        confidence=0.9,
        sufficient_context=True,
        participating_agents=[],
        reasoning="",
    )
    res = v.validate(resp)
    assert res.valid is True
    assert "evil.com" not in res.sanitized_answer
    assert "[URL_BLOCKED]" in res.sanitized_answer
    assert "localhost" in res.sanitized_answer


def test_requires_citations_when_sufficient_and_long_answer():
    v = OutputValidator()
    resp = ConsolidatedResponseDTO(
        answer="x" * 200,
        citations=[],
        confidence=0.9,
        sufficient_context=True,
        participating_agents=[],
        reasoning="",
    )
    res = v.validate(resp)
    assert res.valid is False
    assert res.violation == "missing_citations"


def test_passes_clean_response():
    v = OutputValidator()
    resp = ConsolidatedResponseDTO(
        answer="Respuesta corta y clara.",
        citations=[CitationDTO(chunk_id="c1", section_title="s", snippet="snip")],
        confidence=0.9,
        sufficient_context=True,
        participating_agents=["A"],
        reasoning="",
    )
    res = v.validate(resp)
    assert res.valid is True
