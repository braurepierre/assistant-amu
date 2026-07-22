"""Smoke tests for :mod:`assistant_amu.config` (Phase 0)."""

from __future__ import annotations

import pytest

from assistant_amu.config import ConfigError, Settings, load_settings

# Config-influencing variables, cleared before each test so defaults are
# exercised deterministically regardless of the developer's real environment.
_CONFIG_VARS = (
    "LLM_BACKEND",
    "LLM_TEMPERATURE",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_NUM_CTX",
    "OLLAMA_TIMEOUT_S",
    "MISTRAL_API_KEY",
    "MISTRAL_MODEL",
    "MISTRAL_TIMEOUT_S",
    "EMBEDDING_MODEL",
    "CHROMA_PATH",
    "CHROMA_COLLECTION",
    "TOP_K",
    "CHUNK_MAX_TOKENS",
    "CHUNK_OVERLAP",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _CONFIG_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_select_ollama():
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.llm_backend == "ollama"
    assert settings.ollama_model == "mistral"
    assert settings.ollama_num_ctx == 8192  # PRD piège n°3
    assert settings.top_k == 5
    assert settings.chunk_max_tokens == 500
    assert settings.embedding_model == "intfloat/multilingual-e5-small"
    assert settings.backend_name == "ollama/mistral"


def test_invalid_backend_raises(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "gpt-4")
    with pytest.raises(ConfigError):
        load_settings()


def test_mistral_backend_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "mistral")  # key stays unset (F5)
    with pytest.raises(ConfigError):
        load_settings()


def test_malformed_int_raises(monkeypatch):
    monkeypatch.setenv("TOP_K", "not-a-number")
    with pytest.raises(ConfigError):
        load_settings()
