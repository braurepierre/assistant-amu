"""Build blind judging bundles for the before/after of AnythingLLM's reconfiguration.

The 2026-07-26 report attributes almost the whole gap to two defaults. Testing
that claim means judging the same product twice — as shipped, then reconfigured —
under one rubric, by judges who cannot tell which is which. A judge told that B
comes after a fix has every reason to find B better.

Blinding applied:
  - the two answers are presented as "Systeme A" / "Systeme B", assigned per
    question by a seeded shuffle; the key is written to a separate file;
  - passages are given as text only, with the ``<document_metadata>`` block
    stripped: it carries the ingestion date, which orders the two runs outright.

Not blinded, and stated as a limitation: the reconfigured run retrieves raw HTML
markup, since the five repaired pages were re-uploaded as HTML and the parser
keeps the tags. A judge therefore sees that one side's passages carry markup and
the other's do not. That is the object of the measurement and cannot be removed;
what it does not reveal is which side is the fix — a reader ignorant of this
repository is as likely to read markup as the defect being corrected.

Usage:
    python eval/configured_bundle.py --out-dir eval/reports/configured_rejudge
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports"
SEED = 20260727
METADATA_BLOCK = re.compile(r"<document_metadata>.*?</document_metadata>\s*", re.DOTALL)


def _load(path: Path):
    return json.load(open(path, encoding="utf-8"))


def _passages(texts: list[str]) -> str:
    cleaned = [METADATA_BLOCK.sub("", t or "").strip() for t in texts]
    cleaned = [t for t in cleaned if t]
    if not cleaned:
        return "(aucun extrait récupéré)"
    return "\n\n".join(f"[Extrait {i}]\n{t}" for i, t in enumerate(cleaned, start=1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(REPORTS / "configured_rejudge"))
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

    rng = random.Random(SEED)
    bundles, key = [], []

    for qid in sorted(after):
        if not after[qid]["answerable"]:
            continue  # the 4 out-of-corpus questions are scored by refusal, not grounding

        sides = [
            {
                "run": "defaut",
                "answer": before[qid]["answer"],
                "passages": [s.get("text", "") for s in (before[qid].get("sources") or [])],
            },
            {
                "run": "configure",
                "answer": after[qid]["answer"],
                "passages": [s.get("text", "") for s in (after[qid].get("sources") or [])],
            },
        ]
        rng.shuffle(sides)
        labels = ["A", "B"]

        bundles.append(
            {
                "id": qid,
                "question": after[qid]["question"],
                "systems": {
                    label: {"answer": side["answer"], "passages": _passages(side["passages"])}
                    for label, side in zip(labels, sides)
                },
            }
        )
        key.append({"id": qid, **{label: side["run"] for label, side in zip(labels, sides)}})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bundles.json").write_text(
        json.dumps(bundles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    flipped = sum(1 for k in key if k["A"] == "configure")
    print(f"[ok] {len(bundles)} dossiers -> {out_dir / 'bundles.json'}")
    print(f"     clé (à ne pas donner aux juges) -> {out_dir / 'key.json'}")
    print(f"     run configuré en position A sur {flipped}/{len(key)} questions (graine {SEED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
