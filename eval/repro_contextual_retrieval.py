r"""Replay the Contextual Retrieval measurements OFFLINE, at zero API cost.

``contextual_retrieval_experiment.py`` needs two indexed collections per chunk
budget, and building the contextual ones normally costs ~316 LLM calls
(~1,7 M input tokens). This script rebuilds all four collections from the context
cache instead, so the published numbers of
``eval/reports/2026-07-26_contextual_retrieval{,_440}.md`` can be re-derived
without paying anything — and without touching the production store.

WHY IT EXISTS. The measurement rests on one precaution: after ranking, each
chunk's text is restored to the pre-contextualisation one
(``metadata["text_raw"]``), so a generated context that quotes an expected
keyword cannot manufacture a hit. That restoration lives in the experiment
script, which no test covers — a regression there would silently invert the
published conclusions. Running this script and comparing its output to the two
reports is what catches that.

GUARANTEES.
* Zero LLM calls: the backend is a stub that *raises* on any call, so a cache
  miss aborts instead of quietly costing money.
* Read-only on the repository: the vector store goes to a work directory outside
  the tree, the context cache is used through a copy, and no report is written.
  ``chroma_db/`` — the production store — is never opened.

Run:
    python eval/repro_contextual_retrieval.py
    # PowerShell:  .\.venv\Scripts\python.exe eval/repro_contextual_retrieval.py

Collections are kept between runs, so only the first one pays the embedding
cost; ``--fresh`` forces a rebuild. Requires ``corpus/contexts.jsonl``, which is
not versioned (derived data, §5.3.1): on a fresh clone, regenerate it with
``python -m assistant_amu.ingestion contextualize``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPO_CACHE = REPO / "corpus" / "contexts.jsonl"

# Budgets to replay: (label, --max-tokens value). None = the production default
# of 500, i.e. the collection the main report compares against.
BUDGETS = (("500 tokens", None), ("440 tokens", 440))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--work-dir",
        default=str(Path(tempfile.gettempdir()) / "amu_repro_contextual"),
        help="where the throwaway vector store lives (default: a temp directory)",
    )
    parser.add_argument(
        "--fresh", action="store_true", help="wipe the work directory before replaying"
    )
    return parser.parse_args(argv)


def _cache_model(path: Path) -> str:
    """Model name carried by the cache — the stub must answer to it.

    The cache is keyed by (content address, model, prompt version): a stub
    announcing another name would miss on every chunk and abort on the first one.
    Reading the name from the cache keeps the two in step by construction.
    """
    models: collections.Counter[str] = collections.Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            models[json.loads(line)["model"]] += 1
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    if not models:
        raise SystemExit(f"No usable entry in {path} — regenerate it with `contextualize`.")
    name, count = models.most_common(1)[0]
    print(f"cache: {sum(models.values())} entrées, modèle retenu {name!r} ({count})")
    return name


class CacheOnlyBackend:
    """Stands in for the LLM: every context must already be cached."""

    def __init__(self, name: str):
        self.name = name

    def generate(self, system: str, user: str) -> str:
        raise SystemExit(
            "DÉFAUT DE CACHE — poursuivre exigerait un appel de modèle payant. "
            "Le corpus ou le prompt a changé depuis la génération du cache : "
            "relancer `python -m assistant_amu.ingestion contextualize`."
        )


def build(tag: str, max_tokens: int | None, cache_copy: Path, backend) -> tuple:
    """Index the baseline and contextual collections for one chunk budget."""
    from assistant_amu.config import get_settings
    from assistant_amu.ingestion.contextualize import ContextCache, contextualize_chunks
    from assistant_amu.ingestion.download import SOURCES_YAML, load_sources
    from assistant_amu.ingestion.pipeline import ingest_corpus
    from assistant_amu.retrieval.embedder import Embedder
    from assistant_amu.retrieval.vector_store import VectorStore

    settings = get_settings()
    embedder = Embedder(settings.embedding_model)
    kwargs = {"max_tokens": max_tokens} if max_tokens else {}
    report = ingest_corpus(load_sources(SOURCES_YAML), **kwargs)
    print(f"[{tag}] {report.summary()}", flush=True)

    base_name = "amu_docs" if max_tokens is None else f"amu_docs_{max_tokens}"
    ctx_name = f"{base_name}_ctx"

    base = VectorStore.from_settings(settings, embedder=embedder, collection_name=base_name)
    if base.count() == 0:
        base.add_chunks(report.chunks)
    print(f"[{tag}] baseline {base_name} : {base.count()} fragments", flush=True)

    ctx = VectorStore.from_settings(settings, embedder=embedder, collection_name=ctx_name)
    if ctx.count() == 0:
        contextual, ctx_report = contextualize_chunks(
            report.chunks, report.documents, backend,
            cache=ContextCache(cache_copy), progress=lambda _: None,
        )
        print(f"[{tag}] {ctx_report.summary()}", flush=True)
        ctx.add_chunks(contextual)
    print(f"[{tag}] contextuelle {ctx_name} : {ctx.count()} fragments", flush=True)
    return base, ctx


def measure(tag: str, max_tokens: int | None, cache_copy: Path, backend) -> None:
    """Print every figure the report tabulates, for one chunk budget."""
    from assistant_amu.config import get_settings
    from assistant_amu.evaluation import evaluate_retrieval, load_questions
    from assistant_amu.retrieval.embedder import Embedder

    import contextual_retrieval_experiment as experiment  # sibling script, same directory

    settings = get_settings()
    base_store, ctx_store = build(tag, max_tokens, cache_copy, backend)
    embedder = Embedder(settings.embedding_model)

    # Same wiring as the report: baseline scored as-is, contextual scored on the
    # restored text ("strict"), and a naïve run to quantify the artifact avoided.
    strict = {f"base_{m}": r for m, r in experiment._build_methods(base_store, strict=False).items()}
    strict |= {f"ctx_{m}": r for m, r in experiment._build_methods(ctx_store, strict=True).items()}
    naive = {f"ctx_{m}": r for m, r in experiment._build_methods(ctx_store, strict=False).items()}

    hard, easy = load_questions(experiment.HARD), load_questions(experiment.EASY)

    def recalls(questions, retrievers) -> dict:
        return {k: evaluate_retrieval(questions, retrievers, k).recall for k in experiment.KS}

    hard_recall, easy_recall = recalls(hard, strict), recalls(easy, strict)
    easy_naive = recalls(easy, naive)
    n_hard = sum(1 for q in hard if q.answerable)
    n_easy = sum(1 for q in easy if q.answerable)

    print(f"\n===== {tag} =====")
    for label, recall, n in (("dur", hard_recall, n_hard), ("facile", easy_recall, n_easy)):
        print(f"-- jeu {label} ({n} questions répondables)")
        for method in experiment.METHODS:
            cells = " | ".join(
                f"k={k} : {recall[k][f'base_{method}']:.2f} -> {recall[k][f'ctx_{method}']:.2f} "
                f"({round((recall[k][f'ctx_{method}'] - recall[k][f'base_{method}']) * n):+d} q)"
                for k in experiment.KS
            )
            print(f"   {method:9s} {cells}")

    print("-- comptage naïf contre strict (jeu facile)")
    for method in experiment.METHODS:
        cells = " | ".join(
            f"k={k} : strict {easy_recall[k][f'ctx_{method}']:.2f} "
            f"naïf {easy_naive[k][f'ctx_{method}']:.2f} "
            f"({round((easy_naive[k][f'ctx_{method}'] - easy_recall[k][f'ctx_{method}']) * n_easy):+d} q)"
            for k in experiment.KS
        )
        print(f"   {method:9s} {cells}")

    window = experiment._window_stats(base_store, ctx_store, settings.embedding_model, embedder)
    print(f"-- fenêtre limite={window['limit']} baseline={window['base']} contextuelle={window['ctx']}")
    stats = experiment._context_stats(ctx_store)
    print(
        f"-- contextes {stats['with_context']}/{stats['chunks']}, "
        f"{stats['mean_words']:.1f} mots en moyenne, maximum {stats['max_words']}"
    )
    print(f"-- exemple médian : {stats['sample']!r}")

    for label, questions in (("dur", hard), ("facile", easy)):
        rows = evaluate_retrieval(questions, strict, 5).rows
        print(f"-- détail à k=5, jeu {label}")
        for method in experiment.METHODS:
            won, lost = experiment._changed_rows(rows, method)
            print(f"   {method:9s} gagnées {[r.id for r in won]} perdues {[r.id for r in lost]}")

    flagship = {
        name: experiment._flagship_rank(strict[name])[0]
        for name in ("base_semantic", "ctx_semantic", "base_bm25", "ctx_bm25")
    }
    print(f"-- question phare (rang de la page RSE dans le top-8) : {flagship}")


def main(argv: list[str] | None = None) -> int:
    # Accented output on a cp1252 Windows console would crash otherwise (same
    # guard as ingestion/__main__.py and docs/build_concepts.py).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    args = _parse_args(argv)
    if not REPO_CACHE.exists():
        print(
            f"Cache absent : {REPO_CACHE}\n"
            "Donnée dérivée, non versionnée — la régénérer avec "
            "`python -m assistant_amu.ingestion contextualize` (appels de modèle payants)."
        )
        return 1

    work_dir = Path(args.work_dir)
    if args.fresh and work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"répertoire de travail : {work_dir}")

    # The store must never be the production one, and the settings are read at
    # import time by get_settings() — hence the environment, set before importing
    # anything from the package. LLM_BACKEND avoids requiring an API key: the
    # real backend is never built, only the stub above is used.
    os.environ["CHROMA_PATH"] = str(work_dir / "chroma")
    os.environ.setdefault("LLM_BACKEND", "ollama")

    cache_copy = work_dir / "contexts.jsonl"
    if not cache_copy.exists():
        shutil.copy(REPO_CACHE, cache_copy)

    backend = CacheOnlyBackend(_cache_model(cache_copy))
    for tag, max_tokens in BUDGETS:
        measure(tag, max_tokens, cache_copy, backend)

    print(
        "\nComparer ces chiffres à eval/reports/2026-07-26_contextual_retrieval.md "
        "(500 tokens) et …_440.md : tout écart signale une régression du comptage "
        "strict ou du découpage, non un aléa de mesure — le cache rend l'exécution "
        "déterministe."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
