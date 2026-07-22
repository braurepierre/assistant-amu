"""Chunk cleaned text and attach metadata.

Hard cap <= 500 tokens per chunk including the ``passage: `` prefix (e5-small
silently truncates beyond 512 tokens), ~50 overlap, prefer paragraph boundaries.
Each chunk carries {source_title, source_url, page, chunk_index, category, section}.
Stable chunk id (source + index); document id = hash of extracted content (used
for dedup and the /ingest 409). PRD §7.2 / Phase 1 (F2).

Not yet implemented — Phase 1.
"""

from __future__ import annotations

# TODO(Phase 1): boundary-aware chunking + metadata (F2).
