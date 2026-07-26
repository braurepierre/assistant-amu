"""Tests for the strict-counting precaution of the Contextual Retrieval experiment.

This precaution is what makes the experiment's numbers mean anything: retrieval
runs on the contextualised text, but the hit condition is evaluated on the
ORIGINAL one. Without it, a generated context sentence that happens to name the
subject of its chunk would satisfy the expected keywords on its own, and the
measurement would credit the method with retrieval wins it never produced.

It lived in ``eval/contextual_retrieval_experiment.py``, which no test reaches,
while the ingestion half (writing ``text_raw``) was covered three times over. A
regression here would have silently inverted the published conclusions.
"""

from __future__ import annotations

from assistant_amu.evaluation import RawTextRetriever, chunk_matches, with_raw_text
from assistant_amu.models import RetrievedChunk

RAW = "L'article 12 précise que la demande doit être déposée avant le 31 mars."
CONTEXT = "Règlement des études, partie « césure » : conditions de dépôt du dossier."


def chunk(text: str, *, raw: str | None = None, chunk_id: str = "c1") -> RetrievedChunk:
    metadata: dict = {"source_title": "Règlement des études"}
    if raw is not None:
        metadata["text_raw"] = raw
    return RetrievedChunk(chunk_id, "d1", text, metadata, 0.9)


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = chunks

    def rank(self, question: str, depth: int) -> list[RetrievedChunk]:
        return self._chunks[:depth]


def test_with_raw_text_restores_the_pre_contextualisation_text():
    contextualised = chunk(f"{CONTEXT}\n\n{RAW}", raw=RAW)

    assert with_raw_text(contextualised).text == RAW


def test_with_raw_text_leaves_a_chunk_without_raw_text_untouched():
    """Baseline chunks, and chunks whose contextualisation failed, carry no text_raw."""
    plain = chunk(RAW)

    assert with_raw_text(plain) is plain


def test_with_raw_text_preserves_identity_and_score():
    contextualised = chunk(f"{CONTEXT}\n\n{RAW}", raw=RAW)

    restored = with_raw_text(contextualised)

    assert (restored.chunk_id, restored.doc_id, restored.score) == ("c1", "d1", 0.9)
    assert restored.metadata["text_raw"] == RAW  # metadata is not stripped


def test_raw_text_retriever_restores_every_chunk_and_keeps_the_ranking():
    ranked = [
        chunk(f"{CONTEXT}\n\n{RAW}", raw=RAW, chunk_id="c1"),
        chunk("Texte nu, sans contexte.", chunk_id="c2"),
    ]

    out = RawTextRetriever(StubRetriever(ranked)).rank("césure ?", depth=2)

    assert [c.chunk_id for c in out] == ["c1", "c2"]  # order is the inner one's
    assert out[0].text == RAW
    assert out[1].text == "Texte nu, sans contexte."


def test_raw_text_retriever_honours_depth():
    ranked = [chunk(RAW, chunk_id=f"c{i}") for i in range(5)]

    assert len(RawTextRetriever(StubRetriever(ranked)).rank("q", depth=3)) == 3


# --- The property the whole experiment rests on ---------------------------

def test_a_context_quoting_an_expected_keyword_cannot_manufacture_a_hit():
    """The heart of the precaution, stated as an executable claim.

    The chunk's own text never mentions « césure »; only the generated context
    does. Counting on the contextualised text would score this as a retrieval
    success — the artifact the experiment exists to avoid.
    """
    contextualised = chunk(f"{CONTEXT}\n\n{RAW}", raw=RAW)
    keywords = ["césure"]

    naive = chunk_matches(contextualised.text, contextualised.metadata, None, keywords)
    strict_chunk = with_raw_text(contextualised)
    strict = chunk_matches(strict_chunk.text, strict_chunk.metadata, None, keywords)

    assert naive is True, "the context sentence alone satisfies the keyword"
    assert strict is False, "restored text must not: the chunk was not actually found"


def test_a_genuine_hit_survives_the_restoration():
    """The counterpart: restoration must not suppress real successes."""
    raw = "La césure permet de suspendre ses études pendant deux semestres."
    contextualised = chunk(f"{CONTEXT}\n\n{raw}", raw=raw)

    restored = with_raw_text(contextualised)

    assert chunk_matches(restored.text, restored.metadata, None, ["césure"]) is True
