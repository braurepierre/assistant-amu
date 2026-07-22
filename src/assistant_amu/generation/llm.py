"""LLM backend abstraction (PRD §7.4).

A single ``LLMBackend`` protocol with two implementations selected by
``LLM_BACKEND``: ``OllamaBackend`` (POST /api/chat, stream=false, explicit
num_ctx) and ``MistralBackend`` (chat completions). No streaming, no elaborate
retry, no state. Errors surface as ``LLMBackendError`` with a normalised cause.

Not yet implemented — Phase 3.
"""

from __future__ import annotations

# TODO(Phase 3): LLMBackend Protocol + OllamaBackend + MistralBackend (§7.4, F5).
