"""Shared data structures for the ingestion and retrieval pipelines.

These are internal implementation types (not API contracts — those live in
``api/schemas.py`` as Pydantic models). Kept in one place so ``extract`` ->
``clean`` -> ``chunk`` -> indexing all speak the same vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Categories accepted in corpus/sources.yaml (PRD §7.1). Extra values are allowed
# but warned about, so the taxonomy stays loose without silently masking typos.
KNOWN_CATEGORIES: tuple[str, ...] = (
    "reglement-scolarite",
    "guide-etudiant",
    "composante",
)

SUPPORTED_TYPES: tuple[str, ...] = ("pdf", "html")


@dataclass(frozen=True, slots=True)
class SourceDoc:
    """One entry from ``corpus/sources.yaml`` (PRD §7.1)."""

    title: str
    category: str | None  # required in sources.yaml; may be None for /ingest uploads
    type: str  # "pdf" | "html"
    url: str | None = None
    path: str | None = None
    extractor: str | None = None  # e.g. "docling" — per-document PDF escalation


@dataclass(frozen=True, slots=True)
class TextBlock:
    """A contiguous span of extracted text with its provenance.

    ``page`` is the 1-based PDF page (``None`` for HTML); ``section`` is the
    heading path traversed to reach the text (e.g. "Titre I > Article 12"),
    used for sourced answers and as a prerequisite for Contextual Retrieval.
    """

    text: str
    page: int | None = None
    section: str | None = None


@dataclass(frozen=True, slots=True)
class Document:
    """A fully extracted (and optionally cleaned) source document."""

    doc_id: str  # hash of the extracted content — dedup key (PRD §7.2)
    title: str
    category: str | None
    url: str | None
    blocks: list[TextBlock] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The document's blocks joined into a single string."""
        return "\n\n".join(block.text for block in self.blocks)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrieval unit: a bounded span of text plus indexing metadata."""

    chunk_id: str  # stable hash(doc_id + chunk_index)
    doc_id: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)
    # metadata keys: source_title, source_url, page, chunk_index, category, section


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned by retrieval, with its relevance score.

    ``score`` is cosine similarity (= 1 - distance), in [0, 1], higher = more
    relevant (PRD §7.5). ChromaDB returns distances; the store converts them.
    """

    chunk_id: str
    doc_id: str
    text: str
    metadata: dict[str, object]
    score: float
