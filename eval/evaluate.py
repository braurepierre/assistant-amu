"""Reproducible evaluation harness (PRD §7.6).

Planned interface (Phase 5, F8):
    python eval/evaluate.py --mode retrieval --method all --k 5
    python eval/evaluate.py --mode end-to-end
    python eval/evaluate.py --mode conversation            # V2

Modes: retrieval (recall@k for semantic | bm25 | rrf | all), end-to-end (full
pipeline, normalised refusal check, manual faithfulness column), conversation
(V2). Writes dated Markdown reports to eval/reports/.

Not yet implemented — Phase 5.
"""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entrypoint — implemented in Phase 5 (§7.6, F8)."""
    raise SystemExit(
        "eval/evaluate.py is a Phase 5 deliverable (PRD §7.6) and is not "
        "implemented yet."
    )


if __name__ == "__main__":
    sys.exit(main())
