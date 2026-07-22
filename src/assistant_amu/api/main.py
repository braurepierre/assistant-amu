"""FastAPI app and endpoints (PRD §7.5).

Validates configuration at import time via ``get_settings()`` so misconfiguration
fails at startup, not on the first request (F5). Interactive docs at ``/docs``.

Not yet implemented — Phase 4.
"""

from __future__ import annotations

# TODO(Phase 4): FastAPI app, POST /ask, POST /ingest, GET /health (§7.5, F7).
