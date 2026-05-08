# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Banking-grade AI helpdesk prototype. Multi-agent RAG (Architecture, Security, Production specialists) orchestrated by LangGraph, served by FastAPI, consumed by a Next.js 15 chat UI. Designed around three pillars: traceability, verifiable anti-hallucination, defense-in-depth anti-prompt-injection.

Stack: Python 3.12 + FastAPI + LangGraph + ChromaDB + OpenAI + Langfuse + Next.js 15 (React 19, Tailwind 4 beta).

## Common commands

Everything runs inside Docker via `make`. Do not invoke `pytest` / `uvicorn` / `next` on the host — they assume the in-container layout (`/app/docs_kb`, `/app/data`, Chroma at `chroma:8000`).

```bash
make up            # docker compose up --build -d  (api:8080, frontend:3000, langfuse:3001)
make down
make logs          # tail api logs
make ingest        # re-run ingest CLI inside api container
make test          # full pytest suite (unit + integration + adversarial)
make eval          # Ragas + custom metrics → eval/reports/ragas_report.json
make adversarial   # only the prompt-injection suite (gate: 10/10)
make lint          # import-linter (architecture contracts) + ruff
make clean         # down + remove volumes (wipes Chroma + feedback.db)
```

Single test:

```bash
docker compose exec api pytest tests/unit/application/test_output_validator.py -v
docker compose exec api pytest tests/adversarial/test_prompt_injection_suite.py::test_canonical_block -v
```

Bootstrap requires `OPENAI_API_KEY` in `.env` (copy from `.env.example`). Adversarial + eval suites call OpenAI — they cost money and need network.

## Architecture (the parts that span files)

### Hexagonal layering — enforced in CI

`backend/src/` is split into four layers and `import-linter` (configured in `backend/pyproject.toml`) enforces the dependency direction. **Breaking these contracts fails `make lint` and CI.**

```
domain         ← pure: entities, value_objects, policies. No framework imports.
application    ← ports (Protocols), DTOs, agents, security, retrieval, use_cases.
                 Cannot import infrastructure or api.
infrastructure ← concrete adapters (openai, chroma, langfuse, sqlite, langgraph_builder).
                 Cannot import api or application.use_cases.
api            ← FastAPI: container.py (DI), routes, middleware, schemas.
```

When swapping a provider (OpenAI → Azure, Chroma → pgvector), edit a single file in `infrastructure/` that implements the existing port in `application/ports/`. Don't reach into `api/` or leak adapter imports into `application/`.

### Composition root

`backend/src/api/container.py` is the **only** place where ports are bound to adapters. `Container.__post_init__` wires the entire object graph (LLM, embeddings, vector store, BM25, hybrid search, security stack, agents, orchestrator, LangGraph). `get_container()` is `lru_cache`d — single instance per process. The ingest CLI uses `build_container_for_ingest()` so it can run with Langfuse keys absent.

### LangGraph orchestrator

`backend/src/infrastructure/graph/langgraph_builder.py` builds a `StateGraph` over `OrchestratorState` (TypedDict). Flow:

```
sanitize → injection_check → router → fan_out (parallel agent::*) →
consolidator → output_validator → finalize → END
                                        ↘ blocked / insufficient terminals
```

Fan-out uses LangGraph conditional edges that return a list of node names; per-agent nodes append to `agent_responses` via a list-concat reducer. The router's `selected_agents` is filtered against `orchestrator.agent_names` — never trust the LLM-selected list.

Adding a new agent = add a class in `application/agents/`, register it in the `agents=[…]` list inside `Container.__post_init__`. The graph rebuilds nodes for `self._orch.agent_names` automatically.

### Anti-prompt-injection (defense in depth)

Nine layers, ordered (see README for the full table). The non-obvious ones when editing:

- **Spotlight encoding** (`application/security/spotlight.py`): user input wrapped in `⟪user_query⟫`, retrieved context in `⟪context⟫`. System prompts must declare those blocks as DATA, not instructions. Never strip those delimiters in agent prompts.
- **Output validator** (`application/security/output_validator.py`): rolling 30-char hash leak detection vs. the `system_prompt_fragments` passed at construction. If you add new immutable system text, add it to the fragments tuple in `Container.__post_init__` or it won't be checked for leaks.
- **PII redactor**: presidio + LATAM regexes. Runs **before** injection check and before retrieval — chunks are never indexed with raw PII from query rephrases.

The 10-attack adversarial suite is a CI gate. If you change the security stack, expect to re-tune patterns; never lower the threshold to make tests pass.

### Anti-hallucination

Three guards, all required:

1. **Pydantic structured output** — every `AgentResponseDTO` / `ConsolidatedResponseDTO` carries `citations[]`, `confidence: float`, `sufficient_context: bool`.
2. **Output Validator** — substantive answers (>80 chars) without a `Citation` are rejected.
3. **Confidence Gate** (`domain/policies/confidence_policy.py`) — below `CONFIDENCE_THRESHOLD` (default 0.65) or `sufficient_context=False` → returns `CANONICAL_INSUFFICIENT` literal. Don't bypass this; it's the canonical "I don't know" path.

### RBAC by metadata

Each chunk has `allowed_roles` in Chroma metadata. `X-User-Role` header filters the retrieval **before** top-k. The role mapping per document is fixed in the docs themselves (see README table). If a user with insufficient role asks → retrieval returns nothing → confidence gate fires → canonical insufficient response. This is the demo for "the system says no" without Keycloak.

### Reranker

`BGEReranker` exists behind the `Reranker` port but is OFF by default (`ENABLE_RERANKER=false`). Corpus is 3 docs ≈ 21 chunks; reranking adds ~200ms with no measurable lift. Enable when KB > ~200 chunks.

### Frontend

Plain Next.js 15 App Router. The `/api/chat` route in `frontend/app/api/` proxies to the backend, injecting `X-API-Key` and `X-User-Role` server-side so the API key never reaches the browser. `BACKEND_URL` (Docker network name `api:8080`) is set in `docker-compose.yml`. No shadcn-ui — small custom components in `components/ui/` + Tailwind 4.

### Eval

`eval/run_ragas.py` runs Ragas (`faithfulness`, `answer_relevancy`, `context_precision`) over `eval/golden_set.jsonl` plus custom metrics (citation_present_rate, correct_doc_rate, refusal_rate, rbac_block_rate). Reports land in `eval/reports/`. Judge is OpenAI — costs ~$0.10/run.

## Things that are easy to break

- **Bypassing `Container`**: instantiating adapters directly in routes/use cases breaks DI and makes tests impossible. Always inject ports.
- **Editing the graph without updating `OrchestratorState`**: nodes return partial state dicts merged into the TypedDict. Add new keys to the state class first.
- **Logging the user payload**: `structlog` is configured to log only IDs, role, intent. Never log `query_text` or `final_answer` directly — compliance constraint.
- **Mutating `participating_agents` from the LLM consolidator output**: the graph deliberately overrides it with `routed_agents` (`langgraph_builder.py::_consolidator`). Don't "fix" that.
- **Touching `entrypoint.sh` ingest call**: it runs `--skip-if-populated`, idempotent. Removing the flag forces a re-ingest on every container start and bloats Chroma.
