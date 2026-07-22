"""Ingestion pipeline: download -> extract -> clean -> chunk (PRD §7.1-§7.2)."""

from __future__ import annotations


class IngestionError(RuntimeError):
    """Raised on an unrecoverable ingestion problem (bad source, parse failure).

    Per-item failures during a batch download are *not* raised — they are
    collected and reported so one bad URL never aborts the lot (PRD §7.1).
    """


__all__ = ["IngestionError"]
