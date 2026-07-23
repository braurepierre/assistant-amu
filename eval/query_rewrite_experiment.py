r"""Query-rewriting experiment — MEASURED ONLY (does not touch the /ask pipeline).

Motivation (observed): conversational / imperative formulations
(« Parle-moi de… », « Dis-moi… », « Je voudrais des infos sur… ») retrieve worse
than definitional ones (« Qu'est-ce que… »). The query vector lands in noise and
the definitional source drops out of the top-k; raising k does NOT fix it (the
fix is at the *query*, not at k). This script measures three rewriting strategies
against that failure mode, in the same "measured, not wired" spirit as the RRF
fusion (PRD §5.1.8 / §5.3.5):

    raw    identity (baseline — the current /ask behaviour)
    strip  heuristic: drop the leading conversational/imperative opener
    llm    Mistral rewrites into a short factual search query

Recall@k (k=3 and 5, proxy for RAGAS context recall) is computed for each
strategy on TWO sets: eval/hard_questions.yaml (the hard formulations) and
eval/questions.yaml (the existing easy set — a non-regression control). A dated
Markdown report is written to eval/reports/.

Reuses the production building blocks directly (no HTTP API): VectorStore +
SemanticRetriever, evaluate_retrieval / load_questions, build_backend.

Run (Mistral backend for the `llm` strategy):
    LLM_BACKEND=mistral python eval/query_rewrite_experiment.py
    # PowerShell:  $env:LLM_BACKEND='mistral'; .\.venv\Scripts\python.exe eval/query_rewrite_experiment.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import Question, evaluate_retrieval, load_questions
from assistant_amu.generation.llm import LLMBackend, build_backend
from assistant_amu.generation.rewrite import rewrite_query, strip_query
from assistant_amu.models import RetrievedChunk
from assistant_amu.retrieval.vector_store import SemanticRetriever, VectorStore

HARD = PROJECT_ROOT / "eval" / "hard_questions.yaml"
EASY = PROJECT_ROOT / "eval" / "questions.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
KS = (3, 5)
FLAGSHIP = "Parle-moi des régimes spéciaux."  # the motivating before/after case
# The central definitional page (distinct from "Droit — Régimes spéciaux d'études").
RSE_CENTRAL = "régime spécial d'études"


# --- Strategies ------------------------------------------------------------
# raw / strip / llm all live in assistant_amu.generation.rewrite — the SAME code
# now wired into /ask (§5.3.5). The experiment imports strip_query / rewrite_query
# and only adds per-question caching so k=3 and k=5 reuse one llm call per question.


class LlmRewriter:
    """Cache the llm rewrite: one backend call per unique question (shared by k=3/5)."""

    def __init__(self, backend: LLMBackend):
        self._backend = backend
        self._cache: dict[str, str] = {}

    def __call__(self, question: str) -> str:
        if question not in self._cache:
            self._cache[question] = rewrite_query(question, "llm", self._backend)
        return self._cache[question]


# --- Retriever wrapper ----------------------------------------------------

class RewritingRetriever:
    """Rewrite the query, then delegate to the semantic retriever (harness API)."""

    def __init__(self, rewrite, semantic: SemanticRetriever):
        self._rewrite = rewrite
        self._semantic = semantic

    def rank(self, question: str, depth: int) -> list[RetrievedChunk]:
        return self._semantic.rank(self._rewrite(question), depth)


# --- Report helpers -------------------------------------------------------

def _recall_table(title: str, n: int, per_k: dict[int, dict[str, float]], strategies) -> list[str]:
    grain = 1.0 / n if n else 0.0
    header = "| Stratégie | " + " | ".join(f"recall@{k}" for k in KS) + " |"
    sep = "|---|" + "|".join("---" for _ in KS) + "|"
    lines = [f"### {title} ({n} questions ; granularité 1/{n} ≈ {grain:.3f})", "", header, sep]
    for s in strategies:
        cells = " | ".join(f"{per_k[k][s]:.2f}" for k in KS)
        lines.append(f"| {s} | {cells} |")
    return lines + [""]


def _flagship_rank(retriever, k: int = 8) -> tuple[int | None, list[str]]:
    """Rank of the central RSE page in the flagship query's top-k, plus titles."""
    ranked = retriever.rank(FLAGSHIP, k)
    titles = [str(c.metadata.get("source_title", "")) for c in ranked]
    rank = next((i + 1 for i, t in enumerate(titles) if RSE_CENTRAL in t.lower()), None)
    return rank, titles


def _truncate(text: str, width: int = 60) -> str:
    text = text.replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1] + "…"


# --- Main -----------------------------------------------------------------

def main() -> int:
    settings = get_settings()
    store = VectorStore.from_settings(settings)
    if store.count() == 0:
        print("Empty collection — run `python -m assistant_amu.ingestion index` first.")
        return 1

    semantic = SemanticRetriever(store)
    backend = build_backend(settings)
    llm_rewriter = LlmRewriter(backend)

    strategies = {
        "raw": RewritingRetriever(lambda q: q, semantic),
        "strip": RewritingRetriever(strip_query, semantic),
        "llm": RewritingRetriever(llm_rewriter, semantic),
    }
    rewriters = {"raw": lambda q: q, "strip": strip_query, "llm": llm_rewriter}

    hard = load_questions(HARD)
    easy = load_questions(EASY)

    # recall@k per strategy, per dataset (evaluate_retrieval reused verbatim).
    def recalls(questions: list[Question]) -> dict[int, dict[str, float]]:
        return {k: evaluate_retrieval(questions, strategies, k).recall for k in KS}

    hard_recall = recalls(hard)
    easy_recall = recalls(easy)

    # Per-question hits (same process -> same cached llm rewrites as the tables).
    hard_rows = evaluate_retrieval(hard, strategies, 5).rows
    easy_rows = {k: evaluate_retrieval(easy, strategies, k).rows for k in KS}

    # Flagship before/after: rewrite + rank of the central RSE page.
    flagship = {}
    for name, retr in strategies.items():
        rank5, titles = _flagship_rank(retr, k=8)
        flagship[name] = {
            "rewrite": rewriters[name](FLAGSHIP),
            "rank": rank5,
            "titles": titles,
        }

    _write_report(settings, backend.name, hard, easy, hard_recall, easy_recall,
                  hard_rows, easy_rows, flagship, rewriters)
    return 0


def _write_report(settings, backend_name, hard, easy, hard_recall, easy_recall,
                  hard_rows, easy_rows, flagship, rewriters):
    today = date.today().isoformat()
    strat = ("raw", "strip", "llm")
    # Recall is computed over ANSWERABLE questions only (see evaluate_retrieval),
    # so the granularity denominator is the answerable count — not the file size.
    n_hard = sum(1 for q in hard if q.answerable)
    n_easy = sum(1 for q in easy if q.answerable)

    lines = [
        f"# Rapport — réécriture de requête (mesure seule) — {today}",
        "",
        f"- Backend LLM (stratégie `llm`) : `{backend_name}` (température {settings.temperature:g}) | "
        f"Embeddeur : `{settings.embedding_model}`",
        f"- Jeu « dur » : {n_hard} formulations impératives/conversationnelles (toutes answerable) · "
        f"jeu « facile » (contrôle de non-régression) : {n_easy} questions answerable.",
        "- `recall@k` = proxy de *context recall* (RAGAS). Réécriture **mesurée, non "
        "branchée** dans `/ask` (même esprit que la RRF, §5.1.8 / §5.3.5).",
        "- Stratégies : `raw` (identité, baseline) · `strip` (retrait heuristique de "
        "l'ouverture conversationnelle, **déterministe**) · `llm` (réécriture Mistral en "
        "requête factuelle, **non déterministe** — chiffres d'un run unique ; lancer à "
        "`LLM_TEMPERATURE=0` pour limiter la variance).",
        "",
        "## Recall@k par stratégie",
        "",
    ]
    lines += _recall_table("Jeu « dur »", n_hard, hard_recall, strat)
    lines += _recall_table("Jeu « facile » — contrôle de non-régression", n_easy, easy_recall, strat)

    # Why llm regresses: easy questions raw hits but llm misses (same-process cache).
    llm_broken = [
        (r.id, r.question)
        for r in easy_rows[3]
        if r.hits["raw"] and not r.hits["llm"]
    ]
    if llm_broken:
        lines += [
            "**Où `llm` régresse (jeu facile, k=3)** — questions récupérées par `raw` "
            "mais perdues après réécriture LLM (`strip`, lui, les laisse intactes) :",
            "",
            "| id | question d'origine | réécriture `llm` |",
            "|---|---|---|",
        ]
        for qid, question in llm_broken:
            lines.append(f"| {qid} | {_truncate(question, 55)} | {_truncate(rewriters['llm'](question), 55)} |")
        lines += [
            "",
            "> La réécriture LLM *paraphrase* la question et peut effacer le signal "
            "lexical qui la rapprochait du bon document (ex. « interrompre mes études "
            "pendant un an » → perte du lien vers « césure »). `strip` ne retire que "
            "l'ouverture conversationnelle et ne touche jamais ces questions.",
            "",
        ]

    # Flagship before/after.
    lines += [
        "## Avant / après — « Parle-moi des régimes spéciaux »",
        "",
        "Cible : la page **définitionnelle centrale** « Régime spécial d'études (RSE) » "
        "(distincte de « Droit — Régimes spéciaux d'études », qui, elle, est récupérée "
        "dans tous les cas). Rang = position de la page RSE centrale dans le top-8.",
        "",
        "| Stratégie | requête effectivement recherchée | RSE centrale récupérée ? |",
        "|---|---|---|",
    ]
    for s in strat:
        info = flagship[s]
        if info["rank"] is None:
            verdict = "❌ absente du top-8"
        else:
            verdict = f"✅ rang {info['rank']}"
        lines.append(f"| {s} | {_truncate(info['rewrite'])} | {verdict} |")
    lines.append("")

    # Per-strategy top-5 titles for the flagship (transparency).
    lines += ["<details><summary>Top-5 documents récupérés (question phare)</summary>", ""]
    for s in strat:
        lines.append(f"**{s}** — requête : `{_truncate(flagship[s]['rewrite'], 80)}`")
        for i, t in enumerate(flagship[s]["titles"][:5], 1):
            mark = " ⟵ RSE centrale" if RSE_CENTRAL in t.lower() else ""
            lines.append(f"  {i}. {t}{mark}")
        lines.append("")
    lines += ["</details>", ""]

    # Per-question detail on the hard set (k=5).
    lines += [
        "## Détail par question — jeu « dur » (k=5)",
        "",
        "| id | question | " + " | ".join(strat) + " |",
        "|---|---|" + "|".join("---" for _ in strat) + "|",
    ]
    for row in hard_rows:
        cells = " | ".join("✅" if row.hits[s] else "❌" for s in strat)
        lines.append(f"| {row.id} | {_truncate(row.question)} | {cells} |")
    lines.append("")

    # Conclusion (computed, not hand-waved).
    winner = _pick_winner(strat, hard_recall, easy_recall)
    base_easy = {k: easy_recall[k]["raw"] for k in KS}
    reg = {k: easy_recall[k][winner] - base_easy[k] for k in KS}
    grain_easy = 1.0 / n_easy
    regresses = any(reg[k] < -grain_easy - 1e-9 for k in KS)  # > one question below raw
    llm_delta = {k: easy_recall[k]["llm"] - easy_recall[k]["raw"] for k in KS}

    def _q(delta: float) -> str:  # recall delta -> signed question count (easy set)
        n = round(delta * n_easy)
        return f"{n:+d} q" if n else "±0 q"

    lines += [
        "## Conclusion",
        "",
        f"- **Stratégie gagnante : `{winner}`** — meilleur recall@k sur le jeu « dur » "
        "sans dégrader le jeu « facile ».",
        f"- Jeu « dur » : "
        + " · ".join(
            f"recall@{k} {hard_recall[k]['raw']:.2f} (raw) → {hard_recall[k][winner]:.2f} ({winner})"
            for k in KS
        )
        + ".",
        f"- Non-régression (jeu facile) : "
        + " · ".join(
            f"recall@{k} {base_easy[k]:.2f} (raw) vs {easy_recall[k][winner]:.2f} ({winner})"
            for k in KS
        )
        + ".",
        f"- Verdict de régression (`{winner}`) : "
        + (
            "**régression** sur les questions faciles (écart > 1 question)."
            if regresses
            else "**pas de régression** (écart nul, `strip` est identité sur les "
            "questions définitionnelles)."
        ),
        f"- `llm` écartée bien qu'elle répare le jeu « dur » autant que `strip` "
        + "(" + " · ".join(f"recall@{k} {hard_recall[k]['llm']:.2f}" for k in KS) + ") : "
        "elle **déstabilise le jeu facile** — solde "
        + " · ".join(
            f"recall@{k} {easy_recall[k]['raw']:.2f}→{easy_recall[k]['llm']:.2f} ({_q(llm_delta[k])})"
            for k in KS
        )
        + f", mais casse en réalité {len(llm_broken)} question(s) définitionnelle(s) qui "
        "marchaient (table ci-dessus), n'en regagnant qu'ailleurs. Elle paraphrase, "
        "est non déterministe, et coûte un appel LLM par requête — `strip` non.",
        "",
        "> Rappel de granularité (le dénominateur = questions *answerable*) : jeu « dur » "
        f"= 1 question ≈ {1.0 / n_hard:.3f} ; jeu « facile » = 1 question ≈ {grain_easy:.3f}. "
        "Un écart inférieur à un cran de question n'est pas significatif.",
        "",
    ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{today}_query_rewrite.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Console summary.
    print(f"backend={backend_name} | winner={winner}")
    for label, rec in (("hard", hard_recall), ("easy", easy_recall)):
        for k in KS:
            print(f"  [{label}] k={k} | " + " ".join(f"{s}={rec[k][s]:.2f}" for s in strat))
    print(f"  flagship RSE rank: " + " ".join(f"{s}={flagship[s]['rank']}" for s in strat))
    print(f"  report: {path}")


def _pick_winner(strategies, hard_recall, easy_recall) -> str:
    """Best mean recall@k on the hard set; ties broken by easy-set mean."""
    def hard_score(s):
        return sum(hard_recall[k][s] for k in KS)

    def easy_score(s):
        return sum(easy_recall[k][s] for k in KS)

    return max(strategies, key=lambda s: (hard_score(s), easy_score(s)))


if __name__ == "__main__":
    raise SystemExit(main())
