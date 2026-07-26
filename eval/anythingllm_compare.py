"""Compare AnythingLLM (default Docker deployment) against assistant-amu on the
same AMU corpus and the same eval/questions.yaml — a documented side experiment,
not part of the contractual PRD scope.

Requires a running AnythingLLM instance, configured once by hand (first-run
onboarding — provider choice, workspace creation — has no API): Docker
container on localhost:3001, Mistral provider (mistral-small-latest), workspace
slug in ANYTHINGLLM_WORKSPACE_SLUG. Config read from .env:
ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE_SLUG.

Usage:
    python eval/anythingllm_compare.py ingest
    python eval/anythingllm_compare.py ask --questions eval/questions.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from assistant_amu.config import PROJECT_ROOT
from assistant_amu.evaluation import load_questions
from assistant_amu.ingestion.download import load_sources, target_filename

CORPUS_RAW = PROJECT_ROOT / "corpus" / "raw"
RESULTS_PATH = PROJECT_ROOT / "eval" / "reports" / "anythingllm_raw_answers.json"


def _config() -> dict:
    return {
        "base": os.environ["ANYTHINGLLM_BASE_URL"].rstrip("/"),
        "key": os.environ["ANYTHINGLLM_API_KEY"],
        "slug": os.environ["ANYTHINGLLM_WORKSPACE_SLUG"],
    }


def _client(cfg: dict) -> httpx.Client:
    return httpx.Client(
        base_url=cfg["base"], headers={"Authorization": f"Bearer {cfg['key']}"}, timeout=120
    )


def cmd_ingest(args: argparse.Namespace) -> int:
    cfg = _config()
    sources = load_sources()
    locations: list[str] = []
    with _client(cfg) as client:
        for i, source in enumerate(sources):
            if source.type == "pdf":
                fname = target_filename(source, i)
                with open(CORPUS_RAW / fname, "rb") as f:
                    resp = client.post("/api/v1/document/upload", files={"file": (fname, f)})
            else:
                resp = client.post("/api/v1/document/upload-link", json={"link": source.url})
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print(f"  ECHEC : {source.title}: {data.get('error')}")
                continue
            doc = data["documents"][0]
            locations.append(doc["location"])
            print(f"  ok ({doc.get('wordCount', '?')} mots) : {source.title}")

        resp = client.post(
            f"/api/v1/workspace/{cfg['slug']}/update-embeddings",
            json={"adds": locations, "deletes": []},
        )
        resp.raise_for_status()

    print(f"[ingest] {len(locations)}/{len(sources)} documents indexés dans le workspace '{cfg['slug']}'")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    cfg = _config()
    questions = load_questions(Path(args.questions))
    results = []
    with _client(cfg) as client:
        for q in questions:
            resp = client.post(
                f"/api/v1/workspace/{cfg['slug']}/chat",
                json={"message": q.question, "mode": "query"},
            )
            resp.raise_for_status()
            data = resp.json()
            sources = data.get("sources") or []
            results.append(
                {
                    "id": q.id,
                    "question": q.question,
                    "answerable": q.answerable,
                    "expected_source": q.expected_source,
                    "expected_keywords": q.expected_keywords,
                    "answer": data.get("textResponse", ""),
                    "num_sources": len(sources),
                    "sources": sources,
                }
            )
            print(f"  {q.id}: {len(sources)} source(s)")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ask] {len(results)} questions -> {RESULTS_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AnythingLLM vs assistant-amu — side experiment.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("--questions", default=str(PROJECT_ROOT / "eval" / "questions.yaml"))
    args = parser.parse_args(argv)
    return cmd_ingest(args) if args.cmd == "ingest" else cmd_ask(args)


if __name__ == "__main__":
    sys.exit(main())
