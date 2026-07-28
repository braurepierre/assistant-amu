"""FastAPI application: POST /ask, POST /ingest, GET /health (PRD §7.5, F7).

Configuration is validated at import time (``get_settings()``) so misconfiguration
fails at startup, not on the first request (F5). The store, backend and pipeline
are lazy singletons exposed as dependencies so tests can override them with fakes
(no real model or network). Interactive docs at ``/docs``.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import PROJECT_ROOT, get_settings
from ..generation.llm import LLMBackend, LLMBackendError, build_backend
from ..generation.rag import Preparation, RagPipeline
from ..ingestion import IngestionError
from ..ingestion.chunk import chunk_document
from ..ingestion.clean import clean_document
from ..ingestion.extract import extract
from ..models import SourceDoc
from ..retrieval.vector_store import VectorStore
from .schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IngestResponse,
    PrepareRequest,
    PrepareResponse,
    Source,
)

# Validate configuration eagerly: a bad LLM_BACKEND fails uvicorn startup (F5).
get_settings()

INGESTED_MANIFEST = PROJECT_ROOT / "corpus" / "ingested.jsonl"
DEMO_PAGE = PROJECT_ROOT / "demo.html"
SITE_OUTPUT = PROJECT_ROOT / "docs" / "site" / "output"
_EXTENSIONS = {".pdf": "pdf", ".html": "html", ".htm": "html"}

app = FastAPI(
    title="AssistantAMU",
    version="0.1.0",
    summary="RAG documentary assistant over Aix-Marseille Université public documents.",
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demo_page() -> HTMLResponse:
    """Serve the static chatbot demo page — a pure HTTP client of this API (§5.4)."""
    if DEMO_PAGE.exists():
        return HTMLResponse(DEMO_PAGE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>demo.html introuvable</h1>", status_code=404)


@lru_cache(maxsize=1)
def get_store() -> VectorStore:
    return VectorStore.from_settings()


@lru_cache(maxsize=1)
def get_backend() -> LLMBackend:
    return build_backend()


def get_pipeline(
    store: VectorStore = Depends(get_store),
    backend: LLMBackend = Depends(get_backend),
) -> RagPipeline:
    return RagPipeline(store=store, backend=backend)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, pipeline: RagPipeline = Depends(get_pipeline)) -> AskResponse:
    history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
    # If the client already resolved the retrieval query via /prepare (live-preview
    # flow), reuse it verbatim so the reformulation is computed exactly once.
    prepared = (
        Preparation(request.condensed_question, request.rewritten_query, request.retrieval_query)
        if request.retrieval_query is not None
        else None
    )
    try:
        result = pipeline.answer(
            request.question, k=request.k, history=history, rewrite=request.rewrite, prepared=prepared
        )
    except LLMBackendError as exc:
        raise HTTPException(status_code=503, detail=f"LLM backend unavailable: {exc.cause}")
    return AskResponse(
        answer=result.answer,
        sources=[
            Source(
                title=str(rc.metadata.get("source_title", "")),
                url=rc.metadata.get("source_url"),
                page=rc.metadata.get("page"),
                excerpt=rc.text[:300],
                score=rc.score,
            )
            for rc in result.sources
        ],
        model=result.model,
        retrieved_chunks=result.retrieved_chunks,
        condensed_question=result.condensed_question,
        rewritten_query=result.rewritten_query,
    )


@app.post("/prepare", response_model=PrepareResponse)
def prepare(request: PrepareRequest, pipeline: RagPipeline = Depends(get_pipeline)) -> PrepareResponse:
    """Resolve the retrieval query (condensation + rewrite) without generating.

    Lets a UI show the reformulation live, before the answer. The returned
    ``retrieval_query`` is echoed back to ``/ask`` so the answer reuses it and the
    preview never drifts from what was searched (§7.7, §5.3.5).
    """
    history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
    try:
        prep = pipeline.prepare(request.question, history=history, rewrite=request.rewrite)
    except LLMBackendError as exc:
        raise HTTPException(status_code=503, detail=f"LLM backend unavailable: {exc.cause}")
    return PrepareResponse(
        condensed_question=prep.condensed_question,
        rewritten_query=prep.rewritten_query,
        retrieval_query=prep.retrieval_query,
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(
    file: UploadFile = File(...),
    title: str = Form(...),
    url: str | None = Form(None),
    category: str | None = Form(None),
    store: VectorStore = Depends(get_store),
) -> IngestResponse:
    doc_type = _EXTENSIONS.get(Path(file.filename or "").suffix.lower())
    if doc_type is None:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {file.filename!r}")

    source = SourceDoc(title=title, category=category, type=doc_type, url=url)
    with tempfile.NamedTemporaryFile(suffix=f".{doc_type}", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)
    try:
        document = clean_document(extract(tmp_path, source))
        chunks = chunk_document(document)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    if store.has_document(document.doc_id):
        raise HTTPException(status_code=409, detail=f"Document already ingested: {document.doc_id}")

    added = store.add_chunks(chunks)
    _append_manifest(document.doc_id, title, url, category)
    return IngestResponse(document_id=document.doc_id, chunks_added=added)


@app.get("/health", response_model=HealthResponse)
def health(
    store: VectorStore = Depends(get_store),
    backend: LLMBackend = Depends(get_backend),
) -> HealthResponse:
    try:
        chunks = store.count()
        documents = store.document_count()
        chroma_status = "ok"
    except Exception:  # noqa: BLE001 - health must never raise
        chunks, documents, chroma_status = 0, 0, "error"
    return HealthResponse(
        chroma=chroma_status,
        llm_backend="ok" if backend.health() else "unreachable",
        documents=documents,
        chunks=chunks,
    )


# The documentation site, served by this application when it has been built.
#
# The assistant panel of the site calls /ask from the page it is on. Served here,
# page and API share an origin: no CORS configuration, and none of the private
# network rules a browser applies to an HTTPS page calling a local address. The
# site remains readable without this application — opened from the filesystem or
# published on its own, its panel simply reports that no instance answers.
#
# Mounted at import time, so a site rebuilt while the server runs is picked up by
# a restart, not on the fly.
if SITE_OUTPUT.is_dir():
    app.mount("/site", StaticFiles(directory=SITE_OUTPUT, html=True), name="site")


def _append_manifest(doc_id: str, title: str, url: str | None, category: str | None) -> None:
    """Trace an /ingest document in the versioned manifest (PRD §7.1, §7.5)."""
    record = {
        "document_id": doc_id,
        "title": title,
        "url": url,
        "category": category,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    INGESTED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with INGESTED_MANIFEST.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
