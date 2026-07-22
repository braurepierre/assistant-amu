"""Extract raw text from PDF/HTML source documents (PRD §7.2 / Phase 1, F2).

PDF: pdfplumber page by page; per-document Docling escalation (``extractor: docling``)
for complex layouts; scanned/no-text-layer documents raise
:class:`ScannedDocumentError` so the caller excludes and logs them (no OCR).
HTML: BeautifulSoup, main content only, heading hierarchy kept as ``section``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup, Tag

from ..models import Document, SourceDoc, TextBlock
from . import IngestionError

# Below this many non-whitespace characters a PDF is considered image-only.
_SCANNED_CHAR_THRESHOLD = 20

# HTML elements that never carry primary content.
_HTML_NOISE = ("nav", "footer", "header", "script", "style", "aside", "form", "noscript")


class ScannedDocumentError(IngestionError):
    """Raised when a PDF has no usable text layer (scanned) — excluded, not OCR'd."""


def compute_doc_id(blocks: list[TextBlock]) -> str:
    """Stable content hash used for dedup and the /ingest 409 (PRD §7.2)."""
    joined = "\n".join(block.text for block in blocks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def extract(path: Path | str, source: SourceDoc) -> Document:
    """Extract a source file into a :class:`Document`, dispatching by type.

    Raises:
        ScannedDocumentError: PDF without a text layer.
        IngestionError: unsupported type or unreadable file.
    """
    path = Path(path)
    if not path.exists():
        raise IngestionError(f"File not found: {path}")

    if source.type == "pdf":
        if source.extractor == "docling":
            blocks = _extract_pdf_docling(path)
        else:
            blocks = _extract_pdf(path)
    elif source.type == "html":
        blocks = _extract_html(path)
    else:
        raise IngestionError(f"Unsupported source type: {source.type!r}")

    if sum(len(b.text.strip()) for b in blocks) < _SCANNED_CHAR_THRESHOLD:
        raise ScannedDocumentError(
            f"{path.name}: no usable text layer (scanned?). Excluded — no OCR (§7.2)."
        )

    return Document(
        doc_id=compute_doc_id(blocks),
        title=source.title,
        category=source.category,
        url=source.url,
        blocks=blocks,
    )


def _extract_pdf(path: Path) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                blocks.append(TextBlock(text=text, page=page_number, section=None))
    return blocks


def _extract_pdf_docling(path: Path) -> list[TextBlock]:
    """Docling escalation for complex PDFs (PRD §7.2). Docling is an optional dep."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise IngestionError(
            f"{path.name} requests 'extractor: docling' but docling is not installed. "
            "Install it with: pip install '.[docling]'."
        ) from exc

    result = DocumentConverter().convert(str(path))
    markdown = result.document.export_to_markdown()
    # Docling preserves structure in Markdown; keep it as one block per page break.
    return [TextBlock(text=part, page=None, section=None)
            for part in markdown.split("\f") if part.strip()]


def _extract_html(path: Path) -> list[TextBlock]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for tag in soup(_HTML_NOISE):
        tag.decompose()

    root: Tag = soup.find("main") or soup.find("article") or soup.body or soup
    heading_stack: dict[int, str] = {}
    blocks: list[TextBlock] = []

    for element in root.find_all(["h1", "h2", "h3", "p", "li"]):
        name = element.name
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        if name in ("h1", "h2", "h3"):
            level = int(name[1])
            heading_stack[level] = text
            # Drop deeper headings once a higher-level one changes.
            for deeper in [lvl for lvl in heading_stack if lvl > level]:
                del heading_stack[deeper]
            continue
        section = " > ".join(heading_stack[lvl] for lvl in sorted(heading_stack)) or None
        blocks.append(TextBlock(text=text, page=None, section=section))
    return blocks
