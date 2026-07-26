"""Render one self-contained blind judging brief per judge.

Each judge receives its own file and nothing else, so no judge can reach
`key.json`. Two questions per judge, matching the design of the 2026-07-26 jury
(8 judges, a pair of questions each).

Usage:
    python eval/blind_rejudge_prompts.py --bundles eval/reports/blind_rejudge/bundles.json --out-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PER_JUDGE = 2

RUBRIC = """\
## Ce qui t'est demandé

Pour CHAQUE système (A et B) de CHAQUE question, rends un verdict sur le seul
critère de l'**ancrage** : ce que la réponse affirme est-il soutenu par les
extraits qui ont été fournis à ce système-là ?

Chaque système a reçu ses propres extraits. Juge chaque réponse **contre ses
propres extraits**, jamais contre ceux de l'autre. Il est normal et attendu que
les deux jeux d'extraits diffèrent.

## Barème — une seule catégorie par réponse

- `correct_grounded` — répond à la question, et chaque affirmation substantielle
  est soutenue par les extraits fournis à ce système.
- `partially_grounded` — le cœur de la réponse est soutenu par les extraits,
  mais elle ajoute des affirmations substantielles qui n'y figurent pas.
- `ungrounded_plausible` — plausible mais non soutenue : les extraits ne la
  portent pas, la réponse repose sur des connaissances générales.
- `incorrect` — contient au moins une affirmation substantielle qui **contredit**
  les extraits fournis, ou un fait vérifiablement faux.
- `refused` — le système décline de répondre. Cette catégorie s'applique dès lors
  que le système ne répond pas, **quelle qu'en soit la raison** : ne la confonds
  pas avec `incorrect`, qui suppose une affirmation fausse.

Pour une réponse `refused` uniquement, renseigne aussi `answer_was_available` :
les extraits fournis à CE système contenaient-ils de quoi répondre ? (true/false)

## Règles

1. **Ne cherche pas à identifier quel produit a écrit quelle réponse.** Les deux
   styles de rédaction diffèrent ; cela ne t'apprend rien sur leur qualité et ne
   doit pas peser sur ton verdict. Ne le mentionne pas dans tes notes.
2. Une réponse longue et bien mise en forme n'est pas mieux ancrée pour autant.
3. Cite le passage décisif à l'appui de chaque verdict (`key_evidence`) : la
   phrase de l'extrait qui soutient, ou celle de la réponse qui contredit.
4. Si tu hésites entre deux catégories, retiens la moins sévère et dis-le.

## Format de sortie

Réponds UNIQUEMENT par un objet JSON, sans texte autour :

```json
{"verdicts": [
  {"id": "<id>", "system": "A", "verdict": "<catégorie>",
   "answer_was_available": null, "key_evidence": "<citation>",
   "justification": "<une ou deux phrases>"},
  {"id": "<id>", "system": "B", "verdict": "...", "answer_was_available": null,
   "key_evidence": "...", "justification": "..."}
]}
```
"""


def render(bundle: dict) -> str:
    parts = [f"# Question {bundle['id']}\n", f"**Question posée :** {bundle['question']}\n"]
    for label in ("A", "B"):
        side = bundle["systems"][label]
        parts.append(f"\n---\n\n## Système {label}\n")
        parts.append(f"### Extraits fournis au système {label}\n\n{side['passages']}\n")
        parts.append(f"### Réponse du système {label}\n\n{side['answer']}\n")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--shift",
        type=int,
        default=0,
        help="rotate the question list before pairing, so no judge of this pass sees "
        "the same pair as in another — pairing is a shared context that would "
        "correlate two verdicts meant to be independent",
    )
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    bundles = json.load(open(args.bundles, encoding="utf-8"))
    if args.shift:
        n = args.shift % len(bundles)
        bundles = bundles[n:] + bundles[:n]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for n, start in enumerate(range(0, len(bundles), PER_JUDGE), start=1):
        chunk = bundles[start : start + PER_JUDGE]
        body = "\n\n".join(render(b) for b in chunk)
        ids = ", ".join(b["id"] for b in chunk)
        text = (
            f"# Dossier de jugement à l'aveugle — juge {n:02d}\n\n"
            f"Questions à juger : **{ids}**\n\n{RUBRIC}\n\n---\n\n{body}\n"
        )
        path = out_dir / f"juge_{n:02d}.md"
        path.write_text(text, encoding="utf-8")
        written.append((path.name, ids))

    for name, ids in written:
        print(f"  {name}: {ids}")
    print(f"\n[ok] {len(written)} dossiers -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
