"""Tests for PDF/HTML extraction (PRD §7.2)."""

from __future__ import annotations

import pytest

from assistant_amu.ingestion.extract import ScannedDocumentError, compute_doc_id, extract
from assistant_amu.models import SourceDoc


def test_extract_html_sections_and_noise(sample_html):
    source = SourceDoc(title="Reglement", category="reglement-scolarite", type="html", url="u")
    doc = extract(sample_html, source)
    joined = doc.text
    assert "menu principal a ignorer" not in joined  # nav stripped
    assert "pied de page a ignorer" not in joined  # footer stripped
    assert "La cesure permet" in joined
    # Heading path captured in section metadata.
    sections = {b.section for b in doc.blocks}
    assert "Reglement des etudes > Cesure" in sections
    assert "Reglement des etudes > MCC" in sections


def test_extract_pdf_pages(sample_pdf):
    source = SourceDoc(title="Guide", category="guide-etudiant", type="pdf", url="u")
    doc = extract(sample_pdf, source)
    pages = [b.page for b in doc.blocks]
    assert pages == [1, 2, 3]
    assert "cesure" in doc.text.lower()
    assert len(doc.doc_id) == 16


def test_doc_id_is_content_stable(sample_pdf):
    source = SourceDoc(title="Guide", category="guide-etudiant", type="pdf", url="u")
    doc1 = extract(sample_pdf, source)
    doc2 = extract(sample_pdf, source)
    assert doc1.doc_id == doc2.doc_id
    # doc_id depends on content, not on the title metadata.
    assert doc1.doc_id == compute_doc_id(doc1.blocks)


def test_scanned_pdf_excluded(scanned_pdf):
    source = SourceDoc(title="Scan", category="composante", type="pdf", url="u")
    with pytest.raises(ScannedDocumentError):
        extract(scanned_pdf, source)
