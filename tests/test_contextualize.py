"""Tests for Contextual Retrieval chunk contextualisation (§5.3.1). No network."""

from __future__ import annotations

import json

import pytest

from assistant_amu.generation.llm import LLMBackendError
from assistant_amu.ingestion.contextualize import (
    CONTEXT_SYSTEM,
    PROMPT_VERSION,
    ContextCache,
    build_user_prompt,
    clean_context,
    context_key,
    contextual_collection_name,
    contextualize_chunks,
    contextualized_chunk,
    generate_context,
)
from assistant_amu.models import Chunk, Document, TextBlock


class FakeBackend:
    """Replays canned replies and records calls (no network)."""

    name = "fake/test"

    def __init__(self, reply="Règlement des études, section césure : conditions de dépôt."):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user):
        self.calls.append((system, user))
        return self.reply

    def health(self):
        return True


class FailingBackend(FakeBackend):
    """Raises a chosen cause; counts attempts so retries are observable."""

    def __init__(self, cause="quota", fail_times=99, reply="Contexte."):
        super().__init__(reply)
        self.cause = cause
        self.fail_times = fail_times
        self.attempts = 0

    def generate(self, system, user):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise LLMBackendError("boom", cause=self.cause)
        return super().generate(system, user)


@pytest.fixture
def doc():
    return Document(
        doc_id="d1",
        title="Règlement des études",
        category="reglement-scolarite",
        url=None,
        blocks=[TextBlock("La césure est une suspension temporaire des études.", page=1)],
    )


@pytest.fixture
def chunks():
    return [
        Chunk("c1", "d1", "L'article 12 fixe la date de dépôt.", {"source_title": "Règlement"}),
        Chunk("c2", "d1", "La demande est examinée par la composante.", {"source_title": "Règlement"}),
    ]


# --- Prompt ----------------------------------------------------------------

def test_system_prompt_is_loaded_from_the_prompts_directory():
    assert "phrase nominale" in CONTEXT_SYSTEM
    assert CONTEXT_SYSTEM.strip() == CONTEXT_SYSTEM  # stripped at load time


def test_user_prompt_puts_the_document_first_and_the_chunk_last():
    prompt = build_user_prompt("texte intégral", "extrait", "Titre")
    assert prompt.index("texte intégral") < prompt.index("extrait")
    assert prompt.rstrip().endswith("</extrait>")
    assert 'titre="Titre"' in prompt


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Règlement, section césure : dépôt.  ", "Règlement, section césure : dépôt."),
        ('"Règlement, section césure."', "Règlement, section césure."),
        ("« Règlement, section césure. »", "Règlement, section césure."),  # guillemets français
        ("\n\nPremière ligne\nseconde ligne", "Première ligne"),
        ("   \n  ", ""),
    ],
)
def test_clean_context_keeps_the_first_meaningful_line(raw, expected):
    assert clean_context(raw) == expected


# --- Chunk transformation --------------------------------------------------

def test_contextualized_chunk_prefixes_and_preserves_the_original(chunks):
    out = contextualized_chunk(chunks[0], "Règlement, section césure.")
    assert out.text.startswith("Règlement, section césure.")
    assert chunks[0].text in out.text
    assert out.metadata["text_raw"] == chunks[0].text  # measurement validity
    assert out.metadata["context"] == "Règlement, section césure."
    assert out.chunk_id == chunks[0].chunk_id  # ids are stable: the index dedups on them


def test_empty_context_leaves_the_chunk_untouched(chunks):
    assert contextualized_chunk(chunks[0], "") is chunks[0]


def test_contextual_collection_name_is_derived_from_the_production_one():
    assert contextual_collection_name("amu_docs") == "amu_docs_ctx"


# --- Cache -----------------------------------------------------------------

def test_cache_round_trips_and_is_keyed_by_model_and_prompt_version(tmp_path):
    cache = ContextCache(tmp_path / "contexts.jsonl")
    cache.put("k1", "c1", "d1", "mistral/small", "Contexte.")

    assert cache.get("k1", "mistral/small") == "Contexte."
    assert cache.get("k1", "ollama/mistral") is None  # another model: regenerate
    assert ContextCache(tmp_path / "contexts.jsonl").get("k1", "mistral/small") == "Contexte."

    record = json.loads((tmp_path / "contexts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["prompt_version"] == PROMPT_VERSION


def test_the_cache_key_addresses_the_text_not_the_chunk_position(chunks):
    """chunk_id is hash(doc_id, index): stable across a re-chunking that moves text.

    Keying the cache on it replays, on a corpus re-cut at another budget, contexts
    written for other spans — the exact failure this key exists to prevent.
    """
    moved = Chunk(chunks[0].chunk_id, chunks[0].doc_id, "Un tout autre texte.", {})
    assert moved.chunk_id == chunks[0].chunk_id
    assert context_key(moved) != context_key(chunks[0])

    same_text_other_doc = Chunk("c9", "d2", chunks[0].text, {})
    assert context_key(same_text_other_doc) != context_key(chunks[0])  # document matters too


def test_records_predating_content_addressing_are_ignored(tmp_path):
    """A key that said nothing about the text cannot be trusted after the fix."""
    path = tmp_path / "contexts.jsonl"
    path.write_text(
        json.dumps({"chunk_id": "c1", "doc_id": "d1", "model": "m",
                    "prompt_version": PROMPT_VERSION, "context": "Contexte périmé."}) + "\n",
        encoding="utf-8",
    )

    assert len(ContextCache(path)) == 0


def test_cache_survives_a_truncated_last_line(tmp_path):
    path = tmp_path / "contexts.jsonl"
    good = json.dumps(
        {"key": "k1", "chunk_id": "c1", "doc_id": "d1", "model": "m",
         "prompt_version": PROMPT_VERSION, "context": "Contexte."},
        ensure_ascii=False,
    )
    path.write_text(good + "\n{\"key\": \"k2\", trunca", encoding="utf-8")

    cache = ContextCache(path)
    assert cache.get("k1", "m") == "Contexte."
    assert len(cache) == 1


def test_a_cached_chunk_costs_no_backend_call(tmp_path, doc, chunks):
    cache = ContextCache(tmp_path / "contexts.jsonl")
    backend = FakeBackend()
    cache.put(context_key(chunks[0]), chunks[0].chunk_id, "d1", backend.name, "Contexte connu.")

    out, report = contextualize_chunks(chunks, [doc], backend, cache=cache, progress=lambda _: None)

    assert report.cached == 1 and report.generated == 1
    assert len(backend.calls) == 1  # only the uncached chunk hit the backend
    assert out[0].metadata["context"] == "Contexte connu."


# --- Batch behaviour -------------------------------------------------------

def test_contextualize_chunks_prefixes_every_chunk(tmp_path, doc, chunks):
    backend = FakeBackend()
    out, report = contextualize_chunks(
        chunks, [doc], backend, cache=ContextCache(tmp_path / "c.jsonl"), progress=lambda _: None
    )

    assert report.generated == 2 and report.cached == 0 and not report.failed
    assert all(c.metadata["context"] == backend.reply for c in out)
    assert [c.metadata["text_raw"] for c in out] == [c.text for c in chunks]


def test_a_failing_chunk_is_kept_unchanged_and_reported(tmp_path, doc, chunks):
    backend = FailingBackend(cause="auth")  # not retried: a key problem will not fix itself
    out, report = contextualize_chunks(
        chunks, [doc], backend, cache=ContextCache(tmp_path / "c.jsonl"), progress=lambda _: None
    )

    assert len(report.failed) == 2 and report.generated == 0
    assert [c.text for c in out] == [c.text for c in chunks]  # degraded, never dropped
    assert "text_raw" not in out[0].metadata


def test_transient_failures_are_retried_then_succeed(tmp_path, doc, chunks):
    backend = FailingBackend(cause="quota", fail_times=2)
    slept: list[float] = []

    out, report = contextualize_chunks(
        chunks[:1], [doc], backend, cache=ContextCache(tmp_path / "c.jsonl"),
        progress=lambda _: None, sleep=slept.append,
    )

    assert report.generated == 1 and not report.failed
    assert backend.attempts == 3 and slept == [2.0, 5.0]  # backoff, no wall-clock cost
    assert out[0].metadata["context"] == backend.reply


def test_retries_are_exhausted_then_the_failure_is_recorded(tmp_path, doc, chunks):
    backend = FailingBackend(cause="timeout")
    out, report = contextualize_chunks(
        chunks[:1], [doc], backend, cache=ContextCache(tmp_path / "c.jsonl"),
        progress=lambda _: None, sleep=lambda _: None,
    )

    assert len(report.failed) == 1 and "timeout" in report.failed[0][1]
    assert out[0].text == chunks[0].text


def test_an_empty_generated_context_is_a_failure_not_a_silent_noop(tmp_path, doc, chunks):
    out, report = contextualize_chunks(
        chunks[:1], [doc], FakeBackend(reply="   "), cache=ContextCache(tmp_path / "c.jsonl"),
        progress=lambda _: None,
    )

    assert report.failed == [("c1", "empty context returned")]
    assert out[0].text == chunks[0].text


def test_a_chunk_without_its_document_is_reported_not_guessed(tmp_path, chunks):
    out, report = contextualize_chunks(
        chunks[:1], [], FakeBackend(), cache=ContextCache(tmp_path / "c.jsonl"),
        progress=lambda _: None,
    )

    assert report.failed == [("c1", "document text unavailable")]
    assert out[0] is chunks[0]


def test_oversized_documents_are_truncated_and_named(tmp_path, chunks):
    big = Document("d1", "Gros règlement", None, None, [TextBlock("x" * 5_000)])
    backend = FakeBackend()

    _, report = contextualize_chunks(
        chunks[:1], [big], backend, cache=ContextCache(tmp_path / "c.jsonl"),
        max_doc_chars=1_000, progress=lambda _: None,
    )

    assert report.truncated_docs == ["Gros règlement"]
    assert len(backend.calls[0][1]) < 2_000  # the document was cut before the call


def test_generate_context_does_not_retry_a_permanent_cause():
    backend = FailingBackend(cause="auth")
    with pytest.raises(LLMBackendError):
        generate_context(backend, "doc", "chunk", "Titre", sleep=lambda _: None)
    assert backend.attempts == 1
