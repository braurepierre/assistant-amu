"""Tests for the evaluation harness logic (PRD §7.6, F8)."""

from __future__ import annotations

from assistant_amu.evaluation import (
    E2ERow,
    Question,
    RrfRetriever,
    chunk_matches,
    evaluate_end_to_end,
    evaluate_retrieval,
    load_questions,
    reciprocal_rank_fusion,
    render_retrieval_report,
)
from assistant_amu.generation.rag import REFUSAL
from assistant_amu.models import RetrievedChunk


def _rc(chunk_id, text, *, title="Doc"):
    return RetrievedChunk(chunk_id, "d", text, {"source_title": title}, 0.5)


class FakeRetriever:
    def __init__(self, by_question):
        self._by_question = by_question

    def rank(self, question, depth):
        return self._by_question.get(question, [])[:depth]


# --- matching -------------------------------------------------------------

def test_chunk_matches_source_and_keywords():
    meta = {"source_title": "Reglement des etudes"}
    assert chunk_matches("La cesure est ...", meta, "Reglement", ["cesure"])
    assert not chunk_matches("La cesure est ...", meta, "Guide", ["cesure"])  # wrong source
    assert not chunk_matches("La cesure est ...", meta, "Reglement", ["mcc"])  # missing keyword


def test_chunk_matches_keywords_only():
    assert chunk_matches("texte avec mcc", {"source_title": "X"}, None, ["mcc"])


# --- RRF ------------------------------------------------------------------

def test_rrf_orders_shared_items_first():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert fused[0] == "b"  # appears in both lists
    assert fused.index("a") < fused.index("c")  # a ranked #2 vs c #2 but only once


def test_rrf_retriever_returns_fused_chunks():
    a, b, c = _rc("a", "alpha"), _rc("b", "beta"), _rc("c", "gamma")
    semantic = FakeRetriever({"q": [a, b]})
    lexical = FakeRetriever({"q": [b, c]})
    rrf = RrfRetriever(semantic, lexical, {"a": a, "b": b, "c": c})
    result = rrf.rank("q", 2)
    assert result[0].chunk_id == "b"
    assert {r.chunk_id for r in result} == {"a", "b"}


# --- retrieval evaluation -------------------------------------------------

def test_evaluate_retrieval_recall_and_disagreements():
    questions = [
        Question("q1", "cesure ?", True, "Reglement", ["cesure"]),
        Question("q2", "mcc ?", True, "Reglement", ["mcc"]),
        Question("q3", "hors sujet", False),  # ignored by retrieval eval
    ]
    hit_cesure = _rc("c1", "la cesure ...", title="Reglement")
    hit_mcc = _rc("c2", "les mcc ...", title="Reglement")
    miss = _rc("c9", "sans rapport", title="Reglement")
    retrievers = {
        "semantic": FakeRetriever({"cesure ?": [hit_cesure], "mcc ?": [hit_mcc]}),
        "bm25": FakeRetriever({"cesure ?": [miss], "mcc ?": [hit_mcc]}),
    }
    report = evaluate_retrieval(questions, retrievers, k=5)
    assert report.n_answerable == 2
    assert report.recall["semantic"] == 1.0
    assert report.recall["bm25"] == 0.5
    assert [r.id for r in report.disagreements] == ["q1"]


def test_render_retrieval_report_has_sections():
    questions = [Question("q1", "cesure ?", True, "Reglement", ["cesure"])]
    retrievers = {"semantic": FakeRetriever({"cesure ?": [_rc("c1", "la cesure", title="Reglement")]})}
    report = evaluate_retrieval(questions, retrievers, k=5)
    md = render_retrieval_report(report, date="2026-07-22", backend="ollama/mistral", model="e5")
    assert "Recall@k" in md
    assert "Désaccords" in md
    assert "2026-07-22" in md


# --- end-to-end -----------------------------------------------------------

class FakePipeline:
    def __init__(self, reply):
        self._reply = reply

    def answer(self, question, k=5):
        from assistant_amu.generation.rag import RagResult
        return RagResult(self._reply, [], "fake/test", 0)


def test_evaluate_end_to_end_refusal_detection():
    questions = [
        Question("q1", "cesure ?", True),
        Question("q2", "quelle heure ?", False),
    ]
    rows = evaluate_end_to_end(questions, FakePipeline(REFUSAL), k=5)
    by_id = {r.id: r for r in rows}
    assert by_id["q1"].refusal_correct is None  # answerable: not applicable
    assert by_id["q2"].refusal_correct is True  # refused a non-answerable -> correct


# --- loading --------------------------------------------------------------

def test_evaluate_conversation_threads_history():
    from assistant_amu.evaluation import Scenario, Turn, evaluate_conversation, render_conversation_report
    from assistant_amu.generation.rag import RagResult

    class FakeConvPipeline:
        def answer(self, question, k=5, history=None):
            sources = [RetrievedChunk("c1", "d", "la cesure ...", {"source_title": "Reglement"}, 0.8)]
            condensed = "cesure en droit ?" if history else None
            return RagResult("La cesure [S1]", sources, "fake", 1, condensed)

    scenarios = [
        Scenario("s1", [
            Turn("cesure ?", True, "Reglement", ["cesure"]),
            Turn("et en droit ?", True, "Reglement", ["cesure"]),
        ])
    ]
    rows = evaluate_conversation(scenarios, FakeConvPipeline(), k=5)
    assert len(rows) == 2
    assert rows[0].condensed_question is None  # first turn, no history
    assert rows[1].condensed_question == "cesure en droit ?"  # follow-up condensed
    assert all(r.recall_hit for r in rows)
    md = render_conversation_report(rows, date="2026-07-22", backend="fake", k=5)
    assert "conversation (V2)" in md


def test_load_scenarios(tmp_path):
    from assistant_amu.evaluation import load_scenarios

    path = tmp_path / "s.yaml"
    path.write_text(
        "scenarios:\n"
        "  - id: s1\n"
        "    turns:\n"
        "      - question: cesure ?\n        answerable: true\n"
        "        expected_source: Reglement\n        expected_keywords: [cesure]\n"
        "      - question: et en droit ?\n        answerable: true\n",
        encoding="utf-8",
    )
    scenarios = load_scenarios(path)
    assert len(scenarios) == 1
    assert len(scenarios[0].turns) == 2
    assert scenarios[0].turns[0].expected_keywords == ["cesure"]


def test_load_questions(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text(
        "questions:\n"
        "  - id: q1\n    question: cesure ?\n    answerable: true\n"
        "    expected_source: Reglement\n    expected_keywords: [cesure]\n"
        "  - id: q2\n    question: heure ?\n    answerable: false\n",
        encoding="utf-8",
    )
    questions = load_questions(path)
    assert len(questions) == 2
    assert questions[0].expected_keywords == ["cesure"]
    assert questions[1].answerable is False
