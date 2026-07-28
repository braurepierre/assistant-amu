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


def test_defaults_select_mistral(monkeypatch):
    # The default backend is the hosted API, which needs a key: supplied here so
    # the test exercises the defaults rather than the fail-fast below.
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.llm_backend == "mistral"
    assert settings.mistral_model == "mistral-small-latest"
    assert settings.backend_name == "mistral/mistral-small-latest"


def test_shared_defaults_hold_for_either_backend(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    settings = load_settings()
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


def test_default_backend_without_key_fails_at_startup():
    """The default needs a key, and says so before the first question (F5)."""
    with pytest.raises(ConfigError):
        load_settings()  # no LLM_BACKEND, no MISTRAL_API_KEY


def test_malformed_int_raises(monkeypatch):
    monkeypatch.setenv("TOP_K", "not-a-number")
    with pytest.raises(ConfigError):
        load_settings()
