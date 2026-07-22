"""Chunk cleaned documents into retrieval units (PRD §7.2 / Phase 1, F2).

Hard cap of ``max_tokens`` per chunk *including* the ``passage: `` prefix
(e5-small silently truncates beyond 512 tokens, so the margin is deliberate).
Splits respect paragraph then sentence boundaries and never cut mid-sentence
unless a single sentence exceeds the budget. Consecutive blocks sharing the same
(page, section) are merged first so HTML paragraphs form well-sized chunks.

The token counter is injectable: production uses the embedding model's tokenizer
(:func:`default_token_counter`); tests pass a cheap word counter.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from functools import lru_cache

from ..models import Chunk, Document, TextBlock
from . import IngestionError

TokenCounter = Callable[[str], int]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
# Close a chunk early on a paragraph boundary once this full it keeps chunks
# aligned to paragraph starts without wasting space.
_PARAGRAPH_BREAK_FILL = 0.75


@lru_cache(maxsize=4)
def default_token_counter(model_name: str = "intfloat/multilingual-e5-small") -> TokenCounter:
    """Build a token counter from a Hugging Face tokenizer (cached per model)."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def count(text: str) -> int:
        return len(tokenizer.encode(text))

    return count


def chunk_document(
    doc: Document,
    *,
    max_tokens: int = 500,
    overlap: int = 50,
    count_tokens: TokenCounter | None = None,
    prefix: str = "passage: ",
) -> list[Chunk]:
    """Split a document into overlapping, metadata-carrying chunks."""
    count = count_tokens or default_token_counter()
    budget = max_tokens - count(prefix)
    if budget <= 0:
        raise IngestionError(
            f"max_tokens={max_tokens} too small for prefix {prefix!r} ({count(prefix)} tokens)."
        )
    if not 0 <= overlap < budget:
        raise IngestionError(f"overlap must satisfy 0 <= overlap < {budget}, got {overlap}.")

    chunks: list[Chunk] = []
    index = 0
    for page, section, text in _group_segments(doc.blocks):
        for piece in _split_segment(text, budget, overlap, count):
            chunks.append(_make_chunk(doc, piece, page, section, index))
            index += 1
    return chunks


def _group_segments(
    blocks: list[TextBlock],
) -> list[tuple[int | None, str | None, str]]:
    """Merge consecutive blocks sharing the same (page, section) into one text."""
    segments: list[tuple[int | None, str | None, str]] = []
    for block in blocks:
        key = (block.page, block.section)
        if segments and (segments[-1][0], segments[-1][1]) == key:
            page, section, text = segments[-1]
            segments[-1] = (page, section, f"{text}\n\n{block.text}")
        else:
            segments.append((block.page, block.section, block.text))
    return segments


def _split_segment(text: str, budget: int, overlap: int, count: TokenCounter) -> list[str]:
    """Greedily pack sentences into <= budget-token chunks with token overlap."""
    if count(text) <= budget:
        return [text.strip()] if text.strip() else []

    units = _split_into_units(text, budget, count)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for unit_text, starts_paragraph in units:
        unit_tokens = count(unit_text)
        would_overflow = current and current_tokens + unit_tokens > budget
        paragraph_break = (
            current and starts_paragraph and current_tokens >= _PARAGRAPH_BREAK_FILL * budget
        )
        if would_overflow or paragraph_break:
            chunks.append(" ".join(current).strip())
            current, current_tokens = _overlap_tail(current, overlap, count)
        current.append(unit_text)
        current_tokens += unit_tokens

    if current:
        chunks.append(" ".join(current).strip())
    return [c for c in chunks if c]


def _split_into_units(text: str, budget: int, count: TokenCounter) -> list[tuple[str, bool]]:
    """Sentence units flagged with whether they start a new paragraph.

    A sentence longer than the budget is hard-split on word boundaries as a last
    resort, so the hard cap always holds.
    """
    units: list[tuple[str, bool]] = []
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        first = True
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if count(sentence) > budget:
                for piece in _hard_split(sentence, budget, count):
                    units.append((piece, first))
                    first = False
            else:
                units.append((sentence, first))
                first = False
    return units


def _hard_split(sentence: str, budget: int, count: TokenCounter) -> list[str]:
    words = sentence.split()
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if count(" ".join(current)) > budget and len(current) > 1:
            current.pop()
            pieces.append(" ".join(current))
            current = [word]
    if current:
        pieces.append(" ".join(current))
    return pieces


def _overlap_tail(units: list[str], overlap: int, count: TokenCounter) -> tuple[list[str], int]:
    """Trailing units whose cumulative token count stays within ``overlap``."""
    if overlap <= 0:
        return [], 0
    tail: list[str] = []
    total = 0
    for unit in reversed(units):
        unit_tokens = count(unit)
        if total + unit_tokens > overlap:
            break
        tail.insert(0, unit)
        total += unit_tokens
    return tail, total


def _make_chunk(
    doc: Document, text: str, page: int | None, section: str | None, index: int
) -> Chunk:
    chunk_id = hashlib.sha256(f"{doc.doc_id}:{index}".encode()).hexdigest()[:16]
    metadata: dict[str, object] = {
        "source_title": doc.title,
        "source_url": doc.url,
        "page": page,
        "chunk_index": index,
        "category": doc.category,
        "section": section,
    }
    return Chunk(chunk_id=chunk_id, doc_id=doc.doc_id, text=text, metadata=metadata)
