"""Extract raw text from PDF/HTML source documents.

PDF: pdfplumber by default, Docling escalation per document (``extractor: docling``),
scanned/no-text-layer documents excluded and logged (no OCR — non-objective).
HTML: BeautifulSoup, main content only, heading hierarchy kept as ``section``
metadata. PRD §7.2 / Phase 1 (F2).

Not yet implemented — Phase 1.
"""

from __future__ import annotations

# TODO(Phase 1): pdfplumber / Docling / BeautifulSoup extraction (F2).
