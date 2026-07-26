"""Recover the passages assistant-amu retrieved for each comparison question.

`assistant_amu_full_answers.json` stores only a source *count*, so the grounding
verdicts of the AnythingLLM comparison could not be checked against what the
pipeline actually read — while the AnythingLLM side stores full passage text.
This script closes that asymmetry without regenerating a single answer.

It costs nothing and changes nothing: with no history and rewrite="raw", the
retrieval query is the question verbatim (rag.py:154-158), so `store.query()`
reproduces exactly the chunks the stored answers were built from. No LLM call is
made, and the production collection is opened read-only.

Note on refusals: `RagResult` clears `sources` when the answer is a refusal (F6),
which is why q02 and q16 report zero sources while five chunks were in fact
retrieved. Those five are recovered here too — they are what shows whether the
refusal was a retrieval failure or a generation one.

Usage:
    python eval/serialize_retrieved_sources.py --out eval/reports/assistant_amu_retrieved_sources.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import load_questions
from assistant_amu.retrieval.vector_store import VectorStore

DEFAULT_QUESTIONS = PROJECT_ROOT / "eval" / "questions.yaml"
DEFAULT_OUT = PROJECT_ROOT / "eval" / "reports" / "assistant_amu_retrieved_sources.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("-k", type=int, default=5, help="retrieval depth (comparison used 5)")
    parser.add_argument("--limit", type=int, default=20, help="first N questions (comparison used 20)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    settings = get_settings()
    store = VectorStore.from_settings(settings)
    questions = load_questions(Path(args.questions))[: args.limit]

    records = []
    for q in questions:
        chunks = store.query(q.question, k=args.k)
        records.append(
            {
                "id": q.id,
                "question": q.question,
                "answerable": q.answerable,
                "n_retrieved": len(chunks),
                "sources": [
                    {
                        "rank": rank,
                        "score": round(c.score, 4),
                        "title": c.metadata.get("source_title"),
                        "page": c.metadata.get("page"),
                        "section": c.metadata.get("section"),
                        "text": c.text,
                    }
                    for rank, c in enumerate(chunks, start=1)
                ],
            }
        )
        print(f"  {q.id}: {len(chunks)} extrait(s)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] {len(records)} questions, collection {settings.chroma_collection!r} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
