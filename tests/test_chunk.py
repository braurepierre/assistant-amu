"""Tests for chunking: hard cap, overlap, boundaries, metadata (PRD §7.2)."""

from __future__ import annotations

import pytest

from assistant_amu.ingestion.chunk import chunk_document
from assistant_amu.models import Document, TextBlock

PREFIX = "passage: "  # 1 word under the word_counter


def _doc(blocks):
    return Document(doc_id="doc1", title="Reglement", category="reglement-scolarite",
                    url="https://amu.fr/x", blocks=blocks)


def test_short_document_single_chunk(word_counter):
    doc = _doc([TextBlock(text="Une phrase courte.", page=1)])
    chunks = chunk_document(doc, max_tokens=50, overlap=5, count_tokens=word_counter)
    assert len(chunks) == 1
    meta = chunks[0].metadata
    assert meta["source_title"] == "Reglement"
    assert meta["source_url"] == "https://amu.fr/x"
    assert meta["page"] == 1
    assert meta["chunk_index"] == 0
    assert meta["category"] == "reglement-scolarite"


def test_hard_cap_respected(word_counter):
    # 12 sentences of 5 words each = 60 words, budget = 20 - 1(prefix) = 19 words.
    text = " ".join(f"Phrase numero {i} bien remplie." for i in range(12))
    chunks = chunk_document(
        _doc([TextBlock(text=text, page=1)]),
        max_tokens=20, overlap=4, count_tokens=word_counter,
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert word_counter(PREFIX + chunk.text) <= 20


def test_no_mid_sentence_split(word_counter):
    text = " ".join(f"Ceci est la phrase {i} du texte." for i in range(10))
    chunks = chunk_document(
        _doc([TextBlock(text=text, page=1)]),
        max_tokens=25, overlap=5, count_tokens=word_counter,
    )
    # Every sentence is short enough, so no chunk should end mid-sentence.
    for chunk in chunks:
        assert chunk.text.rstrip().endswith((".", "!", "?"))


def test_overlap_present(word_counter):
    text = " ".join(f"Phrase alpha {i} contenu suffisant." for i in range(12))
    chunks = chunk_document(
        _doc([TextBlock(text=text, page=1)]),
        max_tokens=20, overlap=6, count_tokens=word_counter,
    )
    # Consecutive chunks share at least one trailing/leading word (overlap).
    first_words = set(chunks[1].text.split())
    last_words = set(chunks[0].text.split())
    assert first_words & last_words


def test_segments_not_merged_across_pages(word_counter):
    blocks = [
        TextBlock(text="Contenu page une.", page=1),
        TextBlock(text="Contenu page deux.", page=2),
    ]
    chunks = chunk_document(_doc(blocks), max_tokens=50, overlap=5, count_tokens=word_counter)
    assert len(chunks) == 2
    assert {c.metadata["page"] for c in chunks} == {1, 2}


def test_same_section_blocks_merged(word_counter):
    blocks = [
        TextBlock(text="Premier paragraphe.", page=None, section="A"),
        TextBlock(text="Deuxieme paragraphe.", page=None, section="A"),
    ]
    chunks = chunk_document(_doc(blocks), max_tokens=50, overlap=5, count_tokens=word_counter)
    assert len(chunks) == 1
    assert "Premier" in chunks[0].text and "Deuxieme" in chunks[0].text


def test_chunk_ids_stable_and_unique(word_counter):
    text = " ".join(f"Phrase {i} de test remplie." for i in range(10))
    doc = _doc([TextBlock(text=text, page=1)])
    ids1 = [c.chunk_id for c in chunk_document(doc, max_tokens=20, overlap=4, count_tokens=word_counter)]
    ids2 = [c.chunk_id for c in chunk_document(doc, max_tokens=20, overlap=4, count_tokens=word_counter)]
    assert ids1 == ids2  # stable
    assert len(set(ids1)) == len(ids1)  # unique


def test_invalid_overlap_raises(word_counter):
    with pytest.raises(Exception):
        chunk_document(_doc([TextBlock(text="x.", page=1)]),
                       max_tokens=20, overlap=100, count_tokens=word_counter)
