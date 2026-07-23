"""RAG query pipeline: prompt assembly + retrieval + generation (PRD §7.4).

The user message places XML-tagged sources first and the question last (better
instruction-following on long contexts; XML unambiguously separates data from
instructions). Refusals are detected by normalised comparison (§7.6) so a 7B's
minor variations still count — the same helper the eval harness uses. Query
condensation (V2, §7.7) is intentionally absent until V1 is validated (§11.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from xml.sax.saxutils import quoteattr

from ..config import PROJECT_ROOT, Settings, get_settings
from ..models import RetrievedChunk
from ..retrieval.vector_store import VectorStore
from .llm import LLMBackend, build_backend
from .rewrite import rewrite_query

PROMPTS_DIR = PROJECT_ROOT / "prompts"
REFUSAL = "Je ne trouve pas cette information dans les documents disponibles."
# Keep the last ~6 turns (user+assistant) of history before condensation (§7.7).
MAX_HISTORY_MESSAGES = 12
_ROLE_LABEL = {"user": "Utilisateur", "assistant": "Assistant"}

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class RagResult:
    answer: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    model: str = ""
    retrieved_chunks: int = 0
    condensed_question: str | None = None  # always None in V1
    rewritten_query: str | None = None  # None unless a rewrite strategy changed the query


@dataclass(frozen=True, slots=True)
class Preparation:
    """The retrieval query resolved before generation (condensation + rewrite).

    Returned by :meth:`RagPipeline.prepare` so a UI can show the reformulation
    live (before the answer) and so :meth:`RagPipeline.answer` can reuse the exact
    same query instead of recomputing it (§7.7 condensation, §5.3.5 rewrite).
    """

    condensed_question: str | None
    rewritten_query: str | None
    retrieval_query: str


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace (PRD §7.6)."""
    return _SPACES.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def is_refusal(answer: str) -> bool:
    """True when the answer is (or contains) the canonical refusal, normalised."""
    return normalize(REFUSAL) in normalize(answer)


@lru_cache(maxsize=4)
def load_system_prompt(name: str = "rag_system.md") -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def build_user_message(
    question: str, sources: list[RetrievedChunk], condensed_question: str | None = None
) -> str:
    """Assemble the user message: <sources> block first, question last (§7.4).

    In V2, when a condensed question is available it is shown alongside the
    original one (§7.7) so the model sees both the resolved and the raw intent.
    """
    lines = ["<sources>"]
    for i, source in enumerate(sources, start=1):
        meta = source.metadata
        attrs = [f'id="S{i}"', f"titre={quoteattr(str(meta.get('source_title', '')))}"]
        if meta.get("page") is not None:
            attrs.append(f"page={quoteattr(str(meta['page']))}")
        if meta.get("section"):
            attrs.append(f"section={quoteattr(str(meta['section']))}")
        lines.append(f"<source {' '.join(attrs)}>")
        lines.append(source.text)
        lines.append("</source>")
    lines.append("</sources>")
    body = "\n".join(lines)
    if condensed_question and condensed_question != question:
        return (
            f"{body}\n\nQuestion d'origine : {question}"
            f"\nQuestion reformulée (autonome) : {condensed_question}"
        )
    return f"{body}\n\nQuestion : {question}"


def format_history(history: list) -> str:
    """Render a chat history into a plain-text transcript for condensation."""
    lines = []
    for message in history:
        role = message["role"] if isinstance(message, dict) else message.role
        content = message["content"] if isinstance(message, dict) else message.content
        lines.append(f"{_ROLE_LABEL.get(role, role)} : {content}")
    return "\n".join(lines)


class RagPipeline:
    """Single-turn RAG: retrieve top-k, generate a sourced answer."""

    def __init__(
        self,
        *,
        store: VectorStore,
        backend: LLMBackend,
        system_prompt: str | None = None,
        condense_prompt: str | None = None,
    ):
        self._store = store
        self._backend = backend
        self._system = system_prompt if system_prompt is not None else load_system_prompt()
        self._condense_system = (
            condense_prompt if condense_prompt is not None
            else load_system_prompt("condense_system.md")
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        store: VectorStore | None = None,
        backend: LLMBackend | None = None,
    ) -> "RagPipeline":
        settings = settings or get_settings()
        return cls(
            store=store or VectorStore.from_settings(settings),
            backend=backend or build_backend(settings),
        )

    def prepare(
        self, question: str, history: list | None = None, rewrite: str = "raw"
    ) -> Preparation:
        """Resolve the retrieval query (condensation + rewrite) WITHOUT generating.

        Exposed so a UI can show the reformulation live, before the answer, and so
        :meth:`answer` can reuse the exact same query — no double condensation/
        rewrite call, and the preview can never drift from what was searched.
        rewrite="raw" with no history is the identity and spends no backend call.
        """
        condensed = self._condense(question, history) if history else None
        base_query = condensed or question
        retrieval_query = rewrite_query(base_query, rewrite, self._backend)
        rewritten = retrieval_query if retrieval_query != base_query else None
        return Preparation(condensed, rewritten, retrieval_query)

    def answer(
        self,
        question: str,
        k: int = 5,
        history: list | None = None,
        rewrite: str = "raw",
        prepared: Preparation | None = None,
    ) -> RagResult:
        # No history + rewrite="raw" => strictly the V1 behaviour (non-regression).
        # `prepared` lets a caller reuse an earlier prepare() (live-preview flow),
        # so the reformulation is resolved exactly once.
        prep = prepared or self.prepare(question, history, rewrite)
        condensed, rewritten = prep.condensed_question, prep.rewritten_query

        sources = self._store.query(prep.retrieval_query, k=k)
        if not sources:
            # Nothing retrieved: refuse without spending a generation call.
            return RagResult(REFUSAL, [], self._backend.name, 0, condensed, rewritten)

        user = build_user_message(question, sources, condensed_question=condensed)
        answer = self._backend.generate(self._system, user).strip()
        if is_refusal(answer):
            # Refusal cites no sources (F6).
            return RagResult(answer, [], self._backend.name, len(sources), condensed, rewritten)
        return RagResult(answer, sources, self._backend.name, len(sources), condensed, rewritten)

    def _condense(self, question: str, history: list) -> str:
        """Reformulate a follow-up into a standalone question (§7.7)."""
        recent = history[-MAX_HISTORY_MESSAGES:]
        user = f"{format_history(recent)}\n\nDernière question : {question}"
        condensed = self._backend.generate(self._condense_system, user).strip()
        return condensed or question  # fall back to the raw question if empty
