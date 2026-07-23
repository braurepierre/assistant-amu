"""Tests for query rewriting (strip heuristic + llm), §5.3.5. No network."""

from __future__ import annotations

import pytest

from assistant_amu.generation.rewrite import REWRITE_SYSTEM, rewrite_query, strip_query


class FakeBackend:
    """Records calls and replays canned replies (no network)."""

    name = "fake/test"

    def __init__(self, reply="régimes spéciaux"):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user):
        self.calls.append((system, user))
        return self.reply

    def health(self):
        return True


# --- strip: deterministic heuristic ---------------------------------------

@pytest.mark.parametrize(
    "question, expected",
    [
        ("Parle-moi des régimes spéciaux.", "régimes spéciaux"),
        ("Explique-moi la césure.", "césure"),
        ("Je voudrais des infos sur le contrôle des connaissances.", "contrôle des connaissances"),
        ("Donne-moi des informations sur le logement étudiant.", "logement étudiant"),
        ("Peux-tu me parler de l'inscription administrative en ligne ?", "inscription administrative en ligne"),
    ],
)
def test_strip_removes_conversational_opener(question, expected):
    assert strip_query(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "Qu'est-ce que la CVEC ?",
        "Comment demander une césure à l'université ?",
        "Quels aménagements pour un étudiant en situation de handicap ?",
        "Où consulter le calendrier universitaire ?",
        "Que signifie le sigle BCC ?",
    ],
)
def test_strip_is_identity_on_definitional_questions(question):
    # Definitional questions start with no opener => byte-identical (no regression).
    assert strip_query(question) == question


def test_strip_never_returns_empty():
    assert strip_query("Parle-moi") == "Parle-moi"  # nothing left to keep -> original


# --- rewrite_query dispatch ------------------------------------------------

def test_rewrite_raw_is_identity_and_calls_nothing():
    backend = FakeBackend()
    q = "Parle-moi des régimes spéciaux."
    assert rewrite_query(q, "raw", backend) == q
    assert backend.calls == []  # raw never touches the backend


def test_rewrite_strip_uses_heuristic_without_backend():
    assert rewrite_query("Parle-moi des régimes spéciaux.", "strip") == "régimes spéciaux"


def test_rewrite_llm_calls_backend_with_rewrite_prompt():
    backend = FakeBackend("régimes spéciaux")
    out = rewrite_query("Parle-moi des régimes spéciaux.", "llm", backend)
    assert out == "régimes spéciaux"
    assert len(backend.calls) == 1
    assert backend.calls[0][0] == REWRITE_SYSTEM  # rewrite system prompt threaded through


def test_rewrite_llm_cleans_quotes_and_extra_lines():
    backend = FakeBackend('« régimes spéciaux »\nblabla')
    assert rewrite_query("q", "llm", backend) == "régimes spéciaux"


def test_rewrite_llm_without_backend_degrades_to_identity():
    q = "Parle-moi des régimes spéciaux."
    assert rewrite_query(q, "llm", None) == q  # no backend -> no-op, never crashes


def test_rewrite_llm_empty_reply_falls_back_to_question():
    assert rewrite_query("ma question", "llm", FakeBackend("   ")) == "ma question"


def test_rewrite_unknown_strategy_raises():
    with pytest.raises(ValueError):
        rewrite_query("q", "bogus")
