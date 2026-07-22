"""LangChain LCEL reimplementation of the single-turn query pipeline (PRD F9).

Comparison branch only. It reuses:
- the SAME persisted ChromaDB collection (`amu_docs`), via a LangChain
  ``Embeddings`` adapter that keeps the E5 ``query:``/``passage:`` prefixes;
- the SAME system prompt (`prompts/rag_system.md`).

so ``/ask`` answers are directly comparable to the hand-written pipeline. What
the hand-written version does *explicitly* and this chain *abstracts away* is
discussed in the branch README.
"""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough

from ..config import Settings, get_settings
from ..generation.rag import load_system_prompt
from ..retrieval.embedder import Embedder


class E5Embeddings(Embeddings):
    """Adapts our prefix-aware :class:`Embedder` to LangChain's interface.

    This is the crux of the comparison: LangChain's off-the-shelf
    ``HuggingFaceEmbeddings`` would NOT add the E5 prefixes (piège n°1), so
    reusing the existing collection correctly still requires our own wrapper.
    """

    def __init__(self, model_name: str):
        self._embedder = Embedder(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_passages(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_queries([text])[0]


def format_docs(docs: list[LCDocument]) -> str:
    """Render retrieved documents as the same XML <sources> block we use in V1."""
    lines = ["<sources>"]
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        attrs = [f'id="S{i}"', f'titre="{meta.get("source_title", "")}"']
        if meta.get("page") is not None:
            attrs.append(f'page="{meta.get("page")}"')
        lines.append(f"<source {' '.join(attrs)}>")
        lines.append(doc.page_content)
        lines.append("</source>")
    lines.append("</sources>")
    return "\n".join(lines)


def build_chain(
    llm: BaseChatModel,
    settings: Settings | None = None,
    *,
    k: int = 5,
    retriever: Runnable | None = None,
) -> Runnable:
    """Build the LCEL chain: retrieve -> format -> prompt -> llm -> str.

    ``retriever`` can be injected (tests); otherwise it is built from the
    persisted Chroma collection.
    """
    settings = settings or get_settings()
    if retriever is None:
        vectorstore = Chroma(
            collection_name=settings.chroma_collection,
            persist_directory=str(settings.chroma_path),
            embedding_function=E5Embeddings(settings.embedding_model),
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    prompt = ChatPromptTemplate.from_messages(
        [("system", load_system_prompt()), ("human", "{context}\n\nQuestion : {question}")]
    )
    return (
        {"context": retriever | RunnableLambda(format_docs), "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


def build_llm(settings: Settings | None = None) -> BaseChatModel:
    """Instantiate the LangChain chat model for the configured backend."""
    settings = settings or get_settings()
    if settings.llm_backend == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            num_ctx=settings.ollama_num_ctx,
            temperature=settings.temperature,
        )
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(
        model=settings.mistral_model,
        api_key=settings.mistral_api_key,
        temperature=settings.temperature,
    )


def answer(question: str, k: int = 5) -> str:
    """Convenience: build the chain for the configured backend and run it."""
    settings = get_settings()
    return build_chain(build_llm(settings), settings, k=k).invoke(question)
