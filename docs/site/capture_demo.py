"""Record a real run of the demonstration scenarios against a local API.

The demonstration page is a pure HTTP client of ``POST /ask``, which needs the
index, the embedding model and an LLM backend. Read the Docs serves files and
runs nothing, so the live demonstration cannot exist there. This script plays
the scenarios of ``demo-scenarios.json`` against a running API and writes down
what actually came back — answers, cited excerpts, scores, latency. The site
then restitutes a real exchange instead of a mock-up.

Two things are recorded beside the answer. The retrieved fragments are read
straight from the vector store, because ``/ask`` deliberately returns no source
when it refuses (F6): without them a refusal would be indistinguishable from an
empty retrieval, when the two are exactly what the page must tell apart. And a
throwaway question is asked first, so the cost of loading the embedding model
does not land on the latency of the first recorded exchange.

Unlike the rest of ``docs/site/``, the capture is versioned: it is the only
trace the build server has of a run it cannot perform. It must therefore be
taken as it comes — an exchange that goes badly is recorded like the others.

Usage:
    python -m uvicorn assistant_amu.api.main:app --port 8000   # in another shell
    python docs/site/capture_demo.py
    python docs/site/capture_demo.py --api http://127.0.0.1:8000 --output FILE
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

from assistant_amu.retrieval.vector_store import VectorStore

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent.parent
SCENARIOS_PATH = SITE_DIR / "demo-scenarios.json"
CAPTURE_PATH = SITE_DIR / "demo-capture.json"

# An answer takes a retrieval, a condensation and a generation: the backend call
# dominates and a short timeout would cut a legitimate run.
TIMEOUT_S = 120.0


def short_commit() -> str:
    """The commit the capture was taken at — a condition of the run, not a date."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def retrieved_fragments(store: VectorStore, query: str, k: int) -> list[dict]:
    """What the search returned for a query, cited or not."""
    return [
        {
            "title": str(chunk.metadata.get("source_title", "")),
            "section": chunk.metadata.get("section"),
            "page": chunk.metadata.get("page"),
            "score": round(chunk.score, 3),
        }
        for chunk in store.query(query, k=k)
    ]


def capture_exchange(client: httpx.Client, store: VectorStore, exchange: dict) -> dict:
    """Play one question and record the answer with what it cost to produce."""
    payload = {"question": exchange["question"], "k": exchange.get("k", 5)}
    if "history" in exchange:
        payload["history"] = exchange["history"]

    started = time.perf_counter()
    response = client.post("/ask", json=payload, timeout=TIMEOUT_S)
    latency = time.perf_counter() - started
    response.raise_for_status()
    answer = response.json()

    # Same precedence as RagPipeline.prepare: a rewrite wins over a condensation,
    # which wins over the raw question (rag.py:156).
    query = answer.get("rewritten_query") or answer.get("condensed_question") or exchange["question"]

    return {
        "question": exchange["question"],
        "history": exchange.get("history", []),
        "k": payload["k"],
        "answer": answer["answer"],
        "sources": answer["sources"],
        "retrieval_query": query,
        "retrieval": retrieved_fragments(store, query, payload["k"]),
        "model": answer["model"],
        "retrieved_chunks": answer["retrieved_chunks"],
        "condensed_question": answer.get("condensed_question"),
        "rewritten_query": answer.get("rewritten_query"),
        "latency_s": round(latency, 2),
    }


def capture(api_url: str) -> dict:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    with httpx.Client(base_url=api_url) as client:
        health = client.get("/health", timeout=TIMEOUT_S)
        health.raise_for_status()
        state = health.json()
        if state.get("chroma") != "ok" or not state.get("chunks"):
            raise SystemExit(f"index empty or unreachable: {state}")

        store = VectorStore.from_settings()
        print("  (warm-up, not recorded)")
        client.post("/ask", json={"question": "test", "k": 1}, timeout=TIMEOUT_S)

        recorded = []
        for scenario in scenarios["scenarios"]:
            exchanges = []
            for exchange in scenario["exchanges"]:
                print(f"  {exchange['question']}")
                exchanges.append(capture_exchange(client, store, exchange))
            recorded.append({"id": scenario["id"], "exchanges": exchanges})

    models = {exchange["model"] for scenario in recorded for exchange in scenario["exchanges"]}
    # Data only: the titles and the prose stay in demo-scenarios.json, so rewording
    # the page never means paying for a new run.
    return {
        "conditions": {
            "documents": state["documents"],
            "chunks": state["chunks"],
            "models": sorted(models),
            "commit": short_commit(),
        },
        "scenarios": recorded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:8000",
        help="base URL of the running API (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CAPTURE_PATH,
        help="file the capture is written to (default: docs/site/demo-capture.json)",
    )
    args = parser.parse_args()

    print(f"capturing against {args.api}")
    result = capture(args.api)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    total = sum(len(scenario["exchanges"]) for scenario in result["scenarios"])
    print(f"captured {total} exchanges -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
