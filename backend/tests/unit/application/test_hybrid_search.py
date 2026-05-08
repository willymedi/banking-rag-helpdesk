from src.application.retrieval.bm25_index import BM25Index
from src.application.retrieval.hybrid_search import HybridSearch
from src.domain.entities.document import Chunk


class _StaticVectorStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    async def upsert(self, chunks): pass
    async def count(self) -> int: return len(self._chunks)
    async def list_all(self, filter_role=None): return self._chunks

    async def search(self, query_embedding, top_k=10, filter_role=None, filter_domain=None):
        out = []
        for c in self._chunks:
            if filter_role and filter_role.lower() not in {r.lower() for r in c.allowed_roles}:
                continue
            if filter_domain and c.domain != filter_domain:
                continue
            out.append((c, 0.5))
            if len(out) >= top_k:
                break
        return out


class _FakeEmb:
    async def embed_one(self, text: str): return [0.0] * 8
    async def embed_many(self, texts): return [[0.0] * 8 for _ in texts]


def _mk(cid, text, domain="architecture", roles=("dev", "auditor")):
    return Chunk(
        chunk_id=cid, doc_id="d", doc_title="t", section_title="s", section_path=("s",),
        text=text, offset_start=0, offset_end=len(text), domain=domain,
        allowed_roles=roles, doc_version="v1", token_count=len(text.split()),
    )


def test_rrf_fuses_two_rankings():
    chunks = [
        _mk("c1", "microservicio contrato openapi"),
        _mk("c2", "logs no contienen pii"),
        _mk("c3", "release runbook"),
    ]
    bm25 = BM25Index()
    bm25.build(chunks)
    vs = _StaticVectorStore(chunks)
    hs = HybridSearch(vector_store=vs, embeddings=_FakeEmb(), bm25_index=bm25)

    import asyncio
    res = asyncio.run(hs.search("microservicio openapi", user_role="dev", agent_domain="architecture", top_k=3))
    ids = [c.chunk_id for c, _ in res]
    assert "c1" in ids


def test_rbac_filter_excludes_unauthorized_chunks():
    chunks = [
        _mk("c1", "publica info", domain="security", roles=("security",)),
    ]
    bm25 = BM25Index()
    bm25.build(chunks)
    vs = _StaticVectorStore(chunks)
    hs = HybridSearch(vector_store=vs, embeddings=_FakeEmb(), bm25_index=bm25)
    import asyncio
    res = asyncio.run(hs.search("info", user_role="dev", agent_domain="security", top_k=3))
    assert res == []
