"""Evaluation harness logic (PRD §7.6, F8).

Pure, importable pieces so they can be unit-tested without a real corpus, model
or LLM: question loading, expected-chunk matching, Reciprocal Rank Fusion, recall
computation, and Markdown report rendering. The CLI wiring (building the real
semantic/BM25 retrievers and the pipeline) lives in ``eval/evaluate.py``.

Terminology follows RAGAS: recall@k is a proxy for *context recall*; the manual
"fidélité" column corresponds to *faithfulness* (§7.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

import yaml

from .generation.rag import is_refusal
from .models import RetrievedChunk

RRF_K = 60  # standard RRF constant (score = sum 1 / (RRF_K + rank))


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    question: str
    answerable: bool
    expected_source: str | None = None
    expected_keywords: list[str] = field(default_factory=list)


def load_questions(path: Path | str) -> list[Question]:
    """Parse eval/questions.yaml into :class:`Question` objects."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = data.get("questions", [])
    questions: list[Question] = []
    for entry in entries:
        questions.append(
            Question(
                id=str(entry["id"]),
                question=str(entry["question"]),
                answerable=bool(entry["answerable"]),
                expected_source=entry.get("expected_source"),
                expected_keywords=list(entry.get("expected_keywords", []) or []),
            )
        )
    return questions


def chunk_matches(
    text: str, metadata: dict, expected_source: str | None, expected_keywords: list[str]
) -> bool:
    """True if a chunk is the expected one: right source AND all keywords present."""
    if expected_source:
        title = str(metadata.get("source_title", "")).lower()
        if expected_source.lower() not in title:
            return False
    low = text.lower()
    return all(keyword.lower() in low for keyword in expected_keywords)


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Fuse ranked id lists by RRF; return ids ordered by descending fused score."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda item: scores[item], reverse=True)


class Retriever(Protocol):
    def rank(self, question: str, depth: int) -> list[RetrievedChunk]: ...


class RrfRetriever:
    """Fuses two base retrievers' rankings via RRF (measured only — §5.1.8)."""

    def __init__(
        self,
        semantic: Retriever,
        lexical: Retriever,
        lookup: dict[str, RetrievedChunk],
        fuse_depth: int = 50,
    ):
        self._semantic = semantic
        self._lexical = lexical
        self._lookup = lookup
        self._fuse_depth = fuse_depth

    def rank(self, question: str, depth: int) -> list[RetrievedChunk]:
        semantic_ids = [c.chunk_id for c in self._semantic.rank(question, self._fuse_depth)]
        lexical_ids = [c.chunk_id for c in self._lexical.rank(question, self._fuse_depth)]
        fused = reciprocal_rank_fusion([semantic_ids, lexical_ids])
        return [self._lookup[cid] for cid in fused[:depth] if cid in self._lookup]


# --- Strict counting over a contextualised index --------------------------
#
# These two live here, and not in the experiment script, because they carry the
# validity of the Contextual Retrieval measurement: retrieval runs on the
# contextualised text, but the hit condition must be evaluated on the ORIGINAL
# one, or a generated context quoting an expected keyword manufactures a hit.
# In the experiment script no test could reach them — a regression there would
# have silently inverted the published conclusions.

def with_raw_text(chunk: RetrievedChunk) -> RetrievedChunk:
    """Restore a chunk's pre-contextualisation text, when one was preserved.

    A chunk without ``metadata["text_raw"]`` — anything from a baseline, or a
    chunk whose contextualisation failed and was kept as-is — is returned
    unchanged, so a mixed collection degrades to the honest reading rather than
    raising.
    """
    raw = chunk.metadata.get("text_raw")
    return chunk if not raw else replace(chunk, text=str(raw))


class RawTextRetriever:
    """Delegate ranking, then restore each chunk's pre-contextualisation text.

    Ranking quality is the contextual index's — that is the whole point of the
    experiment; only what the hit condition reads is swapped back.
    """

    def __init__(self, inner: Retriever):
        self._inner = inner

    def rank(self, question: str, depth: int) -> list[RetrievedChunk]:
        return [with_raw_text(c) for c in self._inner.rank(question, depth)]


# --- Retrieval evaluation -------------------------------------------------

@dataclass
class RetrievalRow:
    id: str
    question: str
    hits: dict[str, bool]


@dataclass
class RetrievalReport:
    rows: list[RetrievalRow]
    recall: dict[str, float]
    disagreements: list[RetrievalRow]
    k: int
    n_answerable: int


def evaluate_retrieval(
    questions: list[Question], retrievers: dict[str, Retriever], k: int
) -> RetrievalReport:
    """Compute recall@k per method over the answerable questions."""
    answerable = [q for q in questions if q.answerable]
    rows: list[RetrievalRow] = []
    hit_counts = {method: 0 for method in retrievers}

    for q in answerable:
        hits: dict[str, bool] = {}
        for method, retriever in retrievers.items():
            ranked = retriever.rank(q.question, k)
            hit = any(
                chunk_matches(c.text, c.metadata, q.expected_source, q.expected_keywords)
                for c in ranked
            )
            hits[method] = hit
            hit_counts[method] += int(hit)
        rows.append(RetrievalRow(q.id, q.question, hits))

    n = len(answerable)
    recall = {m: (hit_counts[m] / n if n else 0.0) for m in retrievers}
    disagreements = [
        r for r in rows
        if "semantic" in r.hits and "bm25" in r.hits and r.hits["semantic"] != r.hits["bm25"]
    ]
    return RetrievalReport(rows, recall, disagreements, k, n)


# --- End-to-end evaluation ------------------------------------------------

@dataclass
class E2ERow:
    id: str
    question: str
    answerable: bool
    answer: str
    n_sources: int
    refusal_correct: bool | None  # only meaningful for non-answerable questions


class Pipeline(Protocol):
    def answer(self, question: str, k: int = 5): ...


def evaluate_end_to_end(questions: list[Question], pipeline: Pipeline, k: int) -> list[E2ERow]:
    """Run the full pipeline; check refusal on non-answerable questions (§7.6)."""
    rows: list[E2ERow] = []
    for q in questions:
        result = pipeline.answer(q.question, k=k)
        refusal_correct = is_refusal(result.answer) if not q.answerable else None
        rows.append(
            E2ERow(q.id, q.question, q.answerable, result.answer, len(result.sources), refusal_correct)
        )
    return rows


# --- Markdown report rendering --------------------------------------------

def render_retrieval_report(report: RetrievalReport, *, date: str, backend: str, model: str) -> str:
    methods = list(report.recall)
    lines = [
        f"# Rapport d'évaluation — retrieval — {date}",
        "",
        f"- Méthodes : {', '.join(methods)}",
        f"- k = {report.k} | questions answerable = {report.n_answerable}",
        f"- Backend LLM : `{backend}` | Modèle d'embedding : `{model}`",
        "",
        "## Recall@k (proxy de *context recall*, RAGAS)",
        "",
        "| Méthode | Recall@k |",
        "|---|---|",
    ]
    lines += [f"| {m} | {report.recall[m]:.2f} |" for m in methods]

    lines += ["", "## Détail par question", "", "| id | question | " + " | ".join(methods) + " |",
              "|---|---|" + "|".join("---" for _ in methods) + "|"]
    for row in report.rows:
        cells = " | ".join("✅" if row.hits[m] else "❌" for m in methods)
        lines.append(f"| {row.id} | {_truncate(row.question)} | {cells} |")

    lines += ["", "## Désaccords sémantique vs BM25", ""]
    if not report.disagreements:
        lines.append("_Aucun désaccord sur ce jeu._")
    else:
        lines.append("| id | question | trouvé par |")
        lines.append("|---|---|---|")
        for row in report.disagreements:
            finder = "semantic" if row.hits["semantic"] else "bm25"
            lines.append(f"| {row.id} | {_truncate(row.question)} | {finder} |")
    return "\n".join(lines) + "\n"


def render_end_to_end_report(rows: list[E2ERow], *, date: str, backend: str, k: int) -> str:
    non_answerable = [r for r in rows if not r.answerable]
    correct = sum(1 for r in non_answerable if r.refusal_correct)
    lines = [
        f"# Rapport d'évaluation — end-to-end — {date}",
        "",
        f"- Backend LLM : `{backend}` | k = {k}",
        f"- Taux de refus correct (non-answerable) : {correct}/{len(non_answerable)}",
        "",
        "## Réponses",
        "",
        "| id | answerable | refus correct | #sources | fidélité (à remplir) | réponse |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        refusal = "—" if r.refusal_correct is None else ("✅" if r.refusal_correct else "❌")
        lines.append(
            f"| {r.id} | {'oui' if r.answerable else 'non'} | {refusal} | {r.n_sources} |  | "
            f"{_truncate(r.answer, 120)} |"
        )
    lines += ["", "> Colonne *fidélité* = faithfulness RAGAS, jugée manuellement (§7.6)."]
    return "\n".join(lines) + "\n"


def _truncate(text: str, width: int = 70) -> str:
    text = text.replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1] + "…"


# --- V2 conversational evaluation (§7.7, F12) -----------------------------

@dataclass(frozen=True, slots=True)
class Turn:
    question: str
    answerable: bool
    expected_source: str | None = None
    expected_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    turns: list[Turn]


def load_scenarios(path: Path | str) -> list[Scenario]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    scenarios: list[Scenario] = []
    for entry in data.get("scenarios", []):
        turns = [
            Turn(
                question=str(t["question"]),
                answerable=bool(t["answerable"]),
                expected_source=t.get("expected_source"),
                expected_keywords=list(t.get("expected_keywords", []) or []),
            )
            for t in entry.get("turns", [])
        ]
        scenarios.append(Scenario(id=str(entry["id"]), turns=turns))
    return scenarios


@dataclass
class ConversationRow:
    scenario_id: str
    turn: int
    question: str
    condensed_question: str | None
    recall_hit: bool
    refusal_correct: bool | None
    answer: str


def evaluate_conversation(scenarios: list[Scenario], pipeline: Pipeline, k: int) -> list[ConversationRow]:
    """Replay each scenario, threading history, measuring recall per turn (§7.7)."""
    rows: list[ConversationRow] = []
    for scenario in scenarios:
        history: list[dict] = []
        for index, turn in enumerate(scenario.turns, start=1):
            result = pipeline.answer(turn.question, k=k, history=history or None)
            hit = turn.answerable and any(
                chunk_matches(s.text, s.metadata, turn.expected_source, turn.expected_keywords)
                for s in result.sources
            )
            refusal_correct = is_refusal(result.answer) if not turn.answerable else None
            rows.append(
                ConversationRow(scenario.id, index, turn.question, result.condensed_question,
                                hit, refusal_correct, result.answer)
            )
            history.append({"role": "user", "content": turn.question})
            history.append({"role": "assistant", "content": result.answer})
    return rows


def render_conversation_report(rows: list[ConversationRow], *, date: str, backend: str, k: int) -> str:
    answerable = [r for r in rows if r.refusal_correct is None]
    hits = sum(1 for r in answerable if r.recall_hit)
    lines = [
        f"# Rapport d'évaluation — conversation (V2) — {date}",
        "",
        f"- Backend LLM : `{backend}` | k = {k}",
        f"- Recall des tours answerable : {hits}/{len(answerable)}",
        "",
        "| scénario | tour | question | question condensée | recall | refus | condensation OK (man.) | fidélité (man.) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        recall = "—" if r.refusal_correct is not None else ("✅" if r.recall_hit else "❌")
        refusal = "—" if r.refusal_correct is None else ("✅" if r.refusal_correct else "❌")
        lines.append(
            f"| {r.scenario_id} | {r.turn} | {_truncate(r.question, 40)} | "
            f"{_truncate(r.condensed_question or '—', 40)} | {recall} | {refusal} |  |  |"
        )
    lines += ["", "> Colonnes *condensation OK* et *fidélité* : jugement manuel (§7.7)."]
    return "\n".join(lines) + "\n"
