"""Tests for prompt assembly, refusal detection and the RAG pipeline (§7.4, F6)."""

from __future__ import annotations

from assistant_amu.generation.rag import (
    REFUSAL,
    RagPipeline,
    build_user_message,
    is_refusal,
    load_system_prompt,
    normalize,
)
from assistant_amu.models import RetrievedChunk


def _rc(chunk_id, text, *, title="Doc", page=1, section=None, score=0.9):
    return RetrievedChunk(
        chunk_id=chunk_id, doc_id="d", text=text, score=score,
        metadata={"source_title": title, "page": page, "section": section},
    )


class FakeStore:
    def __init__(self, results):
        self._results = results

    def query(self, question, k=5):
        return self._results[:k]


class FakeBackend:
    name = "fake/test"

    def __init__(self, reply):
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user):
        self.calls.append((system, user))
        return self._reply

    def health(self):
        return True


def test_build_user_message_sources_before_question():
    msg = build_user_message(
        "Ma question ?",
        [_rc("c1", "texte un", title="Reglement", page=12, section="Cesure")],
    )
    assert msg.index("<sources>") < msg.index("Question :")
    assert 'id="S1"' in msg
    assert "Reglement" in msg and "Cesure" in msg
    assert msg.rstrip().endswith("Question : Ma question ?")


def test_pipeline_returns_answer_and_sources():
    store = FakeStore([_rc("c1", "La cesure est une suspension.", score=0.8)])
    backend = FakeBackend("La cesure est une suspension des etudes. [S1]")
    result = RagPipeline(store=store, backend=backend, system_prompt="SYS").answer("cesure ?", k=5)
    assert result.answer.endswith("[S1]")
    assert result.retrieved_chunks == 1
    assert len(result.sources) == 1
    assert result.model == "fake/test"
    assert result.condensed_question is None  # V1
    assert backend.calls[0][0] == "SYS"  # system prompt threaded through


def test_refusal_drops_cited_sources():
    store = FakeStore([_rc("c1", "texte hors sujet", score=0.2)])
    backend = FakeBackend(REFUSAL)
    result = RagPipeline(store=store, backend=backend, system_prompt="SYS").answer("hors sujet ?")
    assert is_refusal(result.answer)
    assert result.sources == []  # F6: 0 source cited on refusal
    assert result.retrieved_chunks == 1


def test_empty_retrieval_refuses_without_calling_llm():
    backend = FakeBackend("must not be called")
    result = RagPipeline(store=FakeStore([]), backend=backend, system_prompt="SYS").answer("q")
    assert result.answer == REFUSAL
    assert result.sources == []
    assert backend.calls == []


def test_is_refusal_normalised():
    assert is_refusal("Je ne trouve pas cette information dans les documents disponibles.")
    assert is_refusal("  je ne trouve PAS cette information dans les documents disponibles  ")
    assert not is_refusal("La cesure est une suspension temporaire des etudes.")


def test_normalize_strips_punctuation_and_case():
    assert normalize("Bonjour, AMU !") == "bonjour amu"


def test_default_system_prompt_loads_and_mentions_identity():
    prompt = load_system_prompt()
    assert "AssistantAMU" in prompt
    assert REFUSAL in prompt  # the exact refusal phrase is defined in the prompt
