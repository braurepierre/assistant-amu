"""Measure inter-judge agreement across the three blind judging passes.

Each question had been judged once, in both the 2026-07-26 series and the blind
one: a wrong verdict had nothing to catch it. Three passes now cover the same 16
questions, deliberately NOT by rerunning an identical prompt — that would measure
the model's determinism rather than whether a verdict survives a change of
conditions:

  pass 1  base   — the blind series of 2026-07-27
  pass 2  swap   — the A and B labels exchanged, everything else held fixed
  pass 3  shift  — the question list rotated before pairing, so no judge of this
                   pass sees the same pair of questions as in pass 1

Comparing pass 1 to pass 2 isolates **position bias**; the three-way tally gives
the stability of each verdict.

Usage:
    python eval/blind_rejudge_agreement.py
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports" / "blind_rejudge"
SYSTEMS = ("assistant-amu", "anythingllm")


def _load(path: Path):
    return json.load(open(path, encoding="utf-8"))


def deanonymise(verdicts: list[dict], key: list[dict]) -> dict[tuple[str, str], str]:
    """(question, system) -> verdict, using that pass's own A/B key."""
    mapping = {k["id"]: k for k in key}
    return {
        (v["id"], mapping[v["id"]][v["label"]]): v["verdict"]
        for v in verdicts
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reports-dir", default=str(REPORTS))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    d = Path(args.reports_dir)
    base_key, swap_key = _load(d / "key.json"), _load(d / "key_swap.json")
    passes = {
        "base": deanonymise(_load(d / "verdicts_blind.json"), base_key),
        "swap": deanonymise(_load(d / "verdicts_pass2_swap.json"), swap_key),
        "shift": deanonymise(_load(d / "verdicts_pass3_shift.json"), base_key),
    }

    items = sorted(passes["base"])
    unanimous, split = 0, []
    majority: dict[tuple[str, str], str] = {}

    for item in items:
        votes = [p[item] for p in passes.values()]
        counts = collections.Counter(votes)
        top, n = counts.most_common(1)[0]
        majority[item] = top
        if n == len(passes):
            unanimous += 1
        else:
            split.append((item, votes))

    print(f"Accord sur {unanimous}/{len(items)} couples (question, système)\n")

    for system in SYSTEMS:
        sub = [i for i in items if i[1] == system]
        agree = sum(1 for i in sub if len({p[i] for p in passes.values()}) == 1)
        spread = len({majority[i] for i in sub})
        print(f"  {system:14s} {agree}/{len(sub)} unanimes · {spread} catégorie(s) distincte(s)")

    print("\nBiais de position (passe base contre passe swap, tout le reste égal) :")
    moved = [i for i in items if passes["base"][i] != passes["swap"][i]]
    print(f"  {len(items) - len(moved)}/{len(items)} verdicts inchangés lorsque A et B sont échangés")
    for item in moved:
        print(f"    {item[0]} {item[1]} : {passes['base'][item]} -> {passes['swap'][item]}")

    if split:
        print("\nVerdicts partagés (2 voix contre 1) :")
        for item, votes in split:
            print(f"  {item[0]} {item[1]:14s} {votes} -> majorité : {majority[item]}")

    print("\nVerdict majoritaire par système :")
    for system in SYSTEMS:
        counts = collections.Counter(majority[i] for i in items if i[1] == system)
        line = " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        print(f"  {system:14s} {line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
