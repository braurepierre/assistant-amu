"""RAG query pipeline (PRD §7.4).

Assembles the user message (XML-tagged sources first, question last), calls the
selected backend, and returns the answer plus cited sources. V2 adds query
condensation (§7.7) — not before V1 F1-F9 are validated (§11.3).

Not yet implemented — Phase 3.
"""

from __future__ import annotations

# TODO(Phase 3): prompt assembly + query pipeline (§7.4, F6).
