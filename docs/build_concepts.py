"""Regenerate the STATS block of the pedagogical page from the real sources.

This keeps ``docs/concepts-assistant-amu.html`` in sync with the project without
hand-editing numbers in the HTML. It rewrites *only* the delimited block::

    /* STATS:START */ ... /* STATS:END */

Hand-authored sections are never touched, so adding a new rubric to the page and
regenerating the facts never conflict.

Sources of truth, by field:
  * ``k_default`` / ``embedding_model`` / backend model names -> read live from
    ``assistant_amu.config`` (so they can never drift from the code);
  * everything else (corpus counts, recall numbers, latencies, tests) -> read
    from ``docs/concepts.facts.yaml``, itself fed by the dated ``eval/reports/``;
  * ``updated`` -> today's date; ``commit`` -> ``git rev-parse --short HEAD``.

A warning is printed when the YAML disagrees with a value that config also
defines, so silent drift is caught rather than shipped.

Usage:
    python docs/build_concepts.py            # rewrite the page in place
    python docs/build_concepts.py --check    # exit 1 if the page is stale (CI-friendly)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

# Emit UTF-8 regardless of the console code page (Windows defaults to cp1252,
# which cannot encode accents or "✓" and would otherwise crash on print).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

DOCS_DIR = Path(__file__).resolve().parent
ROOT = DOCS_DIR.parent
HTML_PATH = DOCS_DIR / "concepts-assistant-amu.html"
FACTS_PATH = DOCS_DIR / "concepts.facts.yaml"

# Make the src-layout package importable without an editable install.
sys.path.insert(0, str(ROOT / "src"))

_BLOCK = re.compile(r"/\* STATS:START \*/.*?/\* STATS:END \*/", re.DOTALL)


def _load_settings():
    """Return validated settings, tolerating a mistral-without-key local .env.

    The page only needs retrieval/model defaults; those are backend-independent,
    so if validation trips on ``LLM_BACKEND=mistral`` without a key we retry with
    a backend that always validates rather than failing the build.
    """
    from assistant_amu.config import ConfigError, load_settings

    try:
        return load_settings()
    except ConfigError:
        os.environ["LLM_BACKEND"] = "ollama"
        return load_settings()


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:  # noqa: BLE001 - git absent or not a repo: degrade gracefully
        return "local"


def build_stats(today: str) -> dict:
    """Assemble the STATS object from config, facts.yaml and git."""
    facts = yaml.safe_load(FACTS_PATH.read_text(encoding="utf-8"))
    settings = _load_settings()

    stats = {
        "updated": today,
        "commit": _git_short_sha(),
        "corpus": facts["corpus"],
        "eval_questions": facts["eval_questions"],
        "k_default": settings.top_k,
        "embedding_model": settings.embedding_model,
        "tests": facts["tests"],
        "recall_at_5": facts["recall_at_5"],
        "recall_curve": facts["recall_curve"],
        "embedders": facts["embedders"],
        "rewrite_hard_recall5": facts["rewrite_hard_recall5"],
        "conversation": facts["conversation"],
        "chunk_hygiene": facts["chunk_hygiene"],
        "langchain_parity": facts["langchain_parity"],
        "backends": {
            "mistral": {"model": settings.mistral_model, **facts["backends"]["mistral"]},
            "ollama": {"model": f"{settings.ollama_model} 7B (CPU)", **facts["backends"]["ollama"]},
        },
    }

    # Drift detection: warn if facts.yaml restates a config-owned value differently.
    for key, code_value in (("k_default", settings.top_k), ("embedding_model", settings.embedding_model)):
        if key in facts and facts[key] != code_value:
            print(
                f"  ! dérive : concepts.facts.yaml {key}={facts[key]!r} "
                f"mais config.py dit {code_value!r} (config.py fait foi)",
                file=sys.stderr,
            )
    return stats


def render_block(stats: dict) -> str:
    payload = json.dumps(stats, ensure_ascii=False, indent=2)
    return f"/* STATS:START */\nvar STATS = {payload};\n/* STATS:END */"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the page is stale")
    args = parser.parse_args()

    if not HTML_PATH.exists():
        print(f"introuvable : {HTML_PATH}", file=sys.stderr)
        return 2

    html = HTML_PATH.read_text(encoding="utf-8")
    if not _BLOCK.search(html):
        print("marqueurs STATS:START / STATS:END absents de la page", file=sys.stderr)
        return 2

    # In --check mode, keep the current date/commit so only real content drift trips it.
    if args.check:
        current = _BLOCK.search(html).group(0)
        m = re.search(r'"updated":\s*"([^"]*)"', current)
        today = m.group(1) if m else date.today().isoformat()
    else:
        today = date.today().isoformat()

    new_block = render_block(build_stats(today))
    updated = _BLOCK.sub(lambda _: new_block, html, count=1)

    if args.check:
        stale = updated != html
        print("STALE : lancer `python docs/build_concepts.py`" if stale else "à jour ✓")
        return 1 if stale else 0

    if updated != html:
        HTML_PATH.write_text(updated, encoding="utf-8")
        print(f"STATS régénéré dans {HTML_PATH.name} ({today}).")
    else:
        print("STATS déjà à jour — rien à écrire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
