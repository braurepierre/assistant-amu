"""Un-blind the before/after verdicts and tally them, refusals included.

Two things are counted, because they are measured differently:

  - the 16 answerable questions, by the blind jury's grounding verdicts
    (``configured_rejudge/verdicts.json``, keyed by ``key.json``);
  - the 4 out-of-corpus questions, mechanically, from the answers themselves.

The refusal criterion is deliberately split in two. A "net refusal" is the
configured refusal sentence and nothing else — what ``queryRefusalResponse`` is
supposed to produce. A "refusal on the substance" only states that the documents
do not hold the answer, then answers anyway from general knowledge; the
2026-07-26 report's correction read q18 that way, and the distinction is what
separates a product that declines from one that hedges.

Usage:
    python eval/configured_tally.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports"
REFUSAL = "Je ne trouve pas cette information dans les documents disponibles."

# Phrases by which an answer concedes that the corpus does not hold the answer.
DISCLAIMS = re.compile(
    r"ne contiennent pas|ne contient pas|n[e'] ?y a pas d[eu]? ?(?:mention|information)"
    r"|il n'y a pas d'information|ne mentionne(?:nt)? pas|je ne peux pas fournir"
    r"|aucune information|ne trouve pas cette information",
    re.IGNORECASE,
)

ORDER = (
    "correct_grounded",
    "partially_grounded",
    "ungrounded_plausible",
    "incorrect",
    "refused",
)


def _load(path: Path):
    return json.load(open(path, encoding="utf-8"))


def _refusal_class(answer: str) -> str:
    """``net`` | ``fond`` | ``aucun`` — how far the answer declines."""
    text = (answer or "").strip()
    if text == REFUSAL:
        return "net"
    if DISCLAIMS.search(text):
        return "fond"
    return "aucun"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default=str(REPORTS))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    reports = Path(args.reports_dir)
    before = {r["id"]: r for r in _load(reports / "anythingllm_raw_answers.json")}
    after = {r["id"]: r for r in _load(reports / "anythingllm_configured_answers.json")}
    key = {k["id"]: k for k in _load(reports / "configured_rejudge" / "key.json")}
    verdicts = _load(reports / "configured_rejudge" / "verdicts.json")

    # Un-blind: (question, A|B) -> run
    graded: dict[str, dict[str, str]] = {}
    for v in verdicts:
        run = key[v["id"]][v["system"]]
        graded.setdefault(v["id"], {})[run] = v["verdict"]

    print("## Questions répondables — verdicts du jury aveugle\n")
    print(f"{'id':<5} {'défaut':<22} {'configuré':<22} mouvement")
    moved = 0
    for qid in sorted(graded):
        d, c = graded[qid]["defaut"], graded[qid]["configure"]
        delta = ORDER.index(d) - ORDER.index(c) if "refused" not in (d, c) else None
        if d == c:
            move = "="
        else:
            moved += 1
            move = "meilleur" if (delta or 0) > 0 else "moins bon"
            if delta is None:
                move = "changement de nature"
        print(f"{qid:<5} {d:<22} {c:<22} {move}")

    print(f"\n{moved}/{len(graded)} questions changent de catégorie.\n")

    print(f"{'catégorie':<22} {'défaut':>8} {'configuré':>10}")
    for cat in ORDER:
        nd = sum(1 for g in graded.values() if g["defaut"] == cat)
        nc = sum(1 for g in graded.values() if g["configure"] == cat)
        print(f"{cat:<22} {nd:>8} {nc:>10}")

    print("\n## Questions hors-corpus — refus\n")
    print(f"{'id':<5} {'défaut':<8} {'configuré':<10} question")
    tally = {"defaut": {}, "configure": {}}
    for qid in sorted(after):
        if after[qid]["answerable"]:
            continue
        d = _refusal_class(before[qid]["answer"])
        c = _refusal_class(after[qid]["answer"])
        tally["defaut"][d] = tally["defaut"].get(d, 0) + 1
        tally["configure"][c] = tally["configure"].get(c, 0) + 1
        print(f"{qid:<5} {d:<8} {c:<10} {after[qid]['question']}")
    for label in ("net", "fond", "aucun"):
        print(
            f"\n{label:<6} défaut : {tally['defaut'].get(label, 0)}/4"
            f"   configuré : {tally['configure'].get(label, 0)}/4"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
