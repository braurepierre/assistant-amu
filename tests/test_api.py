"""Tests for the FastAPI endpoints (PRD §7.5, F7). LLM mocked, no network."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from assistant_amu.api.main import app, get_backend, get_store
from assistant_amu.generation.llm import LLMBackendError
from assistant_amu.generation.rag import REFUSAL
from assistant_amu.models import RetrievedChunk


class FakeStore:
    def __init__(self):
        self.added = []
        self._docs: set[str] = set()

    def query(self, question, k=5):
        chunk = RetrievedChunk(
            chunk_id="c1", doc_id="d1", text="La cesure est une suspension des etudes.",
            metadata={"source_title": "Reglement", "source_url": "https://amu.fr/x",
                      "page": 12, "section": "Cesure"},
            score=0.83,
        )
        return [chunk][:k]

    def count(self):
        return 5

    def document_count(self):
        return 2

    def has_document(self, doc_id):
        return doc_id in self._docs

    def add_chunks(self, chunks):
        self._docs.update(c.doc_id for c in chunks)
        self.added.extend(chunks)
        return len(chunks)


class FakeBackend:
    name = "ollama/mistral"

    def __init__(self):
        self.reply = "La cesure est une suspension des etudes. [S1]"
        self.error: Exception | None = None

    def generate(self, system, user):
        if self.error:
            raise self.error
        return self.reply

    def health(self):
        return True


@pytest.fixture
def client_and_fakes():
    store, backend = FakeStore(), FakeBackend()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    yield TestClient(app), store, backend
    app.dependency_overrides.clear()


def test_ask_returns_answer_and_sources(client_and_fakes):
    client, _, _ = client_and_fakes
    response = client.post("/ask", json={"question": "Modalites de cesure ?", "k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].endswith("[S1]")
    assert body["model"] == "ollama/mistral"
    assert body["retrieved_chunks"] == 1
    assert body["condensed_question"] is None
    source = body["sources"][0]
    assert source["title"] == "Reglement"
    assert source["page"] == 12
    assert source["url"] == "https://amu.fr/x"
    assert 0.0 <= source["score"] <= 1.0
    assert len(source["excerpt"]) <= 300


def test_ask_refusal_has_no_sources(client_and_fakes):
    client, _, backend = client_and_fakes
    backend.reply = REFUSAL
    body = client.post("/ask", json={"question": "Quelle heure est-il ?"}).json()
    assert body["sources"] == []


@pytest.mark.parametrize("payload", [{"question": ""}, {"question": "x" * 501}, {"question": "ok", "k": 0}, {"question": "ok", "k": 11}])
def test_ask_validation_422(client_and_fakes, payload):
    client, _, _ = client_and_fakes
    assert client.post("/ask", json=payload).status_code == 422


def test_ask_503_on_backend_error(client_and_fakes):
    client, _, backend = client_and_fakes
    backend.error = LLMBackendError("down", cause="connection")
    response = client.post("/ask", json={"question": "cesure ?"})
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM backend unavailable: connection"


def test_health(client_and_fakes):
    client, _, _ = client_and_fakes
    body = client.get("/health").json()
    assert body == {"chroma": "ok", "llm_backend": "ok", "documents": 2, "chunks": 5}


def test_openapi_docs_available(client_and_fakes):
    client, _, _ = client_and_fakes
    assert client.get("/openapi.json").status_code == 200


# --- /ingest: monkeypatch the tokenizer (offline) and manifest path (no repo write) ---

@pytest.fixture
def ingest_client(client_and_fakes, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "assistant_amu.ingestion.chunk.default_token_counter",
        lambda *a, **k: (lambda text: len(text.split())),
    )
    monkeypatch.setattr("assistant_amu.api.main.INGESTED_MANIFEST", tmp_path / "ingested.jsonl")
    return client_and_fakes


_HTML = b"<html><body><main><h1>Titre</h1><p>La cesure est une suspension des etudes.</p></main></body></html>"


def test_ingest_html_success_and_manifest(ingest_client):
    client, store, _ = ingest_client
    response = client.post(
        "/ingest",
        files={"file": ("doc.html", _HTML, "text/html")},
        data={"title": "Reglement", "category": "reglement-scolarite"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chunks_added"] >= 1
    assert body["document_id"]
    assert len(store.added) >= 1


def test_ingest_duplicate_returns_409(ingest_client):
    client, _, _ = ingest_client
    files = {"file": ("doc.html", _HTML, "text/html")}
    client.post("/ingest", files=files, data={"title": "Reglement"})
    dup = client.post("/ingest", files={"file": ("doc.html", _HTML, "text/html")}, data={"title": "Reglement"})
    assert dup.status_code == 409


def test_ingest_unsupported_type_422(ingest_client):
    client, _, _ = ingest_client
    response = client.post(
        "/ingest", files={"file": ("notes.txt", b"plain", "text/plain")}, data={"title": "X"}
    )
    assert response.status_code == 422
