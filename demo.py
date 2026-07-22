"""Gradio demo for AssistantAMU — a thin HTTP client of the API (PRD §5.4).

Zero business logic: it only calls ``POST /ask`` and renders the answer plus its
sources. Start the API first (see DEMO.md), then run: ``python demo.py``.
"""

from __future__ import annotations

import os

import gradio as gr
import httpx

API_URL = os.environ.get("ASSISTANT_AMU_API", "http://127.0.0.1:8000")


def ask(question: str, k: int) -> str:
    """Call POST /ask and format the answer and sources as Markdown."""
    if not question.strip():
        return "_Pose une question._"
    try:
        response = httpx.post(
            f"{API_URL}/ask", json={"question": question, "k": int(k)}, timeout=180
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return f"**Erreur {exc.response.status_code}** : {exc.response.text}"
    except httpx.HTTPError as exc:
        return f"**API injoignable** ({API_URL}) : {exc}. L'API est-elle lancée ?"

    data = response.json()
    parts = [data["answer"], "", f"*Backend : {data['model']} — {data['retrieved_chunks']} extraits*"]
    if data["condensed_question"]:
        parts.append(f"*Question reformulée : {data['condensed_question']}*")
    for i, source in enumerate(data["sources"], start=1):
        page = f", p. {source['page']}" if source.get("page") is not None else ""
        parts.append(f"\n**[S{i}]** {source['title']}{page} — score {source['score']:.2f}")
        parts.append(f"> {source['excerpt']}")
    return "\n".join(parts)


demo = gr.Interface(
    fn=ask,
    inputs=[
        gr.Textbox(label="Votre question", placeholder="Quelles sont les modalités de la césure ?"),
        gr.Slider(1, 10, value=5, step=1, label="Extraits récupérés (k)"),
    ],
    outputs=gr.Markdown(label="Réponse sourcée"),
    title="AssistantAMU",
    description="Assistant documentaire RAG sur les documents publics d'Aix-Marseille Université.",
    flagging_mode="never",
)

if __name__ == "__main__":
    demo.launch()
