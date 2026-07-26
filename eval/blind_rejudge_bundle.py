"""Build blind judging bundles for the AnythingLLM comparison.

The 2026-07-26 verdicts were rendered by judges whose notes name both systems.
The 2026-07-27 verification measured the consequence: three cells wrong, all
against AnythingLLM. This script rebuilds the judging material with the system
identities removed, so the verdicts can be re-rendered and the two series
compared — the gap between them is the measure of the bias.

Blinding applied:
  - the two answers are presented as "Systeme A" / "Systeme B", assigned per
    question by a seeded shuffle; the key is written to a separate file;
  - retrieved passages are given as text only. Document titles are dropped:
    the two systems name their sources differently (clean titles on one side,
    upload filenames on the other), which would leak the identity.

Not blinded, and stated as a limitation: the answers themselves are verbatim,
since they are the object of the judgement. Their formatting differs markedly
(inline [S1] citation markers on one side, markdown headings and a trailing
source note on the other). A judge cannot map either style to a given product
without prior knowledge of this repository, but the two are distinguishable
from each other.

Usage:
    python eval/blind_rejudge_bundle.py --out-dir eval/reports/blind_rejudge
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports"
SEED = 20260727


def _load(path: Path):
    return json.load(open(path, encoding="utf-8"))


def _passages(texts: list[str]) -> str:
    if not texts:
        return "(aucun extrait récupéré)"
    return "\n\n".join(
        f"[Extrait {i}]\n{t.strip()}" for i, t in enumerate(texts, start=1) if t and t.strip()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(REPORTS / "blind_rejudge"))
    parser.add_argument("--reports-dir", default=str(REPORTS))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    reports = Path(args.reports_dir)
    allm = {r["id"]: r for r in _load(reports / "anythingllm_raw_answers.json")}
    amu_answers = {r["id"]: r for r in _load(reports / "assistant_amu_full_answers.json")}
    amu_sources = {r["id"]: r for r in _load(reports / "assistant_amu_retrieved_sources.json")}

    rng = random.Random(SEED)
    bundles, key = [], []

    for qid in sorted(amu_answers):
        if not amu_answers[qid]["answerable"]:
            continue  # the 4 out-of-corpus questions are scored by refusal, not grounding

        amu = {
            "system": "assistant-amu",
            "answer": amu_answers[qid]["answer"],
            "passages": [s["text"] for s in amu_sources[qid]["sources"]],
        }
        other = {
            "system": "anythingllm",
            "answer": allm[qid]["answer"],
            "passages": [s.get("text", "") for s in (allm[qid].get("sources") or [])],
        }

        pair = [amu, other]
        rng.shuffle(pair)
        labels = ["A", "B"]

        bundles.append(
            {
                "id": qid,
                "question": amu_answers[qid]["question"],
                "systems": {
                    label: {"answer": side["answer"], "passages": _passages(side["passages"])}
                    for label, side in zip(labels, pair)
                },
            }
        )
        key.append({"id": qid, **{label: side["system"] for label, side in zip(labels, pair)}})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bundles.json").write_text(
        json.dumps(bundles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    flipped = sum(1 for k in key if k["A"] == "anythingllm")
    print(f"[ok] {len(bundles)} dossiers -> {out_dir/'bundles.json'}")
    print(f"     clé (à ne pas donner aux juges) -> {out_dir/'key.json'}")
    print(f"     AnythingLLM en position A sur {flipped}/{len(key)} questions (graine {SEED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
