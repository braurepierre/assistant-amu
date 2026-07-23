r"""Embedder comparison — MEASURED ONLY (does not touch the /ask pipeline).

PRD Phase 5 deliverable: compare the semantic recall@k of three French-capable
sentence encoders on the SAME chunks and the SAME annotated questions, so the
choice of embedder is grounded in numbers rather than reputation:

    intfloat/multilingual-e5-small   baseline / production embedder (E5 family)
    dangvantuan/sentence-camembert-base   CamemBERT fine-tuned for STS (no prefix)
    Lajavaness/sentence-flaubert-base     FlauBERT fine-tuned for STS (no prefix)

Mechanics mirror `evaluate.py --embedding-model` (§7.6): the production chunks
are read once from the persisted `amu_docs` collection, then re-embedded into an
EPHEMERAL parallel collection per model (suffixed, dropped in `finally`). The
production collection is never modified. BM25 recall is embedder-independent and
reported once as a lexical reference. No LLM is involved.

E5 needs the `query:`/`passage:` prefixes; CamemBERT and FlauBERT take none — the
family table in `retrieval/embedder.py` applies the right set automatically, so
adding FlauBERT required no code change beyond listing its HF id here.

Run (no LLM backend needed):
    python eval/embedder_comparison.py
    # PowerShell: .\.venv\Scripts\python.exe eval/embedder_comparison.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import evaluate_retrieval, load_questions
from assistant_amu.models import Chunk
from assistant_amu.retrieval.bm25_store import Bm25Index
from assistant_amu.retrieval.embedder import Embedder
from assistant_amu.retrieval.vector_store import SemanticRetriever, VectorStore

QUESTIONS = PROJECT_ROOT / "eval" / "questions.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
KS = (3, 5, 8)
DETAIL_K = 5

# (label, HF id). The first entry is the production/base embedder (E5).
CAMEMBERT = "dangvantuan/sentence-camembert-base"
# NB: the *cased* `Lajavaness/sentence-flaubert-base` fails to load under
# sentence-transformers 5.6.1 (its Moses `FlaubertTokenizer` has no
# `basic_tokenizer`, which ST's Transformer module assumes). This *uncased*
# FlauBERT fine-tuned on XNLI/STS loads cleanly and is the FlauBERT data point.
FLAUBERT = "hugorosen/flaubert_base_uncased-xnli-sts"


def _truncate(text: str, width: int = 70) -> str:
    text = text.replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1] + "…"


def _semantic_recall(retriever, questions) -> dict[int, float]:
    """recall@k (semantic only) for every k in KS, for one embedder."""
    return {k: evaluate_retrieval(questions, {"semantic": retriever}, k).recall["semantic"] for k in KS}


def _semantic_hits(retriever, questions) -> dict[str, bool]:
    """Per-question hit at DETAIL_K (semantic), keyed by question id."""
    rows = evaluate_retrieval(questions, {"semantic": retriever}, DETAIL_K).rows
    return {row.id: row.hits["semantic"] for row in rows}


def main() -> int:
    settings = get_settings()
    base_store = VectorStore.from_settings(settings)
    if base_store.count() == 0:
        print("Empty collection — run `python -m assistant_amu.ingestion index` first.")
        return 1

    questions = load_questions(QUESTIONS)
    answerable = [q for q in questions if q.answerable]
    ids, docs, metas = base_store.get_all()
    chunks = [Chunk(i, str(m.get("doc_id", "")), d, m) for i, d, m in zip(ids, docs, metas)]
    n_docs = len({m.get("doc_id") for m in metas})
    corpus_desc = f"{n_docs} docs / {len(chunks)} chunks"
    print(f"corpus: {corpus_desc} | {len(answerable)} answerable questions")

    models = [
        ("e5-small", settings.embedding_model),
        ("camembert", CAMEMBERT),
        ("flaubert", FLAUBERT),
    ]

    recall: dict[str, dict[int, float]] = {}
    hits: dict[str, dict[str, bool]] = {}
    errors: dict[str, str] = {}

    for label, model_id in models:
        cleanup = None  # ephemeral store to drop in `finally`, even if embedding fails
        try:
            if model_id == settings.embedding_model:
                store = base_store  # already embedded with E5 — reuse, don't rebuild
            else:
                suffix = model_id.split("/")[-1].replace("-", "")[:16]
                store = VectorStore(
                    path=settings.chroma_path,
                    collection_name=f"{settings.chroma_collection}__cmp_{suffix}",
                    embedder=Embedder(model_id),
                )
                cleanup = store  # collection now exists — guarantee its teardown
                print(f"[{label}] embedding {len(chunks)} chunks with {model_id} …")
                store.add_chunks(chunks)
            retriever = SemanticRetriever(store)
            recall[label] = _semantic_recall(retriever, questions)
            hits[label] = _semantic_hits(retriever, questions)
            print(f"[{label}] " + " ".join(f"recall@{k}={recall[label][k]:.2f}" for k in KS))
        except Exception as exc:  # noqa: BLE001 — one bad model must not sink the others
            errors[label] = f"{type(exc).__name__}: {exc}"
            print(f"[{label}] FAILED — {errors[label]}")
        finally:
            if cleanup is not None:
                cleanup.delete_collection()  # production collection is never touched

    # BM25 reference (embedder-independent): computed once over the same chunks.
    bm25 = Bm25Index(ids, docs, metas)
    bm25_recall = {k: evaluate_retrieval(questions, {"bm25": bm25}, k).recall["bm25"] for k in KS}
    print("[bm25] " + " ".join(f"recall@{k}={bm25_recall[k]:.2f}" for k in KS))

    _write_report(settings, answerable, recall, hits, bm25_recall, errors, corpus_desc)
    return 0


def _write_report(settings, answerable, recall, hits, bm25_recall, errors, corpus_desc) -> None:
    today = date.today().isoformat()
    n = len(answerable)
    grain = 1.0 / n if n else 0.0
    ok = [label for label in ("e5-small", "camembert", "flaubert") if label in recall]

    lines = [
        f"# Rapport — comparaison d'embeddeurs (mesure seule) — {today}",
        "",
        f"- Corpus : {corpus_desc} — {n} questions answerable "
        f"(granularité 1/{n} ≈ {grain:.3f}).",
        f"- Chunks ré-embarqués depuis la collection `{settings.chroma_collection}` (mêmes chunks "
        "pour tous les modèles) ; collections éphémères supprimées après mesure.",
        "- `recall@k` (sémantique) = proxy de *context recall* (RAGAS). BM25 = référence "
        "lexicale, indépendante de l'embeddeur. **Mesure seule** : le pipeline `/ask` reste "
        "sémantique pur avec l'embeddeur de production (§5.1.8).",
        "- Modèles E5 : préfixes `query:`/`passage:` ; CamemBERT & FlauBERT : aucun préfixe "
        "(table par famille dans `retrieval/embedder.py`).",
        "",
        "## Recall@k par embeddeur",
        "",
        "| Embeddeur | " + " | ".join(f"recall@{k}" for k in KS) + " |",
        "|---|" + "|".join("---" for _ in KS) + "|",
    ]
    label_id = {
        "e5-small": settings.embedding_model,
        "camembert": CAMEMBERT,
        "flaubert": FLAUBERT,
    }
    for label in ok:
        cells = " | ".join(f"{recall[label][k]:.2f}" for k in KS)
        lines.append(f"| `{label_id[label]}` | {cells} |")
    lines.append("| _BM25 (référence lexicale)_ | " + " | ".join(f"{bm25_recall[k]:.2f}" for k in KS) + " |")
    lines.append("")

    if errors:
        lines += ["> **Modèles non mesurés** (téléchargement/chargement échoué) :", ""]
        lines += [f"> - `{label_id.get(label, label)}` — {msg}" for label, msg in errors.items()]
        lines.append("")

    # Per-question detail at DETAIL_K + who-finds-what.
    if len(ok) >= 1:
        lines += [
            f"## Détail par question (sémantique, k={DETAIL_K})",
            "",
            "| id | question | " + " | ".join(ok) + " |",
            "|---|---|" + "|".join("---" for _ in ok) + "|",
        ]
        for q in answerable:
            cells = " | ".join("✅" if hits.get(label, {}).get(q.id) else "❌" for label in ok)
            lines.append(f"| {q.id} | {_truncate(q.question)} | {cells} |")
        lines.append("")

    # Disagreements: questions where the models differ at DETAIL_K.
    if len(ok) >= 2:
        diff = [
            q for q in answerable
            if len({hits.get(label, {}).get(q.id, False) for label in ok}) > 1
        ]
        lines += [f"## Désaccords entre embeddeurs (k={DETAIL_K})", ""]
        if not diff:
            lines.append("_Aucun désaccord : les embeddeurs récupèrent le même ensemble._")
        else:
            lines += ["| id | question | " + " | ".join(ok) + " |",
                      "|---|---|" + "|".join("---" for _ in ok) + "|"]
            for q in diff:
                cells = " | ".join("✅" if hits.get(label, {}).get(q.id) else "❌" for label in ok)
                lines.append(f"| {q.id} | {_truncate(q.question)} | {cells} |")
        lines.append("")

    # Computed conclusion: best mean recall over KS.
    if ok:
        def mean_recall(label: str) -> float:
            return sum(recall[label][k] for k in KS) / len(KS)

        winner = max(ok, key=mean_recall)
        ranking = " · ".join(f"`{label}` {mean_recall(label):.2f}" for label in sorted(ok, key=mean_recall, reverse=True))
        lines += [
            "## Conclusion",
            "",
            f"- **Meilleur recall@k moyen : `{winner}`** ({label_id[winner]}).",
            f"- Classement (moyenne recall@{'/'.join(map(str, KS))}) : {ranking}.",
            "- Rappel : un écart inférieur à un cran de question "
            f"(≈ {grain:.3f}) n'est pas significatif sur ce jeu de {n} questions.",
            "- La bascule éventuelle de l'embeddeur de production est une décision distincte "
            "(coût, taille, latence CPU), pas seulement un delta de recall.",
            "",
        ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{today}_embedder_comparison.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  report: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
