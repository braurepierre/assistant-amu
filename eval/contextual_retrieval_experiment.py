r"""Contextual Retrieval experiment — MEASURED ONLY (does not touch the /ask pipeline).

Compares the production index against a parallel index whose chunks were each
prefixed, at indexing time, with an LLM-generated sentence situating them in
their document (PRD §5.3.1, Anthropic sept. 2024). Both the embeddings and the
BM25 index of that second collection are therefore *contextual*, which is the
configuration Anthropic credits with -49 % retrieval failures.

Measured on the same two sets as the query-rewriting experiment: the easy set
(eval/questions.yaml, definitional phrasings) and the hard set
(eval/hard_questions.yaml, conversational phrasings), at k = 3 and 5, for the
three methods (semantic / BM25 / RRF). A dated Markdown report goes to
eval/reports/.

MEASUREMENT VALIDITY — the point that decides whether the numbers mean anything.
The easy set annotates ``expected_keywords`` (« césure », « RSE »…) that must
appear *in the retrieved chunk*. A generated context routinely names the topic
of its own chunk, so scoring against the contextualised text would count « the
context sentence says césure » as a retrieval win and inflate recall for free.
Every retriever is therefore wrapped so that, after ranking, each chunk's text is
restored to the ORIGINAL one kept in ``metadata["text_raw"]``: the context helps
*find* the chunk, never *prove* the hit. The report also quantifies the artifact
by scoring the same rankings both ways ("strict" vs "naïf").

Prerequisites:
    python -m assistant_amu.ingestion index                  # baseline collection
    LLM_BACKEND=mistral python -m assistant_amu.ingestion contextualize   # _ctx collection

Run:
    python eval/contextual_retrieval_experiment.py
    # PowerShell:  .\.venv\Scripts\python.exe eval/contextual_retrieval_experiment.py

Any pair of collections can be compared, which is how the chunk budget is
controlled for: prefixing a chunk that already fills the encoder window pushes
its tail out of it, so the same comparison is run on a corpus re-cut with room
for the prefix.

    python -m assistant_amu.ingestion index --max-tokens 440 --collection amu_docs_440
    LLM_BACKEND=mistral python -m assistant_amu.ingestion contextualize \
        --max-tokens 440 --collection amu_docs_440_ctx
    python eval/contextual_retrieval_experiment.py \
        --baseline-collection amu_docs_440 --contextual-collection amu_docs_440_ctx --tag _440
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import (
    Question,
    RawTextRetriever,
    RetrievalRow,
    RrfRetriever,
    evaluate_retrieval,
    load_questions,
    with_raw_text,
)
from assistant_amu.ingestion.contextualize import contextual_collection_name
from assistant_amu.models import RetrievedChunk
from assistant_amu.retrieval.bm25_store import Bm25Index
from assistant_amu.retrieval.embedder import Embedder, prefixes_for
from assistant_amu.retrieval.vector_store import SemanticRetriever, VectorStore

HARD = PROJECT_ROOT / "eval" / "hard_questions.yaml"
EASY = PROJECT_ROOT / "eval" / "questions.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
KS = (3, 5)
METHODS = ("semantic", "bm25", "rrf")
FLAGSHIP = "Parle-moi des régimes spéciaux."  # the motivating case of the rewriting experiment
RSE_CENTRAL = "régime spécial d'études"

# Significance threshold, fixed BEFORE measuring and stated in the report — same
# bar as eval/reports/2026-07-26_corpus_scaling.md, which declares it up front.
# A gap below it is neither a gain nor a loss, whatever its sign.
SIGNIFICANCE_QUESTIONS = 3


# --- Retriever wrapper (measurement validity) ------------------------------
#
# RawTextRetriever and with_raw_text now live in assistant_amu.evaluation, where
# tests can reach them without a corpus: they carry the validity of this whole
# experiment, and no test covered them while they lived here. Re-exported under
# their former private names so the offline replay script keeps working.

_with_raw_text = with_raw_text


def _build_methods(store: VectorStore, *, strict: bool) -> dict[str, object]:
    """The three methods over one collection, optionally scored on raw text."""
    ids, docs, metas = store.get_all()
    semantic = SemanticRetriever(store)
    bm25 = Bm25Index(ids, docs, metas)
    lookup = {
        i: RetrievedChunk(i, str(m.get("doc_id", "")), d, m, 0.0)
        for i, d, m in zip(ids, docs, metas)
    }
    if strict:
        lookup = {i: _with_raw_text(c) for i, c in lookup.items()}
    # RRF fuses the *contextual* rankings; only the returned objects are swapped.
    rrf = RrfRetriever(semantic, bm25, lookup)
    if strict:
        semantic, bm25 = RawTextRetriever(semantic), RawTextRetriever(bm25)
    return {"semantic": semantic, "bm25": bm25, "rrf": rrf}


# --- Report helpers --------------------------------------------------------

def _matrix(title: str, n: int, recalls: dict[int, dict[str, float]]) -> list[str]:
    """Recall table: one row per method, baseline vs contextual at each k."""
    header = "| Méthode | " + " | ".join(
        f"baseline k={k} | contextuel k={k} | Δ k={k}" for k in KS
    ) + " |"
    sep = "|---|" + "|".join("---|---|---" for _ in KS) + "|"
    lines = [f"### {title} ({n} questions ; 1 question ≈ {1.0 / n:.3f})", "", header, sep]
    for method in METHODS:
        cells = []
        for k in KS:
            base = recalls[k][f"base_{method}"]
            ctx = recalls[k][f"ctx_{method}"]
            cells += [f"{base:.2f}", f"{ctx:.2f}", _delta(ctx - base, n)]
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    return lines + [""]


def _delta(delta: float, n: int) -> str:
    """Signed recall delta, expressed in questions (the only honest unit here)."""
    questions = round(delta * n)
    if abs(questions) == 0:
        return "±0"
    return f"{delta:+.2f} ({questions:+d} q)"


def _questions(n: int) -> str:
    """'1 question' / '4 questions' — the report published '(+4 question)' for a while."""
    return "question" if abs(n) <= 1 else "questions"


def _cells(n: int, adjective: str) -> str:
    """'1 cellule gagnante' / '8 cellules gagnantes'."""
    return f"cellule {adjective}" if abs(n) <= 1 else f"cellules {adjective}s"


def _truncate(text: str, width: int = 60) -> str:
    text = str(text).replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def _flagship_rank(retriever, k: int = 8) -> tuple[int | None, list[str]]:
    ranked = retriever.rank(FLAGSHIP, k)
    titles = [str(c.metadata.get("source_title", "")) for c in ranked]
    rank = next((i + 1 for i, t in enumerate(titles) if RSE_CENTRAL in t.lower()), None)
    return rank, titles


def _changed_rows(rows: list[RetrievalRow], method: str) -> tuple[list, list]:
    """Questions the contextual index wins, and those it loses, for one method."""
    won = [r for r in rows if not r.hits[f"base_{method}"] and r.hits[f"ctx_{method}"]]
    lost = [r for r in rows if r.hits[f"base_{method}"] and not r.hits[f"ctx_{method}"]]
    return won, lost


# --- Main ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    base_name = args.baseline_collection or settings.chroma_collection
    ctx_name = args.contextual_collection or contextual_collection_name(base_name)

    # One embedder for both collections: same weights, same prefixes, so the only
    # difference measured is the text that was indexed.
    embedder = Embedder(settings.embedding_model)
    base_store = VectorStore.from_settings(settings, embedder=embedder, collection_name=base_name)
    ctx_store = VectorStore.from_settings(settings, embedder=embedder, collection_name=ctx_name)

    if base_store.count() == 0:
        print(f"Empty collection {base_name!r} — run `python -m assistant_amu.ingestion index`.")
        return 1
    if ctx_store.count() == 0:
        print(f"Empty collection {ctx_name!r} — run `python -m assistant_amu.ingestion contextualize`.")
        return 1
    if ctx_store.count() != base_store.count():
        print(
            f"! collections differ in size: baseline={base_store.count()} "
            f"contextual={ctx_store.count()} — the comparison would not be like-for-like."
        )
        return 1

    strict = {f"base_{m}": r for m, r in _build_methods(base_store, strict=False).items()}
    strict |= {f"ctx_{m}": r for m, r in _build_methods(ctx_store, strict=True).items()}
    # Same rankings, scored on the contextualised text: quantifies the artifact.
    naive = {f"ctx_{m}": r for m, r in _build_methods(ctx_store, strict=False).items()}

    hard, easy = load_questions(HARD), load_questions(EASY)

    def recalls(questions: list[Question], retrievers: dict) -> dict[int, dict[str, float]]:
        return {k: evaluate_retrieval(questions, retrievers, k).recall for k in KS}

    hard_recall, easy_recall = recalls(hard, strict), recalls(easy, strict)
    easy_naive = recalls(easy, naive)  # keyword annotations live in the easy set only
    # Per-question tables at *every* k in KS, not only at 5: the headline figure of
    # this experiment is read at k=3, and while the tables existed only at k=5 no
    # document in the repository said which questions composed it.
    hard_rows = {k: evaluate_retrieval(hard, strict, k).rows for k in KS}
    easy_rows = {k: evaluate_retrieval(easy, strict, k).rows for k in KS}

    flagship = {
        name: _flagship_rank(strict[name])
        for name in ("base_semantic", "ctx_semantic", "base_bm25", "ctx_bm25")
    }

    ctx_stats = _context_stats(ctx_store)
    window = _window_stats(base_store, ctx_store, settings.embedding_model, embedder)
    _write_report(settings, base_name, ctx_name, hard, easy, hard_recall, easy_recall,
                  easy_naive, hard_rows, easy_rows, flagship, ctx_stats, window, args.tag)
    return 0


def _parse_args(argv: list[str] | None) -> "argparse.Namespace":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline-collection", default=None, help="default: the production one")
    parser.add_argument("--contextual-collection", default=None, help="default: <baseline>_ctx")
    parser.add_argument("--tag", default="", help="suffix appended to the report filename")
    return parser.parse_args(argv)


def _window_stats(base_store, ctx_store, model_name: str, embedder: Embedder) -> dict:
    """Count chunks that overflow the embedder's window, before and after.

    The chunker aims at 500 tokens *including* the ``passage: `` prefix, against
    a 512-token window: 12 tokens of margin. A ~25-word context sentence does not
    fit in it, so the tail of the longest chunks falls outside the encoder — the
    prefix is read, the end of the chunk is not.
    """
    from assistant_amu.ingestion.chunk import default_token_counter

    count = default_token_counter(model_name)
    prefix = prefixes_for(model_name).passage
    limit = int(embedder.model.max_seq_length)

    def measure(store) -> dict:
        _, docs, _ = store.get_all()
        lengths = [count(prefix + d) for d in docs]
        over = [length for length in lengths if length > limit]
        return {
            "over": len(over),
            "share": len(over) / len(lengths) if lengths else 0.0,
            "max": max(lengths) if lengths else 0,
            "lost": sum(length - limit for length in over),
        }

    return {"limit": limit, "base": measure(base_store), "ctx": measure(ctx_store)}


def _context_stats(store: VectorStore) -> dict:
    """Descriptive stats on the generated contexts (length, coverage)."""
    _, docs, metas = store.get_all()
    contexts = [str(m.get("context", "")) for m in metas]
    present = [c for c in contexts if c]
    words = [len(c.split()) for c in present]
    return {
        "chunks": len(docs),
        "with_context": len(present),
        "mean_words": sum(words) / len(words) if words else 0.0,
        "max_words": max(words) if words else 0,
        "sample": sorted(present, key=len)[len(present) // 2] if present else "",
    }


def _write_report(settings, base_name, ctx_name, hard, easy, hard_recall, easy_recall,
                  easy_naive, hard_rows, easy_rows, flagship, ctx_stats, window, tag) -> None:
    today = date.today().isoformat()
    n_hard = sum(1 for q in hard if q.answerable)
    n_easy = sum(1 for q in easy if q.answerable)

    lines = [
        f"# Rapport — Contextual Retrieval (mesure seule) — {today}",
        "",
        f"- Embeddeur : `{settings.embedding_model}` · collections comparées : "
        f"`{base_name}` (baseline) vs `{ctx_name}` (contextuelle) · "
        f"{ctx_stats['chunks']} fragments de part et d'autre.",
        f"- Contextes générés : {ctx_stats['with_context']}/{ctx_stats['chunks']} fragments, "
        f"{ctx_stats['mean_words']:.1f} mots en moyenne (maximum {ctx_stats['max_words']}). "
        f"Prompt : `prompts/context_system.md`.",
        "- Les deux index de la collection contextuelle sont contextuels : les "
        "embeddings **et** BM25 sont calculés sur le fragment préfixé — c'est la "
        "configuration à laquelle Anthropic attribue −49 % d'échecs de recherche.",
        "- Mesure seule : `/ask` reste branché sur la collection de production "
        "(même esprit que la RRF et la réécriture, §5.1.8 / §5.3.5).",
        "",
        "> **Règle de comptage.** Le contexte généré nomme presque toujours le sujet "
        "du fragment qu'il préfixe. Or le jeu « facile » exige la présence de "
        "mots-clés *dans le fragment récupéré* : compter sur le texte contextualisé "
        "reviendrait à valider « la phrase de contexte dit *césure* » comme une "
        "réussite de recherche. Le contexte sert donc à **trouver** le fragment, "
        "jamais à **prouver** la réussite : après classement, le texte de chaque "
        "fragment est ramené à sa version d'origine (`metadata[\"text_raw\"]`) avant "
        "le test. L'ampleur de l'artefact évité est chiffrée plus bas.",
        "",
        "## Recall@k — baseline contre contextuel",
        "",
    ]
    lines += _matrix("Jeu « dur » (formulations conversationnelles)", n_hard, hard_recall)
    lines += _matrix("Jeu « facile » (formulations définitionnelles)", n_easy, easy_recall)

    # The artifact, quantified.
    lines += [
        "## Ce que coûterait un comptage naïf",
        "",
        "Mêmes classements, même index contextuel : seule change la version du "
        "texte sur laquelle les mots-clés attendus sont cherchés (jeu « facile », "
        "seul à porter des `expected_keywords`).",
        "",
        "| Méthode | " + " | ".join(f"strict k={k} | naïf k={k} | écart" for k in KS) + " |",
        "|---|" + "|".join("---|---|---" for _ in KS) + "|",
    ]
    for method in METHODS:
        cells = []
        for k in KS:
            s = easy_recall[k][f"ctx_{method}"]
            nv = easy_naive[k][f"ctx_{method}"]
            cells += [f"{s:.2f}", f"{nv:.2f}", _delta(nv - s, n_easy)]
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "> L'écart mesure exactement la part de « réussite » qu'un comptage naïf "
        "aurait attribuée à la contextualisation sans qu'aucun fragment ne soit "
        "mieux trouvé. C'est le résultat méthodologique de cette expérience.",
        "",
    ]

    # Per-question movement, per method, per set AND per k — so every headline
    # figure is traceable to the questions that compose it.
    for label, rows_by_k in (("dur", hard_rows), ("facile", easy_rows)):
        for k in KS:
            lines += [f"## Détail par question — jeu « {label} », k={k}", ""]
            moved = False
            for method in METHODS:
                won, lost = _changed_rows(rows_by_k[k], method)
                if not won and not lost:
                    continue
                moved = True
                lines.append(f"**{method}** — gagnées : {len(won)} · perdues : {len(lost)}")
                lines.append("")
                lines.append("| id | question | baseline | contextuel |")
                lines.append("|---|---|---|---|")
                for row in won + lost:
                    lines.append(
                        f"| {row.id} | {_truncate(row.question)} | "
                        f"{'✅' if row.hits[f'base_{method}'] else '❌'} | "
                        f"{'✅' if row.hits[f'ctx_{method}'] else '❌'} |"
                    )
                lines.append("")
            if not moved:
                lines += [f"Aucune question ne change de statut sur ce jeu à k={k}.", ""]

    # Flagship case.
    lines += [
        "## Question phare — « Parle-moi des régimes spéciaux »",
        "",
        "Cible : la page définitionnelle centrale « Régime spécial d'études (RSE) ». "
        "Rang dans le top-8 (`—` = absente).",
        "",
        "| Index | sémantique | BM25 |",
        "|---|---|---|",
        f"| baseline | {_rank_cell(flagship['base_semantic'][0])} | {_rank_cell(flagship['base_bm25'][0])} |",
        f"| contextuel | {_rank_cell(flagship['ctx_semantic'][0])} | {_rank_cell(flagship['ctx_bm25'][0])} |",
        "",
    ]

    # Mechanical cost of the prefix on a fixed-window encoder.
    base_w, ctx_w = window["base"], window["ctx"]
    lines += [
        f"## Diagnostic — le préfixe tient-il dans la fenêtre de {window['limit']} tokens ?",
        "",
        f"Le contexte s'ajoute au budget de tokens du fragment : {ctx_stats['mean_words']:.1f} "
        "mots en moyenne ici. Un fragment déjà proche de la fenêtre de l'encodeur en "
        "sort donc, et **rien ne le signale à l'exécution** — le contexte est lu, la fin "
        "du fragment ne l'est pas. Ce contrôle vérifie que les écarts mesurés plus haut "
        "ne sont pas cet artefact.",
        "",
        "| Collection | fragments hors fenêtre | part | plus long fragment | tokens perdus |",
        "|---|---|---|---|---|",
        f"| baseline | {base_w['over']} | {base_w['share']:.0%} | {base_w['max']} | {base_w['lost']} |",
        f"| contextuelle | {ctx_w['over']} | {ctx_w['share']:.0%} | {ctx_w['max']} | {ctx_w['lost']} |",
        "",
        (
            f"> **Artefact présent.** {ctx_w['over']} fragments ({ctx_w['share']:.0%}) "
            f"débordent après contextualisation contre {base_w['over']} avant, pour "
            f"{ctx_w['lost']} tokens perdus au total. Les questions définitionnelles "
            "visent des fragments longs et précis, dont la queue sort désormais de la "
            "fenêtre : les chiffres ci-dessus mesurent donc la méthode **et** "
            "l'étroitesse de la marge de découpage. Lever la confusion demande de "
            "re-découper le corpus à budget réduit, puis de tout re-mesurer."
            if ctx_w["over"]
            else
            f"> **Artefact écarté.** Aucun fragment ne déborde de la fenêtre, ni avant "
            f"ni après contextualisation (le plus long atteint {ctx_w['max']} tokens sur "
            f"{window['limit']}). Le préfixe tient dans le budget : aucun écart mesuré "
            "plus haut ne peut être imputé à une troncature silencieuse."
        ),
        "",
    ]

    # Sample context, for inspection.
    if ctx_stats["sample"]:
        lines += [
            "<details><summary>Exemple de contexte généré (longueur médiane)</summary>",
            "",
            f"> {ctx_stats['sample']}",
            "",
            "</details>",
            "",
        ]

    lines += _conclusion(hard_recall, easy_recall, easy_naive, n_hard, n_easy, window)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{today}_contextual_retrieval{tag}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for label, rec in (("hard", hard_recall), ("easy", easy_recall)):
        for k in KS:
            cells = " ".join(
                f"{m}={rec[k][f'base_{m}']:.2f}->{rec[k][f'ctx_{m}']:.2f}" for m in METHODS
            )
            print(f"  [{label}] k={k} | {cells}")
    print(f"  report: {path}")


def _rank_cell(rank: int | None) -> str:
    return f"rang {rank}" if rank else "— (absente du top-8)"


def _conclusion(hard_recall, easy_recall, easy_naive, n_hard, n_easy, window) -> list[str]:
    """State the verdict from the numbers, naming the configuration each one comes from.

    Every figure below is an extremum over twelve non-comparable cells (two
    question sets x three methods x two values of k). Opposing a maximum to a
    minimum as if it were a balance would be wrong — a set winning 8 questions in
    one cell and losing 3 in eleven others would still read as a net win. So each
    figure is labelled with its cell, and a dispersion line carries the balance.
    """
    cells = [
        {
            "set": label,
            "method": m,
            "k": k,
            "delta": recalls[k][f"ctx_{m}"] - recalls[k][f"base_{m}"],
            "q": round((recalls[k][f"ctx_{m}"] - recalls[k][f"base_{m}"]) * n),
        }
        for label, recalls, n in (("dur", hard_recall, n_hard), ("facile", easy_recall, n_easy))
        for m in METHODS
        for k in KS
    ]

    def where(c: dict) -> str:
        return f"jeu « {c['set']} », `{c['method']}` à k={c['k']}"

    def amount(c: dict) -> str:
        return f"{c['delta']:+.2f} ({c['q']:+d} {_questions(c['q'])})"

    best = max(cells, key=lambda c: c["q"])
    worst = min(cells, key=lambda c: c["q"])
    hard_best = max((c for c in cells if c["set"] == "dur"), key=lambda c: c["q"])
    total = sum(c["q"] for c in cells)
    n_win = sum(1 for c in cells if c["q"] > 0)
    n_lose = sum(1 for c in cells if c["q"] < 0)
    n_flat = len(cells) - n_win - n_lose

    naive_gap = max(
        easy_naive[k][f"ctx_{m}"] - easy_recall[k][f"ctx_{m}"] for m in METHODS for k in KS
    )
    naive_q = round(naive_gap * n_easy)

    gains = best["q"] >= SIGNIFICANCE_QUESTIONS
    losses = -worst["q"] >= SIGNIFICANCE_QUESTIONS
    if gains and losses:
        verdict = (
            f"la contextualisation **gagne et perd selon la configuration** : jusqu'à "
            f"{best['q']} {_questions(best['q'])} gagnées ({where(best)}) et jusqu'à "
            f"{-worst['q']} perdues ({where(worst)})"
        )
    elif gains:
        verdict = (
            f"la contextualisation **améliore** la recherche — au mieux {best['q']} "
            f"{_questions(best['q'])} ({where(best)}), aucune perte n'atteignant le seuil"
        )
    elif losses:
        verdict = (
            f"la contextualisation **dégrade** la recherche — au pire {-worst['q']} "
            f"{_questions(worst['q'])} ({where(worst)}), aucun gain n'atteignant le seuil"
        )
    else:
        verdict = (
            "la contextualisation **ne se distingue pas** de la baseline : aucun écart, "
            "dans aucune des douze cellules, n'atteint le seuil"
        )

    # "What it breaks" must follow the sign of the worst cell, and its explanation
    # must follow that cell's *method* — the vector-displacement account only holds
    # for semantic search.
    why_loss = {
        "semantic": "Le préfixe déplace le vecteur du fragment vers le sujet du "
        "*document* et l'éloigne de son contenu propre.",
        "bm25": "Hypothèse à vérifier : le préfixe place l'intitulé du document en tête "
        "de chaque fragment, si bien que l'IDF des termes de titre s'effondre et que la "
        "longueur moyenne croît — les termes qui distinguaient un document d'un autre "
        "perdent leur pouvoir discriminant.",
        "rrf": "La fusion dépend de la composition des deux classements qui "
        "l'alimentent : un déplacement dans l'un d'eux suffit à changer le top-k fusionné.",
    }
    repairs = (
        f"- **Ce qu'elle répare** : les formulations conversationnelles — {where(hard_best)}, "
        f"{amount(hard_best)}. C'est le mode d'échec que la méthode vise : un fragment que "
        "rien ne rattachait à son sujet devient retrouvable."
        if hard_best["q"] > 0
        else f"- **Ce qu'elle ne répare pas** : sur le jeu « dur » — le mode d'échec que la "
        f"méthode vise — le meilleur écart est {amount(hard_best)} ({where(hard_best)}). "
        "La méthode n'y gagne rien."
    )
    breaks = (
        f"- **Ce qu'elle casse** : {where(worst)}, {amount(worst)}. "
        + why_loss[worst["method"]]
        if worst["q"] < 0
        else "- **Elle ne casse rien** : aucune des douze cellules ne recule ; le pire "
        f"écart vaut {amount(worst)} ({where(worst)})."
    )

    return [
        "## Conclusion",
        "",
        f"- **Seuil de signification, fixé avant la mesure : {SIGNIFICANCE_QUESTIONS} "
        "questions.** En deçà, un écart n'est retenu ni comme un gain ni comme une perte. "
        "Même barre que le rapport de sensibilité à la taille du corpus.",
        f"- Sur ce corpus et ce jeu d'évaluation, {verdict}.",
        f"- **Dispersion** : sur les {len(cells)} cellules (2 jeux × {len(METHODS)} méthodes "
        f"× {len(KS)} valeurs de k), la somme des écarts vaut {total:+d} "
        f"{_questions(total)} — {n_win} {_cells(n_win, 'gagnante')}, "
        f"{n_lose} {_cells(n_lose, 'perdante')}, {n_flat} {_cells(n_flat, 'inchangée')}. "
        "Les deux chiffres ci-dessus sont des extrema, non un solde : cette ligne est ce "
        "qui les met en perspective.",
        repairs,
        breaks,
        (
            f"- Réserve : {window['ctx']['over']} fragments sortent de la fenêtre de "
            f"{window['limit']} tokens après contextualisation, contre "
            f"{window['base']['over']} avant. Ces chiffres mesurent donc la méthode "
            "**et** l'étroitesse de la marge de découpage ; conclure sur la méthode "
            "seule demande de re-découper à budget réduit puis de re-mesurer."
            if window["ctx"]["over"]
            else
            "- La troncature est écartée : aucun fragment ne sort de la fenêtre de "
            f"{window['limit']} tokens, ni avant ni après contextualisation. L'écart "
            "mesuré porte donc bien sur la méthode elle-même."
        ),
        f"- Artefact évité par le comptage strict : jusqu'à {naive_gap:+.2f} de recall "
        f"({naive_q:+d} {_questions(naive_q)}) qu'un comptage naïf aurait crédité "
        "à la contextualisation sans qu'aucun fragment ne soit mieux trouvé.",
        "- Rappel de granularité : le jeu « dur » compte "
        f"{n_hard} questions (1 question ≈ {1.0 / n_hard:.3f}) et le jeu « facile » "
        f"{n_easy} (1 question ≈ {1.0 / n_easy:.3f}). Les chiffres d'Anthropic portent "
        "sur des corpus de plusieurs milliers de fragments et une évaluation à "
        "l'échelle : un écart d'une question ici ne les confirme ni ne les infirme.",
        "",
        (
            "**Décision.** `/ask` reste sur la collection de production, en application "
            "du principe « mesurer n'est pas brancher » (§40 du PRD) : le Contextual "
            "Retrieval figure au §5.3 parmi les évolutions documentées et non "
            "implémentées, au même titre que la RRF et la réécriture. **Aucune mesure, "
            "si favorable soit-elle, ne suffirait à elle seule à le brancher en V1.** "
            "Ce rapport reste par ailleurs mesuré dans une configuration qui ne laisse "
            "pas à la méthode la place de fonctionner, et la piste à instruire est "
            "nommée ci-dessus."
            if window["ctx"]["over"]
            else
            "**Décision.** `/ask` reste sur la collection de production, en application "
            "du principe « mesurer n'est pas brancher » (§40 du PRD) : le Contextual "
            "Retrieval figure au §5.3 parmi les évolutions documentées et non "
            "implémentées, au même titre que la RRF et la réécriture. **Aucune mesure, "
            "si favorable soit-elle, ne suffirait à elle seule à le brancher en V1.** "
            "L'arbitrage est ici établi sans confusion possible avec la troncature. "
            "Restent deux questions ouvertes, qui relèvent de l'instruction et non de la "
            "décision : laquelle des deux populations de requêtes servir en priorité, et "
            "si une contextualisation *sélective*, limitée aux fragments réellement "
            "décontextualisés, ne prendrait pas les deux."
        ),
        "",
    ]


if __name__ == "__main__":
    sys.exit(main())
