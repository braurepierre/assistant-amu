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
        self.queries: list[str] = []

    def query(self, question, k=5):
        self.queries.append(question)
        return self._results[:k]


class FakeBackend:
    name = "fake/test"

    def __init__(self, reply):
        # A single string, or a list of replies returned in call order (V2:
        # first the condensation, then the answer).
        self._replies = [reply] if isinstance(reply, str) else list(reply)
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user):
        index = len(self.calls)
        self.calls.append((system, user))
        return self._replies[index] if index < len(self._replies) else self._replies[-1]

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


# --- V2: query condensation (§7.7) ---------------------------------------

def test_condensation_runs_with_history():
    store = FakeStore([_rc("c1", "La cesure en droit ...", score=0.8)])
    backend = FakeBackend(["Modalites de cesure pour un etudiant en droit ?", "Reponse [S1]"])
    history = [
        {"role": "user", "content": "Modalites de cesure ?"},
        {"role": "assistant", "content": "La cesure est une suspension."},
    ]
    result = RagPipeline(store=store, backend=backend, system_prompt="SYS", condense_prompt="COND").answer(
        "Et pour un etudiant en droit ?", history=history
    )
    assert result.condensed_question == "Modalites de cesure pour un etudiant en droit ?"
    assert len(backend.calls) == 2
    assert backend.calls[0][0] == "COND"  # first call: condensation prompt
    assert backend.calls[1][0] == "SYS"  # second call: answer prompt
    assert store.queries[0] == "Modalites de cesure pour un etudiant en droit ?"  # retrieval on condensed


def test_no_history_is_v1_single_call():
    store = FakeStore([_rc("c1", "texte", score=0.8)])
    backend = FakeBackend(["Reponse [S1]"])
    result = RagPipeline(store=store, backend=backend, system_prompt="SYS", condense_prompt="COND").answer("Question ?")
    assert result.condensed_question is None
    assert len(backend.calls) == 1  # no condensation call (non-regression)
    assert backend.calls[0][0] == "SYS"


def test_history_truncated_to_recent_turns():
    from assistant_amu.generation.rag import MAX_HISTORY_MESSAGES

    store = FakeStore([_rc("c1", "texte", score=0.8)])
    backend = FakeBackend(["condensee", "reponse"])
    history = [{"role": "user", "content": f"m{i}"} for i in range(20)]
    RagPipeline(store=store, backend=backend, system_prompt="SYS", condense_prompt="COND").answer(
        "suite ?", history=history
    )
    condense_user_message = backend.calls[0][1]
    assert "m19" in condense_user_message  # most recent kept
    assert "m7" not in condense_user_message  # beyond the last MAX_HISTORY_MESSAGES dropped
    assert MAX_HISTORY_MESSAGES == 12


def test_build_user_message_includes_condensed():
    msg = build_user_message("Et en droit ?", [_rc("c1", "texte")], condensed_question="Cesure en droit ?")
    assert "Question d'origine : Et en droit ?" in msg
    assert "Cesure en droit ?" in msg
