"""Tests for sources.yaml parsing/validation (PRD §7.1)."""

from __future__ import annotations

import pytest

from assistant_amu.ingestion import IngestionError
from assistant_amu.ingestion.download import load_sources


def _write(tmp_path, text):
    path = tmp_path / "sources.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_sources(tmp_path):
    path = _write(
        tmp_path,
        """
documents:
  - title: "Reglement des etudes"
    category: reglement-scolarite
    type: pdf
    url: "https://example.org/reglement.pdf"
  - title: "Guide local"
    category: guide-etudiant
    type: html
    path: "corpus/raw/guide.html"
""",
    )
    sources = load_sources(path)
    assert len(sources) == 2
    assert sources[0].url and sources[0].path is None
    assert sources[1].path and sources[1].url is None


def test_empty_documents_is_valid(tmp_path):
    assert load_sources(_write(tmp_path, "documents: []")) == []


def test_missing_documents_key_raises(tmp_path):
    with pytest.raises(IngestionError):
        load_sources(_write(tmp_path, "other: 1"))


def test_missing_required_field_raises(tmp_path):
    with pytest.raises(IngestionError):
        load_sources(_write(tmp_path, "documents:\n  - title: x\n    type: pdf\n    url: u\n"))


def test_url_and_path_mutually_exclusive(tmp_path):
    with pytest.raises(IngestionError):
        load_sources(
            _write(
                tmp_path,
                'documents:\n  - {title: x, category: composante, type: pdf, url: u, path: p}\n',
            )
        )


def test_unsupported_type_raises(tmp_path):
    with pytest.raises(IngestionError):
        load_sources(
            _write(tmp_path, 'documents:\n  - {title: x, category: composante, type: docx, url: u}\n')
        )


def test_missing_file_raises(tmp_path):
    with pytest.raises(IngestionError):
        load_sources(tmp_path / "nope.yaml")
