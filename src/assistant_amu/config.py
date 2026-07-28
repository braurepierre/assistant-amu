"""Application configuration.

Settings are read from environment variables (optionally populated from a local
``.env`` file via python-dotenv) with sensible defaults, then validated. Invalid
configuration raises :class:`ConfigError` so the process fails at startup rather
than on the first request (PRD F5).

See the PRD (§6.1, §7.2, §7.3, §7.4) for the rationale behind each default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project root: three levels up from <root>/src/assistant_amu/config.py.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load a local .env if present. Values already in the environment take priority.
load_dotenv(PROJECT_ROOT / ".env")

VALID_BACKENDS: tuple[str, ...] = ("ollama", "mistral")


class ConfigError(RuntimeError):
    """Raised when the environment configuration is invalid."""


def _get_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Environment variable {name} must be an integer, got {raw!r}."
        ) from exc


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Environment variable {name} must be a number, got {raw!r}."
        ) from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable, validated view of the runtime configuration."""

    # LLM backend selection (PRD §7.4).
    llm_backend: str
    temperature: float

    # Ollama (local backend).
    ollama_base_url: str
    ollama_model: str
    ollama_num_ctx: int
    ollama_timeout_s: int

    # Mistral La Plateforme (API backend).
    mistral_api_key: str | None
    mistral_model: str
    mistral_timeout_s: int

    # Retrieval and indexing (PRD §7.3).
    embedding_model: str
    chroma_path: Path
    chroma_collection: str
    top_k: int

    # Chunking (PRD §7.2).
    chunk_max_tokens: int
    chunk_overlap: int

    @property
    def backend_name(self) -> str:
        """Human-readable backend id echoed in API responses and eval reports."""
        if self.llm_backend == "ollama":
            return f"ollama/{self.ollama_model}"
        return f"mistral/{self.mistral_model}"


def load_settings() -> Settings:
    """Read and validate settings from the environment.

    Raises:
        ConfigError: if a value is malformed or an invalid backend is selected.
    """
    # Default backend: the hosted API. The local one answers in minutes on CPU,
    # which no interactive surface can wait for; this one answers in seconds.
    # Without a key the call below fails at startup rather than on the first
    # question — set LLM_BACKEND=ollama to run without an account.
    backend = _get_str("LLM_BACKEND", "mistral").lower()
    if backend not in VALID_BACKENDS:
        raise ConfigError(
            f"LLM_BACKEND must be one of {VALID_BACKENDS}, got {backend!r}."
        )

    mistral_api_key = os.environ.get("MISTRAL_API_KEY", "").strip() or None

    settings = Settings(
        llm_backend=backend,
        temperature=_get_float("LLM_TEMPERATURE", 0.2),
        ollama_base_url=_get_str("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=_get_str("OLLAMA_MODEL", "mistral"),
        ollama_num_ctx=_get_int("OLLAMA_NUM_CTX", 8192),
        ollama_timeout_s=_get_int("OLLAMA_TIMEOUT_S", 120),
        mistral_api_key=mistral_api_key,
        mistral_model=_get_str("MISTRAL_MODEL", "mistral-small-latest"),
        mistral_timeout_s=_get_int("MISTRAL_TIMEOUT_S", 30),
        embedding_model=_get_str(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
        ),
        chroma_path=Path(
            _get_str("CHROMA_PATH", str(PROJECT_ROOT / "chroma_db"))
        ),
        chroma_collection=_get_str("CHROMA_COLLECTION", "amu_docs"),
        top_k=_get_int("TOP_K", 5),
        chunk_max_tokens=_get_int("CHUNK_MAX_TOKENS", 500),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 50),
    )

    # Fail fast: the API backend is unusable without a key (PRD F5).
    if settings.llm_backend == "mistral" and not settings.mistral_api_key:
        raise ConfigError(
            "LLM_BACKEND=mistral but MISTRAL_API_KEY is not set. "
            "Set it in your .env or export it before starting the app."
        )
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings, validated once and cached.

    Import this from application entrypoints so misconfiguration surfaces at
    startup, not on the first request. Tests call :func:`load_settings` directly
    to bypass the cache.
    """
    return load_settings()
