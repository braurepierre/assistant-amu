"""Tests for text cleaning: boilerplate, TOC, whitespace (PRD §7.2)."""

from __future__ import annotations

from assistant_amu.ingestion.clean import clean_document
from assistant_amu.models import Document, TextBlock


def _doc(blocks):
    return Document(doc_id="x", title="t", category="c", url=None, blocks=blocks)


def test_repeated_header_removed():
    header = "Universite d'Aix-Marseille"
    blocks = [
        TextBlock(text=f"{header}\nContenu unique de la page {i}.", page=i)
        for i in range(1, 5)  # header on 4 pages (>= 3)
    ]
    cleaned = clean_document(_doc(blocks))
    assert all(header not in b.text for b in cleaned.blocks)
    assert any("Contenu unique de la page 1." in b.text for b in cleaned.blocks)


def test_non_repeated_line_kept():
    blocks = [
        TextBlock(text="Titre unique\nProse.", page=1),
        TextBlock(text="Autre titre\nProse.", page=2),
    ]
    cleaned = clean_document(_doc(blocks))
    assert any("Titre unique" in b.text for b in cleaned.blocks)


def test_toc_dot_leader_removed():
    blocks = [TextBlock(text="Article 3 .......... 12\nVrai contenu.", page=1)]
    cleaned = clean_document(_doc(blocks))
    assert "Article 3" not in cleaned.blocks[0].text
    assert "Vrai contenu." in cleaned.blocks[0].text


def test_whitespace_normalised():
    blocks = [TextBlock(text="trop    d'espaces\n\n\n\net de lignes", page=1)]
    cleaned = clean_document(_doc(blocks))
    text = cleaned.blocks[0].text
    assert "  " not in text
    assert "\n\n\n" not in text


def test_provenance_and_id_preserved():
    blocks = [TextBlock(text="Contenu.", page=7, section="Titre > Sous")]
    cleaned = clean_document(_doc(blocks))
    assert cleaned.doc_id == "x"
    assert cleaned.blocks[0].page == 7
    assert cleaned.blocks[0].section == "Titre > Sous"
