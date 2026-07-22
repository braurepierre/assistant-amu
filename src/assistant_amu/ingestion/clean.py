"""Clean extracted text (PRD §7.2 / Phase 1).

Remove repeated headers/footers (short lines recurring on >= 3 pages), drop
table-of-contents lines (dot-leader + page-number heuristic), normalise
whitespace and blank runs. Provenance (page, section) is preserved; the
document id is kept from extraction so a source keeps its identity.
"""

from __future__ import annotations

import re
from collections import Counter

from ..models import Document, TextBlock

_DOT_LEADER = re.compile(r"\.{4,}\s*\d+\s*$")  # e.g. "Article 3 .......... 12"
_MULTISPACE = re.compile(r"[ \t]+")
_MULTINEWLINE = re.compile(r"\n{3,}")
_BOILERPLATE_MAX_LEN = 80  # headers/footers are short
_MIN_REPEAT_PAGES = 3


def clean_document(doc: Document) -> Document:
    """Return a cleaned copy of ``doc`` (same id, same provenance)."""
    boilerplate = _find_boilerplate(doc.blocks)
    cleaned: list[TextBlock] = []
    for block in doc.blocks:
        kept_lines = [
            line
            for line in block.text.split("\n")
            if not _drop_line(line, boilerplate)
        ]
        text = _normalize_whitespace("\n".join(kept_lines))
        if text:
            cleaned.append(TextBlock(text=text, page=block.page, section=block.section))
    return Document(
        doc_id=doc.doc_id,
        title=doc.title,
        category=doc.category,
        url=doc.url,
        blocks=cleaned,
    )


def _drop_line(line: str, boilerplate: set[str]) -> bool:
    stripped = line.strip()
    if not stripped:
        return False  # keep blanks — they mark paragraph boundaries for chunking
    return stripped in boilerplate or bool(_DOT_LEADER.search(stripped))


def _find_boilerplate(blocks: list[TextBlock]) -> set[str]:
    """Short lines appearing on >= _MIN_REPEAT_PAGES distinct blocks (pages)."""
    counter: Counter[str] = Counter()
    for block in blocks:
        unique_short_lines = {
            line.strip()
            for line in block.text.split("\n")
            if line.strip() and len(line.strip()) <= _BOILERPLATE_MAX_LEN
        }
        counter.update(unique_short_lines)
    return {line for line, count in counter.items() if count >= _MIN_REPEAT_PAGES}


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_MULTISPACE.sub(" ", line).strip() for line in text.split("\n")]
    return _MULTINEWLINE.sub("\n\n", "\n".join(lines)).strip()
