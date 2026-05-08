"""DI Container: wires ports → adapters at startup."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.agents.architecture_agent import ArchitectureAgent
from src.application.agents.orchestrator_agent import OrchestratorAgent
from src.application.agents.production_agent import ProductionAgent
from src.application.agents.security_agent import SecurityAgent
from src.application.ports.embeddings_provider import EmbeddingsProvider
from src.application.ports.feedback_repository import FeedbackRepository
from src.application.ports.llm_provider import LLMProvider
from src.application.ports.reranker import Reranker
from src.application.ports.tracer import Tracer
from src.application.ports.vector_store import VectorStore
from src.application.retrieval.bm25_index import BM25Index
from src.application.retrieval.hybrid_search import HybridSearch
from src.application.security.injection_detector import InjectionDetector
from src.application.security.output_validator import OutputValidator
from src.application.security.pii_redactor import PIIRedactor
from src.application.security.spotlight import SPOTLIGHT_SYSTEM_RULES
from src.application.use_cases.answer_query import AnswerQuery
from src.application.use_cases.record_feedback import RecordFeedback
from src.domain.policies.confidence_policy import ConfidencePolicy
from src.infrastructure.embeddings.openai_embeddings import OpenAIEmbeddings
from src.infrastructure.graph.langgraph_builder import LangGraphBuilder
from src.infrastructure.llm.openai_provider import OpenAIProvider
from src.infrastructure.observability.langfuse_tracer import LangfuseTracer, NullTracer
from src.infrastructure.persistence.sqlite_feedback_repo import SqliteFeedbackRepo
from src.infrastructure.vector.chroma_store import ChromaStore


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    api_key: str = "mesa-demo-key"

    chroma_host: str = "chroma"
    chroma_port: int = 8000

    langfuse_host: str = "http://langfuse:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    enable_reranker: bool = False
    confidence_threshold: float = 0.65

    docs_path: str = "/app/docs_kb"
    db_path: str = "/app/data/feedback.db"
    log_level: str = "INFO"
    rate_limit_per_min: int = 10


@dataclass
class Container:
    settings: Settings
    llm: LLMProvider = field(init=False)
    embeddings: EmbeddingsProvider = field(init=False)
    vector_store: VectorStore = field(init=False)
    bm25_index: BM25Index = field(init=False)
    reranker: Reranker | None = field(init=False)
    hybrid_search: HybridSearch = field(init=False)
    injection_detector: InjectionDetector = field(init=False)
    pii_redactor: PIIRedactor = field(init=False)
    output_validator: OutputValidator = field(init=False)
    tracer: Tracer = field(init=False)
    feedback_repo: FeedbackRepository = field(init=False)
    orchestrator: OrchestratorAgent = field(init=False)
    confidence_policy: ConfidencePolicy = field(init=False)
    answer_query_uc: AnswerQuery = field(init=False)
    record_feedback_uc: RecordFeedback = field(init=False)

    def __post_init__(self) -> None:
        s = self.settings
        self.llm = OpenAIProvider(api_key=s.openai_api_key)
        self.embeddings = OpenAIEmbeddings(api_key=s.openai_api_key)
        self.vector_store = ChromaStore(host=s.chroma_host, port=s.chroma_port)
        self.bm25_index = BM25Index()
        self.reranker = None
        if s.enable_reranker:
            from src.infrastructure.reranker.bge_reranker import BGEReranker

            self.reranker = BGEReranker()
        self.hybrid_search = HybridSearch(
            self.vector_store, self.embeddings, self.bm25_index, self.reranker
        )
        self.injection_detector = InjectionDetector(self.llm)
        self.pii_redactor = PIIRedactor(use_presidio=True)
        # Provide system prompt fragments for leak detection
        self.output_validator = OutputValidator(
            system_prompt_fragments=(
                SPOTLIGHT_SYSTEM_RULES,
                "REGLAS INMUTABLES DE SEGURIDAD",
                "Sos un asistente técnico bancario senior",
            )
        )
        if s.langfuse_public_key and s.langfuse_secret_key:
            self.tracer = LangfuseTracer(
                public_key=s.langfuse_public_key,
                secret_key=s.langfuse_secret_key,
                host=s.langfuse_host,
            )
        else:
            self.tracer = NullTracer()
        self.feedback_repo = SqliteFeedbackRepo(db_path=s.db_path)

        agents = [
            ArchitectureAgent(self.llm, self.hybrid_search),
            SecurityAgent(self.llm, self.hybrid_search),
            ProductionAgent(self.llm, self.hybrid_search),
        ]
        self.orchestrator = OrchestratorAgent(self.llm, agents)
        self.confidence_policy = ConfidencePolicy(threshold=s.confidence_threshold)

        graph_builder = LangGraphBuilder(
            orchestrator=self.orchestrator,
            injection_detector=self.injection_detector,
            pii_redactor=self.pii_redactor,
            output_validator=self.output_validator,
            confidence_policy=self.confidence_policy,
        )
        graph = graph_builder.build()

        self.answer_query_uc = AnswerQuery(graph=graph, tracer=self.tracer, pii_redactor=self.pii_redactor)
        self.record_feedback_uc = RecordFeedback(self.feedback_repo)

    async def warm_bm25(self) -> None:
        """Rebuild BM25 from chunks already in vector store (idempotent at boot)."""
        chunks = await self.vector_store.list_all()
        self.bm25_index.build(chunks)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container(settings=get_settings())


def build_container_for_ingest() -> Container:
    """Used by scripts/ingest.py — bypasses Langfuse if not configured."""
    return Container(settings=get_settings())
