from src.application.retrieval.chunker import ChunkerConfig, chunk_document

DOC = """## Sección 1
Este es el primer párrafo de la sección uno. Tiene algo de contenido sobre microservicios bancarios y sus contratos de API. Un microservicio debe tener tests, observabilidad, y un contrato OpenAPI antes de exponerse.

## Sección 2
Otra sección. Habla de seguridad básica para APIs internas. Las APIs internas no deben loggear datos personales identificables, según la política del banco.
"""


def test_chunker_respects_section_boundaries():
    chunks = chunk_document(
        doc_id="doc_test",
        doc_title="Doc Test",
        text=DOC,
        domain="architecture",
        allowed_roles=("dev",),
        config=ChunkerConfig(target_tokens=200, overlap_tokens=20, min_chunk_tokens=10),
    )
    assert len(chunks) >= 2
    titles = {c.section_title for c in chunks}
    assert "Sección 1" in titles
    assert "Sección 2" in titles


def test_chunker_metadata_propagation():
    chunks = chunk_document(
        doc_id="doc_test",
        doc_title="Doc Test",
        text=DOC,
        domain="security",
        allowed_roles=("security", "auditor"),
    )
    for c in chunks:
        assert c.doc_id == "doc_test"
        assert c.domain == "security"
        assert "security" in c.allowed_roles
        assert c.token_count > 0
        assert c.chunk_id.startswith("doc_test_s")
