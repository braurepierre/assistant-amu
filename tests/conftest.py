"""Shared pytest fixtures: mini-document fixtures for ingestion (PRD §11.6)."""

from __future__ import annotations

import pytest
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# A deterministic, dependency-free token counter for chunking tests. Production
# uses the real embedding tokenizer (chunk.default_token_counter).
def _word_count(text: str) -> int:
    return len(text.split())


@pytest.fixture
def word_counter():
    return _word_count


@pytest.fixture
def sample_html(tmp_path):
    """A small HTML page with nav/footer noise and an h1>h2 heading structure."""
    html = """<!doctype html>
    <html><head><title>Reglement</title></head>
    <body>
      <nav>menu principal a ignorer</nav>
      <main>
        <h1>Reglement des etudes</h1>
        <h2>Cesure</h2>
        <p>La cesure permet de suspendre ses etudes pendant une annee.</p>
        <p>Elle est encadree par le reglement des etudes de l'universite.</p>
        <h2>MCC</h2>
        <p>Les modalites de controle des connaissances sont definies par composante.</p>
        <ul><li>Regime standard d'assiduite.</li><li>Regime special d'etudes.</li></ul>
      </main>
      <footer>pied de page a ignorer</footer>
    </body></html>"""
    path = tmp_path / "reglement.html"
    path.write_text(html, encoding="utf-8")
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    """A 3-page PDF with a repeated header (exercises boilerplate removal)."""
    pdf = FPDF()
    header = "Universite d'Aix-Marseille (document interne)"
    body = "La cesure est une suspension temporaire des etudes. "
    for i in range(1, 4):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, header, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.multi_cell(0, 8, f"Page {i}. {body * 4}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    path = tmp_path / "guide.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def scanned_pdf(tmp_path):
    """A PDF with no text layer — simulates a scanned document."""
    pdf = FPDF()
    pdf.add_page()
    path = tmp_path / "scanned.pdf"
    pdf.output(str(path))
    return path
