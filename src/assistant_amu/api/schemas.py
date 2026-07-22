"""Pydantic v2 request/response models — API contracts (PRD §7.5, §7.7).

The models are the single source of truth for validation (422) and the OpenAPI
docs. The optional ``history`` field is the V2 extension: its absence reproduces
the V1 behaviour exactly (backward-compatible).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=10)
    # V2 (optional, backward-compatible): omitted => V1 single-turn behaviour.
    # Beyond the last 6 turns the pipeline truncates silently (§7.7).
    history: list[HistoryMessage] | None = None

    # Clean single-turn example so /docs "Try it out" does not pre-fill a bogus
    # `history` (which would wrongly trigger V2 condensation on dummy text).
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"question": "Quelles sont les modalités de la césure ?", "k": 5}
        }
    )


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


class IngestResponse(BaseModel):
    document_id: str
    chunks_added: int


class HealthResponse(BaseModel):
    chroma: str  # "ok" | "error"
    llm_backend: str  # "ok" | "unreachable"
    documents: int
    chunks: int
