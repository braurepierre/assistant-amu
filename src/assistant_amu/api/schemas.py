"""Pydantic v2 request/response models — API contracts (PRD §7.5, §7.7).

The models are the single source of truth for validation (422) and the OpenAPI
docs. The optional ``history`` field is the V2 extension: its absence reproduces
the V1 behaviour exactly (backward-compatible).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# What one turn of a conversation may weigh, and how many turns a request may
# carry. Without these the request body is unbounded where `question` and `k`
# are not: the pipeline keeps only the last MAX_HISTORY_MESSAGES entries, but
# truncation happens *after* the body has been read, validated and held in
# memory, and a single message of several megabytes still reaches the model.
# The caps are set above what a real conversation produces — a question is
# capped at 500 characters and an answer runs to a few paragraphs — so they
# refuse abuse without refusing use.
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_ITEMS = 24


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=10)
    # V2 (optional, backward-compatible): omitted => V1 single-turn behaviour.
    # Beyond the last 6 turns the pipeline truncates silently (§7.7); the cap
    # here is wider, so an ordinary conversation is never refused for its length.
    history: list[HistoryMessage] | None = Field(default=None, max_length=MAX_HISTORY_ITEMS)
    # Query rewriting before retrieval (§5.3.5, measured in eval/). "raw" is the
    # V1 default (identity, no extra backend call); "strip" is a deterministic
    # heuristic; "llm" costs one extra backend call and is non-deterministic.
    rewrite: Literal["raw", "strip", "llm"] = "raw"

    # Live-preview flow (used by the demo): when /prepare has already resolved the
    # retrieval query, pass it back so /ask reuses it verbatim — no second
    # condensation/rewrite call, and the previewed query cannot drift from what is
    # searched. Omitted by normal clients => /ask resolves it itself.
    retrieval_query: str | None = None
    condensed_question: str | None = None
    rewritten_query: str | None = None

    # Clean single-turn example so /docs "Try it out" does not pre-fill a bogus
    # `history` (which would wrongly trigger V2 condensation on dummy text).
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"question": "Quelles sont les modalités de la césure ?", "k": 5}
        }
    )


class PrepareRequest(BaseModel):
    """Resolve the retrieval query (condensation + rewrite) without generating."""

    question: str = Field(min_length=1, max_length=500)
    history: list[HistoryMessage] | None = Field(default=None, max_length=MAX_HISTORY_ITEMS)
    rewrite: Literal["raw", "strip", "llm"] = "raw"


class PrepareResponse(BaseModel):
    condensed_question: str | None = None  # V2 condensation of a follow-up (§7.7)
    rewritten_query: str | None = None  # non-null only if the rewrite changed the query
    retrieval_query: str  # the query actually used for retrieval (echoed back to /ask)


class Source(BaseModel):
    title: str
    url: str | None = None
    page: int | None = None
    excerpt: str  # first ~300 characters of the chunk
    score: float  # cosine similarity in [0, 1] (§7.5)


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    retrieved_chunks: int
    condensed_question: str | None = None  # always null in V1
    rewritten_query: str | None = None  # the rewritten retrieval query, if rewrite changed it


class IngestResponse(BaseModel):
    document_id: str
    chunks_added: int


class HealthResponse(BaseModel):
    chroma: str  # "ok" | "error"
    llm_backend: str  # "ok" | "unreachable"
    documents: int
    chunks: int
