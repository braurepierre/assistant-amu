"""Embedding wrapper (sentence-transformers).

Owns a {model -> prefixes} table and applies the right prefix set per model
family: E5 requires ``"query: "`` / ``"passage: "`` (piège n°1), CamemBERT gets
no prefix (would pollute its inputs). No other module calls the embedding model
directly. PRD §7.3 / Phase 2.

Not yet implemented — Phase 2.
"""

from __future__ import annotations

# TODO(Phase 2): e5/camembert embedder with per-family prefixes (§7.3).
