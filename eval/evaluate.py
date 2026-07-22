"""Reproducible evaluation harness — CLI (PRD §7.6, F8).

Examples:
    python eval/evaluate.py --mode retrieval --method all --k 5
    python eval/evaluate.py --mode retrieval --method all --embedding-model dangvantuan/sentence-camembert-base
    python eval/evaluate.py --mode retrieval --chunk-report --chunk-sizes 300 500
    python eval/evaluate.py --mode end-to-end --k 5

Retrieval mode measures recall@k for semantic / bm25 / rrf (RRF fusion is
*measured only*; /ask stays semantic in V1). Dated Markdown reports are written
to eval/reports/. The first run establishes the baseline (record it in the
README); later runs compare against it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import (
    RrfRetriever,
    evaluate_conversation,
    evaluate_end_to_end,
    evaluate_retrieval,
    load_questions,
    load_scenarios,
    render_conversation_report,
    render_end_to_end_report,
    render_retrieval_report,
)
from assistant_amu.generation.llm import build_backend
from assistant_amu.generation.rag import RagPipeline
from assistant_amu.ingestion.download import load_sources
from assistant_amu.ingestion.pipeline import ingest_corpus
from assistant_amu.models import Chunk, RetrievedChunk
from assistant_amu.retrieval.bm25_store import Bm25Index
from assistant_amu.retrieval.embedder import Embedder
from assistant_amu.retrieval.vector_store import SemanticRetriever, VectorStore

QUESTIONS = PROJECT_ROOT / "eval" / "questions.yaml"
SCENARIOS = PROJECT_ROOT / "eval" / "scenarios.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
METHODS = ("semantic", "bm25", "rrf")


def _build_retrievers(store: VectorStore, method: str) -> dict:
    ids, docs, metas = store.get_all()
    semantic = SemanticRetriever(store)
    bm25 = Bm25Index(ids, docs, metas)
    lookup = {
        i: RetrievedChunk(i, str(m.get("doc_id", "")), d, m, 0.0)
        for i, d, m in zip(ids, docs, metas)
    }
    all_retrievers = {"semantic": semantic, "bm25": bm25, "rrf": RrfRetriever(semantic, bm25, lookup)}
    chosen = METHODS if method == "all" else (method,)
    return {m: all_retrievers[m] for m in chosen}


def _write_report(content: str, name: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / name
    path.write_text(content, encoding="utf-8")
    return path


def _run_retrieval(store: VectorStore, method: str, k: int, *, backend: str, model: str,
                   tag: str = "", questions_path: Path = QUESTIONS) -> None:
    questions = load_questions(questions_path)
    report = evaluate_retrieval(questions, _build_retrievers(store, method), k)
    today = date.today().isoformat()
    content = render_retrieval_report(report, date=today, backend=backend, model=model)
    name = f"{today}_retrieval_{method}{tag}_k{k}.md"
    path = _write_report(content, name)
    print(f"[retrieval] {model} | " + " ".join(f"{m}={report.recall[m]:.2f}" for m in report.recall))
    print(f"  report: {path}")


def cmd_retrieval(args: argparse.Namespace) -> int:
    settings = get_settings()
    base_store = VectorStore.from_settings(settings)
    if base_store.count() == 0:
        print("Empty collection — run `python -m assistant_amu.ingestion index` first.")
        return 1
    backend = build_backend(settings).name
    questions_path = Path(args.questions)

    if args.chunk_report:
        return _run_chunk_report(args, settings, backend, questions_path)

    if args.embedding_model:
        _run_with_embedding_model(args, settings, base_store, backend, questions_path)
    else:
        _run_retrieval(base_store, args.method, args.k, backend=backend,
                       model=settings.embedding_model, questions_path=questions_path)
    return 0


def _run_with_embedding_model(args, settings, base_store, backend: str, questions_path: Path) -> None:
    """Re-embed the same chunks in an ephemeral parallel collection (§7.6)."""
    ids, docs, metas = base_store.get_all()
    suffix = args.embedding_model.split("/")[-1].replace("-", "")[:16]
    store = VectorStore(
        path=settings.chroma_path,
        collection_name=f"{settings.chroma_collection}__{suffix}",
        embedder=Embedder(args.embedding_model),
    )
    try:
        store.add_chunks([Chunk(i, str(m.get("doc_id", "")), d, m) for i, d, m in zip(ids, docs, metas)])
        _run_retrieval(store, args.method, args.k, backend=backend, model=args.embedding_model,
                       tag="_altemb", questions_path=questions_path)
    finally:
        store.delete_collection()  # production collection is never touched


def _run_chunk_report(args, settings, backend: str, questions_path: Path) -> int:
    """Re-chunk + re-index the corpus at each size in an ephemeral collection."""
    sources = load_sources()
    for size in args.chunk_sizes:
        report = ingest_corpus(sources, max_tokens=size)
        store = VectorStore(
            path=settings.chroma_path,
            collection_name=f"{settings.chroma_collection}__chunk{size}",
            embedder=Embedder(settings.embedding_model),
        )
        try:
            store.add_chunks(report.chunks)
            _run_retrieval(store, args.method, args.k, backend=backend,
                           model=settings.embedding_model, tag=f"_chunk{size}",
                           questions_path=questions_path)
        finally:
            store.delete_collection()
    return 0


def cmd_end_to_end(args: argparse.Namespace) -> int:
    settings = get_settings()
    pipeline = RagPipeline.from_settings(settings)
    backend = build_backend(settings).name
    rows = evaluate_end_to_end(load_questions(Path(args.questions)), pipeline, args.k)
    today = date.today().isoformat()
    content = render_end_to_end_report(rows, date=today, backend=backend, k=args.k)
    path = _write_report(content, f"{today}_end-to-end_k{args.k}.md")
    correct = sum(1 for r in rows if r.refusal_correct)
    total = sum(1 for r in rows if not r.answerable)
    print(f"[end-to-end] refusal correct: {correct}/{total}")
    print(f"  report: {path}")
    return 0


def cmd_conversation(args: argparse.Namespace) -> int:
    settings = get_settings()
    pipeline = RagPipeline.from_settings(settings)
    backend = build_backend(settings).name
    scenarios = load_scenarios(args.scenarios)
    if not scenarios:
        print("No scenarios in scenarios.yaml yet (see PRD §7.7).")
        return 1
    rows = evaluate_conversation(scenarios, pipeline, args.k)
    today = date.today().isoformat()
    content = render_conversation_report(rows, date=today, backend=backend, k=args.k)
    path = _write_report(content, f"{today}_conversation_k{args.k}.md")
    print(f"[conversation] {len(rows)} turns across {len(scenarios)} scenarios")
    print(f"  report: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AssistantAMU evaluation harness (F8, F12).")
    parser.add_argument("--mode", choices=("retrieval", "end-to-end", "conversation"), required=True)
    parser.add_argument("--method", choices=(*METHODS, "all"), default="all")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--embedding-model", default=None, help="HF id for an alternative embedder (§7.6)")
    parser.add_argument("--chunk-report", action="store_true", help="measure recall across chunk sizes")
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[300, 500])
    parser.add_argument("--questions", default=str(QUESTIONS), help="path to the questions YAML")
    parser.add_argument("--scenarios", default=str(SCENARIOS), help="path to the scenarios YAML (V2)")
    args = parser.parse_args(argv)

    if args.mode == "retrieval":
        return cmd_retrieval(args)
    if args.mode == "conversation":
        return cmd_conversation(args)
    return cmd_end_to_end(args)


if __name__ == "__main__":
    sys.exit(main())
