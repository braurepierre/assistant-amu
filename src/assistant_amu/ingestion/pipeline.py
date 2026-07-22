"""End-to-end ingestion over the corpus: extract -> clean -> chunk (PRD §7.2).

Sources are resolved from ``sources.yaml`` (which carries the metadata and the
per-document extractor) to their downloaded files under ``corpus/raw/`` or a
local ``path:``. Scanned documents are excluded and logged, never OCR'd. Indexing
into ChromaDB is layered on in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import PROJECT_ROOT
from ..models import Chunk, Document, SourceDoc
from . import IngestionError
from .chunk import TokenCounter, chunk_document
from .clean import clean_document
from .download import RAW_DIR, target_filename
from .extract import ScannedDocumentError, extract


@dataclass
class IngestReport:
    processed: list[tuple[str, str, int]] = field(default_factory=list)  # (title, doc_id, n_chunks)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (title, reason)
    chunks: list[Chunk] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"documents processed: {len(self.processed)} | "
            f"excluded: {len(self.excluded)} | "
            f"chunks produced: {len(self.chunks)}"
        )


def resolve_path(source: SourceDoc, index: int, raw_dir: Path) -> Path | None:
    """Locate the file backing a source, or None if it is not present yet."""
    if source.path:
        local = Path(source.path)
        return local if local.is_absolute() else PROJECT_ROOT / local
    candidate = raw_dir / target_filename(source, index)
    return candidate if candidate.exists() else None


def ingest_document(
    path: Path, source: SourceDoc, *, count_tokens: TokenCounter | None = None, **chunk_kwargs
) -> tuple[Document, list[Chunk]]:
    """Extract, clean and chunk a single document."""
    doc = clean_document(extract(path, source))
    chunks = chunk_document(doc, count_tokens=count_tokens, **chunk_kwargs)
    return doc, chunks


def ingest_corpus(
    sources: list[SourceDoc],
    *,
    raw_dir: Path | str = RAW_DIR,
    count_tokens: TokenCounter | None = None,
    **chunk_kwargs,
) -> IngestReport:
    """Run the full pipeline over every source, collecting a report."""
    raw_dir = Path(raw_dir)
    report = IngestReport()
    for index, source in enumerate(sources):
        path = resolve_path(source, index, raw_dir)
        if path is None:
            report.excluded.append((source.title, "file not downloaded (run download first)"))
            continue
        try:
            doc, chunks = ingest_document(
                path, source, count_tokens=count_tokens, **chunk_kwargs
            )
        except ScannedDocumentError as exc:
            report.excluded.append((source.title, str(exc)))
            continue
        except IngestionError as exc:
            report.excluded.append((source.title, f"ingestion error: {exc}"))
            continue
        report.processed.append((source.title, doc.doc_id, len(chunks)))
        report.chunks.extend(chunks)
    return report
