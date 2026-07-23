r"""Hand-written pipeline vs LangChain port — side-by-side comparison (PRD F9).

Runs the SAME questions through both implementations, in one process, against the
SAME persisted ChromaDB collection and the SAME system prompt, so their answers
are directly comparable:

    main   assistant_amu.generation.rag.RagPipeline   (explicit, hand-written)
    lc     assistant_amu.langchain_port.pipeline       (LCEL chain)

Both resolve their LLM from `get_settings()`, so with LLM_BACKEND=mistral both hit
the same model — the comparison isolates *the wiring*, not the backend. For each
question we report: the two answers, refusal parity, citation parity ([S1]…), and
a rough lexical overlap. The point is F9's claim — "réponses équivalentes" — and
to make visible what the chain returns (a bare string) vs what /ask's contract
still needs (structured sources, refusal → empty sources, error → 503).

Run (Mistral backend recommended: fast + deterministic-ish at low temperature):
    LLM_BACKEND=mistral python eval/compare_pipelines.py
    # PowerShell: $env:LLM_BACKEND='mistral'; .\.venv\Scripts\python.exe eval/compare_pipelines.py
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import load_questions
from assistant_amu.generation.rag import RagPipeline, is_refusal, normalize
from assistant_amu.langchain_port.pipeline import E5Embeddings, build_chain, build_llm

QUESTIONS = PROJECT_ROOT / "eval" / "questions.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
K = 5
_CITATION = re.compile(r"\[S\d+\]")


def _citations(text: str) -> set[str]:
    return set(_CITATION.findall(text))


def _overlap(a: str, b: str) -> float:
    """Jaccard overlap of normalised word sets — a coarse 'same content?' signal."""
    wa, wb = set(normalize(a).split()), set(normalize(b).split())
    if not wa and not wb:
        return 1.0
    return len(wa & wb) / len(wa | wb) if (wa | wb) else 0.0


def _truncate(text: str, width: int = 90) -> str:
    text = text.replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1] + "…"


def main() -> int:
    settings = get_settings()
    pipeline = RagPipeline.from_settings(settings)
    # Both pipelines open a Chroma client on the same directory in ONE process.
    # Our VectorStore disables telemetry; LangChain's Chroma defaults to on, and
    # ChromaDB refuses two clients with divergent settings on the same path. So we
    # build the LC retriever ourselves with MATCHING settings and inject it via
    # build_chain(retriever=…) — the port itself is untouched (it only ever makes
    # one client when run alone).
    lc_store = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(settings.chroma_path),
        embedding_function=E5Embeddings(settings.embedding_model),
        client_settings=ChromaSettings(anonymized_telemetry=False),
    )
    chain = build_chain(build_llm(settings), settings, k=K,
                        retriever=lc_store.as_retriever(search_kwargs={"k": K}))
    questions = load_questions(QUESTIONS)
    print(f"backend={settings.backend_name} | {len(questions)} questions | k={K}")

    rows = []
    for q in questions:
        main_res = pipeline.answer(q.question, k=K)
        lc_answer = chain.invoke(q.question)
        main_refuse, lc_refuse = is_refusal(main_res.answer), is_refusal(lc_answer)
        row = {
            "id": q.id,
            "question": q.question,
            "answerable": q.answerable,
            "main_answer": main_res.answer,
            "lc_answer": lc_answer,
            "main_sources": len(main_res.sources),
            "main_cites": _citations(main_res.answer),
            "lc_cites": _citations(lc_answer),
            "main_refuse": main_refuse,
            "lc_refuse": lc_refuse,
            "refusal_parity": main_refuse == lc_refuse,
            "overlap": _overlap(main_res.answer, lc_answer),
        }
        rows.append(row)
        print(f"  {q.id}: refusal main={main_refuse} lc={lc_refuse} | overlap={row['overlap']:.2f}")

    _write_report(settings, rows)
    return 0


def _write_report(settings, rows) -> None:
    today = date.today().isoformat()
    n = len(rows)
    refusal_agree = sum(1 for r in rows if r["refusal_parity"])
    cite_agree = sum(1 for r in rows if r["main_cites"] == r["lc_cites"])
    mean_overlap = sum(r["overlap"] for r in rows) / n if n else 0.0

    lines = [
        f"# Rapport — pipeline manuel vs port LangChain — {today}",
        "",
        f"- Backend LLM (les deux pipelines) : `{settings.backend_name}` "
        f"(température {settings.temperature:g}) | Embeddeur : `{settings.embedding_model}` | k = {K}",
        f"- Même collection ChromaDB, même prompt système → la comparaison isole *le câblage*.",
        f"- {n} questions. **Parité de refus** : {refusal_agree}/{n}. "
        f"**Parité de citations [S…]** : {cite_agree}/{n}. "
        f"**Recouvrement lexical moyen** : {mean_overlap:.2f}.",
        "",
        "## Synthèse",
        "",
        "- La chaîne LCEL renvoie une **chaîne de caractères** ; le pipeline manuel renvoie un "
        "`RagResult` structuré (`answer` + `sources` + `model` + `retrieved_chunks`).",
        "- Détection de refus, mise à zéro des sources sur refus, mapping erreur backend → 503 : "
        "**hors** de la chaîne — c'est du code produit que LangChain n'abstrait pas.",
        "- Un recouvrement < 1.0 est attendu : même contexte et même prompt, mais deux formulations "
        "d'un modèle non déterministe. Le signal fiable d'équivalence est la **parité de refus** et "
        "la **parité de citations**, pas l'égalité mot-à-mot.",
        "",
        "## Détail par question",
        "",
        "| id | ans. | refus main/lc | cites main/lc | recouvr. | réponse manuelle | réponse LangChain |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        refus = f"{'oui' if r['main_refuse'] else 'non'}/{'oui' if r['lc_refuse'] else 'non'}"
        refus_mark = " ✅" if r["refusal_parity"] else " ⚠️"
        cites = f"{len(r['main_cites'])}/{len(r['lc_cites'])}"
        lines.append(
            f"| {r['id']} | {'o' if r['answerable'] else 'n'} | {refus}{refus_mark} | {cites} | "
            f"{r['overlap']:.2f} | {_truncate(r['main_answer'])} | {_truncate(r['lc_answer'])} |"
        )
    lines.append("")

    # Divergences worth a human look: refusal disagreements.
    disagree = [r for r in rows if not r["refusal_parity"]]
    lines += ["## Divergences de refus (à regarder)", ""]
    if not disagree:
        lines.append("_Aucune : les deux pipelines refusent (ou répondent) sur les mêmes questions._")
    else:
        lines += ["| id | question | main | lc |", "|---|---|---|---|"]
        for r in disagree:
            lines.append(
                f"| {r['id']} | {_truncate(r['question'], 50)} | "
                f"{'refus' if r['main_refuse'] else 'répond'} | "
                f"{'refus' if r['lc_refuse'] else 'répond'} |"
            )
    lines.append("")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{today}_pipeline_vs_langchain.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"backend={settings.backend_name} | refusal parity {refusal_agree}/{n} | "
          f"cite parity {cite_agree}/{n} | mean overlap {mean_overlap:.2f}")
    print(f"  report: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
