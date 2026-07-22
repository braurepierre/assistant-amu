"""Tests for the LangChain port (branch only, PRD F9). No real LLM/model."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from assistant_amu.langchain_port.pipeline import build_chain, format_docs


def test_format_docs_matches_v1_xml_shape():
    docs = [LCDocument(page_content="La cesure ...", metadata={"source_title": "Reglement", "page": 12})]
    rendered = format_docs(docs)
    assert "<sources>" in rendered
    assert 'id="S1"' in rendered
    assert "Reglement" in rendered
    assert 'page="12"' in rendered


def test_chain_runs_end_to_end_with_fakes():
    docs = [LCDocument(page_content="La cesure est une suspension.", metadata={"source_title": "Reglement"})]
    retriever = RunnableLambda(lambda _question: docs)
    llm = FakeListChatModel(responses=["La cesure est une suspension. [S1]"])
    chain = build_chain(llm, retriever=retriever)
    assert chain.invoke("Modalites de cesure ?") == "La cesure est une suspension. [S1]"
