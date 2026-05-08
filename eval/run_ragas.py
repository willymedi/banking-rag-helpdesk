"""Ragas eval runner.

Loads golden_set.jsonl, calls the deployed API for each query, builds a Ragas
dataset and computes faithfulness, context_precision, context_recall,
answer_relevancy. Saves HTML + JSON report.

Usage (inside api container):
    python -m eval.run_ragas
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

API_URL = os.getenv("EVAL_API_URL", "http://localhost:8080")
API_KEY = os.getenv("API_KEY", "mesa-demo-key")
GOLDEN = Path(__file__).parent / "golden_set.jsonl"
REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)


async def call_api(query: str, role: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{API_URL}/query",
            headers={"X-API-Key": API_KEY, "X-User-Role": role, "Content-Type": "application/json"},
            json={"query": query},
        )
        r.raise_for_status()
        return r.json()


async def collect() -> list[dict]:
    out = []
    with GOLDEN.open() as f:
        cases = [json.loads(line) for line in f if line.strip()]
    for case in cases:
        try:
            resp = await call_api(case["query"], case["user_role"])
        except Exception as exc:
            resp = {"answer": "", "citations": [], "blocked_reason": f"api_error:{exc}"}
        out.append({"case": case, "response": resp})
    return out


def to_ragas_dataset(items: list[dict]):
    from datasets import Dataset

    rows = []
    for it in items:
        c = it["case"]
        r = it["response"]
        rows.append(
            {
                "question": c["query"],
                "answer": r.get("answer", ""),
                "contexts": [cit["snippet"] for cit in r.get("citations", [])] or [""],
                "ground_truth": "",  # opcional
                "expected_doc_ids": c.get("expected_doc_ids", []),
                "must_be_sufficient": c.get("must_be_sufficient", True),
                "blocked_reason": r.get("blocked_reason", ""),
                "sufficient_context": r.get("sufficient_context", False),
            }
        )
    return Dataset.from_list(rows)


def custom_metrics(items: list[dict]) -> dict:
    """Métricas propias además de Ragas (que requiere LLM judge → cost)."""
    n = len(items)
    cite_present = sum(1 for it in items if it["response"].get("citations"))
    correct_doc = 0
    correct_refusal = 0
    rbac_hits = 0
    rbac_total = 0
    for it in items:
        c = it["case"]
        r = it["response"]
        cited_docs = {cit.get("doc_id", "") for cit in r.get("citations", [])}
        if c["domain"] == "rbac":
            rbac_total += 1
            # rol no debe acceder al doc → no debe haber citas o sufficient_context=False
            if not r.get("sufficient_context") or not cited_docs:
                rbac_hits += 1
        elif not c.get("must_be_sufficient", True):
            # out-of-scope: debe rechazar
            if not r.get("sufficient_context"):
                correct_refusal += 1
        else:
            # debe responder y citar al menos un doc esperado
            if cited_docs & set(c.get("expected_doc_ids", [])):
                correct_doc += 1
    return {
        "n": n,
        "citation_present_rate": cite_present / n if n else 0.0,
        "correct_doc_rate": correct_doc / max(1, sum(1 for it in items if it["case"].get("must_be_sufficient", True) and it["case"]["domain"] != "rbac")),
        "correct_refusal_rate": correct_refusal / max(1, sum(1 for it in items if not it["case"].get("must_be_sufficient", True) and it["case"]["domain"] != "rbac")),
        "rbac_block_rate": rbac_hits / rbac_total if rbac_total else 0.0,
    }


async def main() -> None:
    print(f"[ragas] calling API at {API_URL} for {GOLDEN.name}")
    items = await collect()

    custom = custom_metrics(items)
    print("[custom-metrics]", json.dumps(custom, indent=2))

    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings as LCEmbeddings
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import answer_relevancy, context_precision, faithfulness

        api_key = os.getenv("OPENAI_API_KEY", "")
        judge_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key, max_tokens=4096)
        )
        judge_emb = LangchainEmbeddingsWrapper(
            LCEmbeddings(model="text-embedding-3-small", api_key=api_key)
        )

        ds = to_ragas_dataset(items)
        ds = ds.filter(lambda r: r["answer"] and r["contexts"][0])
        if len(ds) > 0:
            ragas_result = evaluate(
                ds,
                metrics=[faithfulness, answer_relevancy, context_precision],
                llm=judge_llm,
                embeddings=judge_emb,
                show_progress=False,
            )
            # Ragas EvaluationResult: use .scores (per-row) or to_pandas() for aggregate
            try:
                df = ragas_result.to_pandas()
                ragas_dict = {col: float(df[col].mean()) for col in df.columns if df[col].dtype.kind in "fc"}
            except Exception:
                ragas_dict = {k: float(v) for k, v in dict(ragas_result).items()}
        else:
            ragas_dict = {"note": "no rows eligible for Ragas (empty answers)"}
    except Exception as exc:
        ragas_dict = {"error": str(exc)}

    report = {"custom": custom, "ragas": ragas_dict, "samples": items[:3]}
    out_json = REPORT_DIR / "ragas_report.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[ragas] report → {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
