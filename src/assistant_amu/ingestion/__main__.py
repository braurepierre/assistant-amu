"""Ingestion CLI (PRD F2/F3/F4): ``python -m assistant_amu.ingestion <command>``.

Commands:
  stats         Run extract -> clean -> chunk over the corpus and print counts.
  dump          Print N random chunks with metadata for visual inspection.
  index         Embed the corpus chunks into ChromaDB (idempotent; F3, dedup F2).
  export        Pack the vector store into one archive, to ship to a host.
  search        Retrieve the top-k chunks for a question (manual relevance check, F4).
  contextualize Build the Contextual Retrieval index in a parallel collection (§5.3.1).
"""

from __future__ import annotations

import argparse
import random
import sys
import tarfile
import textwrap
from pathlib import Path

from .contextualize import CACHE_PATH
from .download import RAW_DIR, SOURCES_YAML, load_sources
from .pipeline import ingest_corpus


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", default=str(SOURCES_YAML))
    parser.add_argument("--raw-dir", default=str(RAW_DIR))


def _add_chunking(parser: argparse.ArgumentParser) -> None:
    """Chunk budget override, for indexing a corpus cut differently (§7.6)."""
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="chunk budget in tokens (default: CHUNK_MAX_TOKENS from the settings)",
    )


def _chunking(args: argparse.Namespace) -> dict:
    """Resolve the chunk budget: the flag, else the settings.

    The help above has always announced CHUNK_MAX_TOKENS, but nothing read
    ``settings.chunk_max_tokens`` — the real default was the literal in
    ``chunk.py``, so setting the variable in ``.env`` had no effect whatsoever.
    Reading the settings here is what makes the announced behaviour true.
    """
    from ..config import get_settings

    settings = get_settings()
    override = getattr(args, "max_tokens", None)
    return {
        "max_tokens": override or settings.chunk_max_tokens,
        "overlap": settings.chunk_overlap,
    }


def cmd_stats(args: argparse.Namespace) -> int:
    report = ingest_corpus(load_sources(args.sources), raw_dir=args.raw_dir)
    print(report.summary())
    if report.excluded:
        print("\nExcluded:")
        for title, reason in report.excluded:
            print(f"  - {title}: {reason}")
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    report = ingest_corpus(load_sources(args.sources), raw_dir=args.raw_dir)
    if not report.chunks:
        print("No chunks produced (empty corpus? run download first).")
        return 0
    rng = random.Random(args.seed)
    sample = rng.sample(report.chunks, k=min(args.n, len(report.chunks)))
    print(f"{report.summary()}\n")
    for chunk in sample:
        meta = chunk.metadata
        print("=" * 78)
        print(f"chunk_id={chunk.chunk_id}  doc_id={chunk.doc_id}")
        print(
            f"title={meta.get('source_title')!r} page={meta.get('page')} "
            f"section={meta.get('section')!r} category={meta.get('category')!r}"
        )
        print("-" * 78)
        print(textwrap.fill(chunk.text, width=78))
        print()
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    from ..retrieval.vector_store import VectorStore

    report = ingest_corpus(load_sources(args.sources), raw_dir=args.raw_dir, **_chunking(args))
    store = VectorStore.from_settings(collection_name=args.collection)
    before = store.count()
    added = store.add_chunks(report.chunks)
    print(report.summary())
    print(f"indexed: +{added} new chunks (was {before}, now {store.count()} in collection)")
    print(f"distinct documents in collection: {store.document_count()}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Pack the vector store into one archive, for a host that has no volume.

    The index is not versioned and is not built in the image: it needs the
    downloaded corpus, which is not versioned either, so building it at image
    build time would mean fetching third-party sites and letting two builds of
    the same commit differ. It travels as an archive instead — produced here,
    published once, unpacked at deployment (``docker/entrypoint.sh``).
    """
    from ..config import get_settings

    source = Path(args.path) if args.path else get_settings().chroma_path
    if not source.is_dir():
        print(f"introuvable : {source}", file=sys.stderr)
        return 2

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # `arcname="."` keeps the archive relative to the store, so unpacking into
    # CHROMA_PATH restores it wherever that points.
    with tarfile.open(destination, "w:gz") as archive:
        archive.add(source, arcname=".")

    size = destination.stat().st_size
    print(f"{destination} — {size / 1_048_576:.1f} Mo depuis {source}")
    return 0


def cmd_contextualize(args: argparse.Namespace) -> int:
    """Contextual Retrieval (PRD §5.3.1) — parallel collection, never the production one."""
    from ..config import get_settings
    from ..generation.llm import build_backend
    from ..retrieval.vector_store import VectorStore
    from .contextualize import (
        MAX_CONTEXT_WORDS,
        ContextCache,
        contextual_collection_name,
        document_char_budget,
    )

    settings = get_settings()
    backend = build_backend(settings)
    budget = document_char_budget(backend)
    report = ingest_corpus(load_sources(args.sources), raw_dir=args.raw_dir, **_chunking(args))
    chunks = report.chunks[: args.limit] if args.limit else report.chunks
    print(report.summary())
    print(f"contextualizing {len(chunks)} chunks with {backend.name} …")

    from .contextualize import contextualize_chunks

    contextual, ctx_report = contextualize_chunks(
        chunks, report.documents, backend, cache=ContextCache(args.cache)
    )
    print(ctx_report.summary())
    for title in ctx_report.truncated_docs:
        print(
            f"  ! document truncated to {budget} chars — it does not fit the window of "
            f"{backend.name} (raise it, or switch to LLM_BACKEND=mistral): {title}"
        )
    if ctx_report.over_word_limit:
        longest = max(words for _, words in ctx_report.over_word_limit)
        print(
            f"  ! {len(ctx_report.over_word_limit)}/{ctx_report.total} contexts exceed the "
            f"{MAX_CONTEXT_WORDS}-word ceiling of the prompt (longest: {longest} words). "
            "Not truncated: the excess is reported, never silently absorbed."
        )
    for chunk_id, reason in ctx_report.failed[:5]:
        print(f"  ! failed {chunk_id}: {reason}")

    if args.dry_run:
        for chunk in contextual[: args.n]:
            print("=" * 78)
            print(textwrap.fill(str(chunk.metadata.get("context", "(no context)")), width=78))
            print("-" * 78)
            print(textwrap.fill(str(chunk.metadata.get("text_raw", chunk.text))[:400], width=78))
        print("\n(dry run — nothing indexed)")
        return 0

    name = args.collection or contextual_collection_name(settings.chroma_collection)
    store = VectorStore.from_settings(settings, collection_name=name)
    if args.reset and store.count():
        store.delete_collection()
        store = VectorStore.from_settings(settings, collection_name=name)
    added = store.add_chunks(contextual)
    print(f"indexed: +{added} new chunks in collection {name!r} (now {store.count()})")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from ..retrieval.vector_store import VectorStore

    store = VectorStore.from_settings(collection_name=args.collection)
    results = store.query(args.question, k=args.k)
    if not results:
        print("No results (empty collection? run `index` first).")
        return 0
    for rank, r in enumerate(results, start=1):
        meta = r.metadata
        print(f"\n#{rank}  score={r.score:.3f}  {meta.get('source_title')!r} "
              f"(page {meta.get('page')}, {meta.get('section')})")
        print("  " + r.text[:300].replace("\n", " "))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Corpus text carries accents and PDF private-use glyphs; the Windows console
    # defaults to cp1252 and would crash on printing them (same guard as
    # docs/build_concepts.py).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # non-reconfigurable stream (piped/captured)
            pass

    parser = argparse.ArgumentParser(prog="assistant_amu.ingestion", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_stats = sub.add_parser("stats", help="extract/clean/chunk the corpus, print counts")
    _add_common(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    p_dump = sub.add_parser("dump", help="print N random chunks with metadata")
    _add_common(p_dump)
    p_dump.add_argument("-n", type=int, default=5, help="number of chunks to show")
    p_dump.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    p_dump.set_defaults(func=cmd_dump)

    p_index = sub.add_parser("index", help="embed corpus chunks into ChromaDB (idempotent)")
    _add_common(p_index)
    _add_chunking(p_index)
    p_index.add_argument(
        "--collection", default=None, help="target collection (default: the production one)"
    )
    p_index.set_defaults(func=cmd_index)

    p_export = sub.add_parser("export", help="pack the vector store into one archive")
    p_export.add_argument(
        "--output", default="chroma_db.tar.gz", help="archive to write (default: chroma_db.tar.gz)"
    )
    p_export.add_argument(
        "--path", default=None, help="store to pack (default: CHROMA_PATH from the settings)"
    )
    p_export.set_defaults(func=cmd_export)

    p_ctx = sub.add_parser(
        "contextualize", help="build the Contextual Retrieval index (parallel collection)"
    )
    _add_common(p_ctx)
    _add_chunking(p_ctx)
    p_ctx.add_argument("--collection", default=None, help="target collection (default: <prod>_ctx)")
    p_ctx.add_argument("--cache", default=str(CACHE_PATH), help="path to the context cache (JSONL)")
    p_ctx.add_argument("--limit", type=int, default=None, help="contextualize only the first N chunks")
    p_ctx.add_argument("-n", type=int, default=3, help="chunks to show with --dry-run")
    p_ctx.add_argument("--dry-run", action="store_true", help="generate and print, index nothing")
    p_ctx.add_argument("--reset", action="store_true", help="drop the target collection first")
    p_ctx.set_defaults(func=cmd_contextualize)

    p_search = sub.add_parser("search", help="retrieve top-k chunks for a question")
    p_search.add_argument("question", help="the question to search for")
    p_search.add_argument("-k", type=int, default=5, help="number of chunks (1-10)")
    p_search.add_argument(
        "--collection", default=None, help="collection to search (default: the production one)"
    )
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
