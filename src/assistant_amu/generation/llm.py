"""LLM backend abstraction (PRD §7.4).

One :class:`LLMBackend` protocol (name + ``generate``), two implementations
selected by ``LLM_BACKEND``: :class:`OllamaBackend` (local, explicit ``num_ctx``
— piège n°3) and :class:`MistralBackend` (API). No streaming, no elaborate
retry, no state. Failures surface as :class:`LLMBackendError` with a normalised
cause so the API layer can map them to a clean 503 (F5).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

import httpx

from ..config import Settings, get_settings

Cause = Literal["timeout", "connection", "auth", "quota", "other"]


class LLMBackendError(Exception):
    """A backend call failed. ``cause`` is a normalised category (PRD §7.4)."""

    def __init__(self, message: str, *, cause: Cause = "other"):
        super().__init__(message)
        self.cause: Cause = cause


@runtime_checkable
class LLMBackend(Protocol):
    name: str  # e.g. "ollama/mistral" — echoed in API responses and eval reports

    def generate(self, system: str, user: str) -> str: ...

    def health(self) -> bool: ...


def _map_http_error(exc: httpx.HTTPError) -> LLMBackendError:
    if isinstance(exc, httpx.TimeoutException):
        return LLMBackendError(f"request timed out: {exc}", cause="timeout")
    if isinstance(exc, httpx.ConnectError):
        return LLMBackendError(f"cannot connect: {exc}", cause="connection")
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        cause: Cause = (
            "auth" if status in (401, 403)
            else "quota" if status == 429
            else "other"
        )
        return LLMBackendError(f"HTTP {status}: {exc}", cause=cause)
    return LLMBackendError(f"request failed: {exc}", cause="other")


class OllamaBackend:
    """Local Ollama chat backend (POST /api/chat, stream=false)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        num_ctx: int,
        timeout_s: float,
        temperature: float,
        client: httpx.Client | None = None,
    ):
        self.name = f"ollama/{model}"
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._num_ctx = num_ctx
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._client = client

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # num_ctx is explicit: Ollama otherwise truncates to a small default
            # window silently, dropping sources without any error (piège n°3).
            "options": {"num_ctx": self._num_ctx, "temperature": self._temperature},
        }
        requester = self._client or httpx
        try:
            response = requester.post(
                f"{self._base_url}/api/chat", json=payload, timeout=self._timeout_s
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _map_http_error(exc) from exc
        return response.json()["message"]["content"]

    def health(self) -> bool:
        requester = self._client or httpx
        try:
            requester.get(f"{self._base_url}/api/tags", timeout=5.0).raise_for_status()
            return True
        except httpx.HTTPError:
            return False


class MistralBackend:
    """Mistral La Plateforme chat completions backend."""

    _URL = "https://api.mistral.ai/v1/chat/completions"
    _MODELS_URL = "https://api.mistral.ai/v1/models"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float,
        temperature: float,
        client: httpx.Client | None = None,
    ):
        self.name = f"mistral/{model}"
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._client = client

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        requester = self._client or httpx
        try:
            response = requester.post(
                self._URL, json=payload, headers=self._headers, timeout=self._timeout_s
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _map_http_error(exc) from exc
        return response.json()["choices"][0]["message"]["content"]

    def health(self) -> bool:
        requester = self._client or httpx
        try:
            requester.get(self._MODELS_URL, headers=self._headers, timeout=5.0).raise_for_status()
            return True
        except httpx.HTTPError:
            return False


def build_backend(settings: Settings | None = None) -> LLMBackend:
    """Instantiate the configured backend (config validation already ran, F5)."""
    settings = settings or get_settings()
    if settings.llm_backend == "ollama":
        return OllamaBackend(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.ollama_num_ctx,
            timeout_s=settings.ollama_timeout_s,
            temperature=settings.temperature,
        )
    if settings.llm_backend == "mistral":
        # Guaranteed present by config validation, but stay defensive.
        if not settings.mistral_api_key:
            raise LLMBackendError("MISTRAL_API_KEY is not set", cause="auth")
        return MistralBackend(
            api_key=settings.mistral_api_key,
            model=settings.mistral_model,
            timeout_s=settings.mistral_timeout_s,
            temperature=settings.temperature,
        )
    raise LLMBackendError(f"unknown backend: {settings.llm_backend!r}", cause="other")
