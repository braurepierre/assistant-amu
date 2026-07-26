"""Batch-level retry for long runs of backend calls.

Deliberately kept OUT of the LLM abstraction, which stays "no elaborate retry"
(PRD §7.4): a single ``/ask`` must fail fast and surface a 503. What needs
resilience is the *batch* — a 316-call contextualisation pass, or a 75-call
rewriting pass, will meet the API rate limit sooner or later, and a single 429
after most calls have been paid for loses the whole run.

This module exists because that logic had been written twice, with delays that
had drifted apart (2/5/15 s in the ingestion module, 5/15/45 s in the rewriting
experiment) and only one of the two testable. The longer set is kept: it was
chosen after a real 429 wiped a paid run, and waiting longer costs nothing
compared to losing the batch.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

# Causes worth retrying: transient by nature. Anything else (a bad key, a refused
# model) would fail identically on the next attempt, so it is re-raised at once.
RETRY_CAUSES: tuple[str, ...] = ("quota", "timeout", "connection")
RETRY_DELAYS: tuple[float, ...] = (5.0, 15.0, 45.0)


def with_retry(
    call: Callable[[], T],
    *,
    causes: Iterable[str] = RETRY_CAUSES,
    delays: Iterable[float] = RETRY_DELAYS,
    sleep: Callable[[float], None] = time.sleep,
    notify: Callable[[str], None] = print,
) -> T:
    """Run ``call``, retrying transient ``LLMBackendError`` causes with a backoff.

    ``sleep`` is injectable so the behaviour is testable without a real clock —
    the property the duplicated copy in the rewriting experiment did not have.
    """
    from .generation.llm import LLMBackendError  # local import: avoids a cycle

    causes = tuple(causes)
    delays = tuple(delays)
    for attempt, delay in enumerate((*delays, None), start=1):
        try:
            return call()
        except LLMBackendError as exc:
            if delay is None or exc.cause not in causes:
                raise
            notify(f"    ! {exc.cause} — reprise {attempt}/{len(delays)} dans {delay:g}s")
            sleep(delay)
    raise AssertionError("unreachable: the last iteration either returns or raises")
