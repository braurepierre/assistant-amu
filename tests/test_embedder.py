"""Tests for the embedding wrapper and per-family prefixes (PRD §7.3, piège n°1)."""

from __future__ import annotations

import numpy as np

from assistant_amu.retrieval.embedder import Embedder, prefixes_for


class RecordingModel:
    """Fake SentenceTransformer that records the exact strings it is asked to encode."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, texts, **kwargs):
        self.seen.extend(texts)
        return np.zeros((len(texts), 3), dtype=float)


def test_prefixes_e5():
    p = prefixes_for("intfloat/multilingual-e5-small")
    assert p.query == "query: " and p.passage == "passage: "


def test_prefixes_camembert_none():
    p = prefixes_for("dangvantuan/sentence-camembert-base")
    assert p.query == "" and p.passage == ""


def test_e5_prefixes_applied():
    model = RecordingModel()
    emb = Embedder("intfloat/multilingual-e5-small", model=model)
    emb.embed_passages(["texte du chunk"])
    emb.embed_queries(["ma question"])
    assert model.seen == ["passage: texte du chunk", "query: ma question"]


def test_camembert_no_prefix_applied():
    model = RecordingModel()
    emb = Embedder("dangvantuan/sentence-camembert-base", model=model)
    emb.embed_passages(["texte"])
    emb.embed_queries(["question"])
    assert model.seen == ["texte", "question"]  # prefixes would skew the Phase 5 comparison


def test_encode_returns_plain_lists():
    emb = Embedder("intfloat/multilingual-e5-small", model=RecordingModel())
    vectors = emb.embed_passages(["a", "b"])
    assert vectors == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
