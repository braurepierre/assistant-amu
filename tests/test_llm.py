"""Tests for the LLM backends (PRD §7.4, F5). No real network."""

from __future__ import annotations

import json

import httpx
import pytest

from assistant_amu.config import load_settings
from assistant_amu.generation.llm import (
    LLMBackendError,
    MistralBackend,
    OllamaBackend,
    build_backend,
)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ollama_generate_sends_num_ctx_and_returns_content():
    def handler(request):
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["options"]["num_ctx"] == 8192  # piège n°3: explicit window
        assert body["options"]["temperature"] == 0.2
        return httpx.Response(200, json={"message": {"content": "Reponse [S1]"}})

    backend = OllamaBackend(
        base_url="http://localhost:11434", model="mistral", num_ctx=8192,
        timeout_s=5, temperature=0.2, client=_client(handler),
    )
    assert backend.name == "ollama/mistral"
    assert backend.generate("system", "user") == "Reponse [S1]"


def test_mistral_generate_sends_auth_and_returns_content():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer secret-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    backend = MistralBackend(
        api_key="secret-key", model="mistral-small-latest", timeout_s=5,
        temperature=0.2, client=_client(handler),
    )
    assert backend.generate("s", "u") == "OK"


@pytest.mark.parametrize("status,cause", [(401, "auth"), (403, "auth"), (429, "quota"), (500, "other")])
def test_http_status_maps_to_cause(status, cause):
    backend = OllamaBackend(
        base_url="http://x", model="m", num_ctx=8192, timeout_s=5, temperature=0.2,
        client=_client(lambda request: httpx.Response(status)),
    )
    with pytest.raises(LLMBackendError) as exc_info:
        backend.generate("s", "u")
    assert exc_info.value.cause == cause


def test_timeout_maps_to_timeout_cause():
    def handler(request):
        raise httpx.TimeoutException("slow")

    backend = OllamaBackend(base_url="http://x", model="m", num_ctx=8192, timeout_s=1,
                            temperature=0.2, client=_client(handler))
    with pytest.raises(LLMBackendError) as exc_info:
        backend.generate("s", "u")
    assert exc_info.value.cause == "timeout"


def test_connect_error_maps_to_connection_cause():
    def handler(request):
        raise httpx.ConnectError("refused")

    backend = OllamaBackend(base_url="http://x", model="m", num_ctx=8192, timeout_s=1,
                            temperature=0.2, client=_client(handler))
    with pytest.raises(LLMBackendError) as exc_info:
        backend.generate("s", "u")
    assert exc_info.value.cause == "connection"


def test_health_reflects_reachability():
    up = OllamaBackend(base_url="http://x", model="m", num_ctx=8192, timeout_s=1,
                       temperature=0.2, client=_client(lambda r: httpx.Response(200, json={})))
    down = OllamaBackend(base_url="http://x", model="m", num_ctx=8192, timeout_s=1,
                         temperature=0.2, client=_client(lambda r: httpx.Response(500)))
    assert up.health() is True
    assert down.health() is False


def test_build_backend_selects_by_setting(monkeypatch):
    for var in ("LLM_BACKEND", "MISTRAL_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    assert isinstance(build_backend(load_settings()), OllamaBackend)

    monkeypatch.setenv("LLM_BACKEND", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert isinstance(build_backend(load_settings()), MistralBackend)
