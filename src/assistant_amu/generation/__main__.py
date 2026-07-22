"""Generation CLI (PRD Phase 3): ``python -m assistant_amu.generation ask "..."``.

Runs the full single-turn pipeline (retrieval + generation) from the command
line, against the configured LLM backend and the indexed corpus.
"""

from __future__ import annotations

import argparse
import sys

from .llm import LLMBackendError
from .rag import RagPipeline


def cmd_ask(args: argparse.Namespace) -> int:
    pipeline = RagPipeline.from_settings()
    try:
        result = pipeline.answer(args.question, k=args.k)
    except LLMBackendError as exc:
        print(f"LLM backend unavailable ({exc.cause}): {exc}", file=sys.stderr)
        return 2
    print(f"\n[{result.model}] retrieved {result.retrieved_chunks} chunk(s)\n")
    print(result.answer)
    if result.sources:
        print("\nSources:")
        for i, source in enumerate(result.sources, start=1):
            meta = source.metadata
            print(f"  [S{i}] {meta.get('source_title')} (page {meta.get('page')}) "
                  f"score={source.score:.3f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assistant_amu.generation", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_ask = sub.add_parser("ask", help="ask a question end to end")
    p_ask.add_argument("question")
    p_ask.add_argument("-k", type=int, default=5, help="number of chunks to retrieve (1-10)")
    p_ask.set_defaults(func=cmd_ask)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
