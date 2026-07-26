"""Contextual Retrieval — situate each chunk in its document before indexing.

Administrative chunks are typically *decontextualised*: « L'article 12 précise
que la demande doit être déposée avant le 31 mars » names neither the règlement
it comes from nor the topic it covers, so it matches no query about « césure ».
The fix (Anthropic, sept. 2024) is to prefix every chunk with a short LLM-generated
sentence situating it in its document, **before** embedding and BM25 indexing —
published effect: -49 % retrieval failures (contextual embeddings + contextual
BM25), -67 % with reranking on top.

PRD §5.3.1 designates it as the V2.1 candidate n°1. Like the RRF fusion and the
query rewriting before it, this is built to be **measured first**: contextualised
chunks go into a *parallel* collection (``--collection``), the production one is
never touched, and ``eval/contextual_retrieval_experiment.py`` compares the two.

Two properties matter for the measurement to mean anything:

* the generated context is stored separately (``metadata["context"]``) and the
  original chunk text is preserved verbatim (``metadata["text_raw"]``), so the
  evaluation can test its hit condition against the ORIGINAL text — a context
  sentence that happens to contain « césure » must not count as a retrieval win;
* generation is cached on disk, keyed by the chunk's *content* (see
  :func:`context_key`), so a re-run costs nothing while a re-cut corpus is never
  served contexts written for other spans.

Reference: https://www.anthropic.com/engineering/contextual-retrieval
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

from .. import backoff
from ..config import PROJECT_ROOT
from ..models import Chunk, Document

if TYPE_CHECKING:  # backend is used duck-typed at runtime (same as rewrite.py)
    from ..generation.llm import LLMBackend

CACHE_PATH = PROJECT_ROOT / "corpus" / "contexts.jsonl"

# Bump when CONTEXT_SYSTEM or the user template changes: cached entries carrying
# an older version are ignored rather than silently mixed with new ones.
PROMPT_VERSION = 2

# Fallback only, for a backend that does not publish its window. A guard fixed in
# characters cannot do the job it was written for: at 60 000 characters (~14k
# tokens) it could never fire on this corpus, whose largest document is 40 144
# characters for 9 587 tokens — while a local backend at num_ctx=8192 would drop
# that document's tail without a word. The budget is therefore derived from the
# backend's real window (see :func:`document_char_budget`).
MAX_DOC_CHARS = 60_000

# French administrative prose runs ~3.5 characters per token with the Mistral and
# Llama tokenizers. Deliberately low: underestimating the ratio shrinks the
# budget, which errs towards warning too often rather than too late.
CHARS_PER_TOKEN = 3.5

# Head-room left inside the window for the system prompt, the chunk being
# situated, the template and the generated sentence.
RESERVED_TOKENS = 1_200

# The prompt asks for at most 25 words (prompts/context_system.md). The model
# does not reliably obey — 48 % of the 433 cached contexts exceed it, up to 45
# words. Contexts are NOT truncated here: cutting a nominal sentence mid-way
# would damage it, and would silently change contexts already measured and
# published. The overrun is counted and reported instead, so the gap between the
# instruction and what the model does is visible rather than absorbed.
MAX_CONTEXT_WORDS = 25

# The system prompt lives in prompts/ like the RAG and condensation ones, and its
# iterations are logged in prompts/CHANGELOG.md (PRD §11.10).
CONTEXT_SYSTEM = (PROJECT_ROOT / "prompts" / "context_system.md").read_text(
    encoding="utf-8"
).strip()

USER_TEMPLATE = """<document titre="{title}">
{document}
</document>

Situe l'extrait suivant dans ce document :

<extrait>
{chunk}
</extrait>"""

# Batch-level resilience now lives in assistant_amu.backoff, shared with the
# rewriting experiment (the two copies had drifted to different delays, and only
# this one was testable). Re-exported: callers and tests referred to these names.
RETRY_CAUSES = backoff.RETRY_CAUSES
RETRY_DELAYS = backoff.RETRY_DELAYS


def document_char_budget(backend: "LLMBackend") -> int:
    """Character budget for the document, derived from the backend's real window.

    A backend that publishes no window falls back to :data:`MAX_DOC_CHARS`.
    """
    window = int(getattr(backend, "context_window", 0) or 0)
    if window <= 0:
        return MAX_DOC_CHARS
    return int(max(window - RESERVED_TOKENS, 0) * CHARS_PER_TOKEN)


def count_words(context: str) -> int:
    return len(context.split())


@dataclass
class ContextReport:
    """Outcome of a contextualisation batch."""

    generated: int = 0
    cached: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)  # (chunk_id, reason)
    truncated_docs: list[str] = field(default_factory=list)
    over_word_limit: list[tuple[str, int]] = field(default_factory=list)  # (chunk_id, words)

    @property
    def total(self) -> int:
        return self.generated + self.cached + len(self.failed)

    def summary(self) -> str:
        line = (
            f"contexts: {self.generated} generated | {self.cached} from cache | "
            f"{len(self.failed)} failed (chunk kept as-is)"
        )
        if self.over_word_limit:
            longest = max(words for _, words in self.over_word_limit)
            line += (
                f" | {len(self.over_word_limit)}/{self.total} over the "
                f"{MAX_CONTEXT_WORDS}-word prompt ceiling (longest: {longest})"
            )
        return line


def context_key(chunk: Chunk) -> str:
    """Content address of a chunk — what its context actually depends on.

    NOT ``chunk_id``: that one is ``sha256(doc_id:chunk_index)`` (``chunk.py``), so
    it survives a change of chunking budget while the text underneath changes. A
    cache keyed on it hands back, on a re-cut corpus, contexts written for other
    spans — silently, and with a reassuring "from cache" count.
    """
    return hashlib.sha256(f"{chunk.doc_id}:{chunk.text}".encode()).hexdigest()[:16]


class ContextCache:
    """Append-only JSONL cache of generated contexts.

    Keyed by (content address, model, prompt version), so a context is only ever
    replayed for the exact text it was written for. Not versioned in git (like
    ``chroma_db/``): derived data, regenerated by re-running the command.
    """

    def __init__(self, path: Path | str = CACHE_PATH):
        self.path = Path(path)
        self._entries: dict[tuple[str, str, int], str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                # Records without "key" predate content addressing: ignored rather
                # than trusted, since their key said nothing about their text.
                key = (record["key"], record["model"], int(record["prompt_version"]))
                # Read INSIDE the try: a record carrying every key but "context"
                # used to raise here and lose the entire cache, defeating the
                # guarantee the comment below states.
                context = record["context"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # one damaged line must not lose the whole cache
            self._entries[key] = context

    def get(self, key: str, model: str) -> str | None:
        return self._entries.get((key, model, PROMPT_VERSION))

    def put(self, key: str, chunk_id: str, doc_id: str, model: str, context: str) -> None:
        self._entries[(key, model, PROMPT_VERSION)] = context
        record = {
            "key": key,
            "chunk_id": chunk_id,  # kept for readability when inspecting the file
            "doc_id": doc_id,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "context": context,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def __len__(self) -> int:
        return len(self._entries)


def contextual_collection_name(base: str) -> str:
    """Name of the parallel collection holding the contextualised chunks."""
    return f"{base}_ctx"


def build_user_prompt(document: str, chunk_text: str, title: str) -> str:
    """Render the user message: document first, chunk last.

    Same ordering principle as the RAG prompt (§7.4): the long context leads, the
    instruction-bearing part closes — better instruction-following on long inputs.
    """
    return USER_TEMPLATE.format(title=title, document=document, chunk=chunk_text)


def clean_context(raw: str) -> str:
    """Keep the first non-empty line, stripped of quoting and trailing noise."""
    for line in raw.strip().splitlines():
        cleaned = line.strip().strip("«»\"'").strip()
        if cleaned:
            return cleaned
    return ""


def contextualized_chunk(chunk: Chunk, context: str) -> Chunk:
    """Return a copy of ``chunk`` prefixed with ``context``.

    The original text is preserved in ``metadata["text_raw"]`` and the generated
    sentence in ``metadata["context"]``: the evaluation matches its expected
    keywords against the ORIGINAL text, so a context sentence quoting the keyword
    cannot manufacture a hit.
    """
    if not context:
        return chunk
    return Chunk(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        text=f"{context}\n\n{chunk.text}",
        metadata={**chunk.metadata, "context": context, "text_raw": chunk.text},
    )


def generate_context(
    backend: "LLMBackend",
    document: str,
    chunk_text: str,
    title: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Generate one situating sentence, retrying transient backend failures."""
    user = build_user_prompt(document, chunk_text, title)
    return backoff.with_retry(
        lambda: clean_context(backend.generate(CONTEXT_SYSTEM, user)), sleep=sleep
    )


def contextualize_chunks(
    chunks: Iterable[Chunk],
    documents: Iterable[Document],
    backend: "LLMBackend",
    *,
    cache: ContextCache | None = None,
    max_doc_chars: int | None = None,
    progress: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[Chunk], ContextReport]:
    """Prefix every chunk with an LLM-generated context sentence.

    A chunk whose generation fails is kept **unchanged** rather than dropped, and
    counted in the report: a partial outage degrades the index visibly instead of
    silently shipping a half-contextual collection.

    ``max_doc_chars`` defaults to the budget the *backend's own window* allows, so
    the truncation warning can actually fire on a local backend — which is what it
    was written for.
    """
    from ..generation.llm import LLMBackendError

    cache = cache if cache is not None else ContextCache()
    budget = document_char_budget(backend) if max_doc_chars is None else max_doc_chars
    texts = _document_texts(documents, budget)
    report = ContextReport(
        truncated_docs=sorted(title for title, was_cut, _ in texts.values() if was_cut)
    )
    model = getattr(backend, "name", "unknown")

    def note_length(chunk_id: str, context: str) -> None:
        words = count_words(context)
        if words > MAX_CONTEXT_WORDS:
            report.over_word_limit.append((chunk_id, words))

    def situate(chunk: Chunk) -> Chunk:
        """Contextualise one chunk, recording its outcome in the report."""
        key = context_key(chunk)
        context = cache.get(key, model)
        if context is not None:
            report.cached += 1
            note_length(chunk.chunk_id, context)
            return contextualized_chunk(chunk, context)

        entry = texts.get(chunk.doc_id)
        if entry is None:  # chunk from a document not in the batch: nothing to situate it in
            report.failed.append((chunk.chunk_id, "document text unavailable"))
            return chunk

        title = str(chunk.metadata.get("source_title", entry[0]))
        try:
            context = generate_context(backend, entry[2], chunk.text, title, sleep=sleep)
        except LLMBackendError as exc:
            report.failed.append((chunk.chunk_id, f"{exc.cause}: {exc}"))
            return chunk

        if not context:
            report.failed.append((chunk.chunk_id, "empty context returned"))
            return chunk

        cache.put(key, chunk.chunk_id, chunk.doc_id, model, context)
        report.generated += 1
        note_length(chunk.chunk_id, context)
        return contextualized_chunk(chunk, context)

    out: list[Chunk] = []
    chunks = list(chunks)
    for index, chunk in enumerate(chunks, start=1):
        out.append(situate(chunk))
        # Reporting lives OUTSIDE the per-chunk branches. Placed inside the
        # generation one, a fully cached batch printed nothing at all, and the
        # closing line never fired when the last chunk came from the cache.
        if index % 20 == 0 or index == len(chunks):
            progress(f"    {index}/{len(chunks)} chunks — {report.summary()}")

    return out, report


def _document_texts(
    documents: Iterable[Document], max_doc_chars: int
) -> dict[str, tuple[str, bool, str]]:
    """Map doc_id -> (title, was_truncated, text), truncating oversized documents."""
    texts: dict[str, tuple[str, bool, str]] = {}
    for doc in documents:
        text = doc.text
        was_cut = len(text) > max_doc_chars
        texts[doc.doc_id] = (doc.title, was_cut, text[:max_doc_chars] if was_cut else text)
    return texts
