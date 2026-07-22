"""Ingestion CLI (PRD F2/F3/F4): ``python -m assistant_amu.ingestion <command>``.

Commands:
  stats   Run extract -> clean -> chunk over the corpus and print counts.
  dump    Print N random chunks with metadata for visual inspection.
  index   Embed the corpus chunks into ChromaDB (idempotent; F3, dedup F2).
  search  Retrieve the top-k chunks for a question (manual relevance check, F4).
"""

from __future__ import annotations

import argparse
import random
import sys
import textwrap

from .download import RAW_DIR, SOURCES_YAML, load_sources
from .pipeline import ingest_corpus


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", default=str(SOURCES_YAML))
    parser.add_argument("--raw-dir", default=str(RAW_DIR))


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

    report = ingest_corpus(load_sources(args.sources), raw_dir=args.raw_dir)
    store = VectorStore.from_settings()
    before = store.count()
    added = store.add_chunks(report.chunks)
    print(report.summary())
    print(f"indexed: +{added} new chunks (was {before}, now {store.count()} in collection)")
    print(f"distinct documents in collection: {store.document_count()}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from ..retrieval.vector_store import VectorStore

    results = VectorStore.from_settings().query(args.question, k=args.k)
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
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="retrieve top-k chunks for a question")
    p_search.add_argument("question", help="the question to search for")
    p_search.add_argument("-k", type=int, default=5, help="number of chunks (1-10)")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
