"""Tests for the ChromaDB store: cosine, dedup, scoring (PRD §7.3, §7.5).

Uses a deterministic fake embedder so no model is downloaded and rankings are
predictable.
"""

from __future__ import annotations

import pytest

from assistant_amu.models import Chunk
from assistant_amu.retrieval.vector_store import VectorStore

_VOCAB = ("cesure", "mcc", "cvec")


class FakeEmbedder:
    """Maps text to a 3-d bag-of-keywords vector (cosine-meaningful)."""

    def _vec(self, text: str) -> list[float]:
        low = text.lower()
        return [float(low.count(word)) for word in _VOCAB]

    def embed_passages(self, texts):
        return [self._vec(t) for t in texts]

    def embed_queries(self, texts):
        return [self._vec(t) for t in texts]


def _chunk(chunk_id, doc_id, text, **meta):
    base = {"source_title": "Doc", "source_url": "u", "page": 1,
            "chunk_index": 0, "category": "composante", "section": "S"}
    base.update(meta)
    return Chunk(chunk_id=chunk_id, doc_id=doc_id, text=text, metadata=base)


@pytest.fixture
def store(tmp_path):
    return VectorStore(path=tmp_path, collection_name="test_amu", embedder=FakeEmbedder())


@pytest.fixture
def chunks():
    return [
        _chunk("c1", "d1", "cesure cesure cesure suspension des etudes"),
        _chunk("c2", "d2", "mcc mcc controle des connaissances"),
        _chunk("c3", "d3", "cvec cvec contribution vie etudiante", page=None, section=None,
               source_url=None),
    ]


def test_collection_uses_cosine(store):
    assert store._collection.metadata.get("hnsw:space") == "cosine"


def test_add_and_count(store, chunks):
    assert store.add_chunks(chunks) == 3
    assert store.count() == 3
    assert store.document_count() == 3


def test_reindex_adds_no_duplicates(store, chunks):
    store.add_chunks(chunks)
    assert store.add_chunks(chunks) == 0  # F2: rerun adds 0
    assert store.count() == 3


def test_query_ranks_by_similarity(store, chunks):
    store.add_chunks(chunks)
    results = store.query("cesure interruption des etudes", k=3)
    assert results[0].chunk_id == "c1"
    assert results[0].score > results[-1].score
    assert 0.0 <= results[0].score <= 1.0


def test_has_document(store, chunks):
    store.add_chunks(chunks)
    assert store.has_document("d1")
    assert not store.has_document("does-not-exist")


def test_none_metadata_sanitized(store, chunks):
    store.add_chunks(chunks)
    results = store.query("cvec contribution", k=1)
    # page/section were None on c3 and must have been dropped, not stored as None.
    assert "page" not in results[0].metadata or results[0].metadata["page"] is not None


def test_query_empty_collection_returns_empty(store):
    assert store.query("anything", k=5) == []
