"""Tests for the shared batch-level retry (assistant_amu.backoff). No network, no clock.

The logic had been written twice — in the ingestion module and in the rewriting
experiment — with delays that had drifted apart and only one copy testable. These
tests cover the single implementation, sleep injected so no real time passes.
"""

from __future__ import annotations

import pytest

from assistant_amu.backoff import RETRY_DELAYS, with_retry
from assistant_amu.generation.llm import LLMBackendError


class Flaky:
    """Fails `fail_times` times with `cause`, then returns a value."""

    def __init__(self, cause: str = "quota", fail_times: int = 1, value: str = "ok"):
        self.cause = cause
        self.fail_times = fail_times
        self.value = value
        self.attempts = 0

    def __call__(self) -> str:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise LLMBackendError("boom", cause=self.cause)
        return self.value


def recorder():
    slept: list[float] = []
    return slept, slept.append


def test_returns_immediately_when_the_call_succeeds():
    slept, sleep = recorder()
    call = Flaky(fail_times=0)

    assert with_retry(call, sleep=sleep, notify=lambda _: None) == "ok"
    assert call.attempts == 1
    assert slept == []


def test_retries_a_transient_cause_and_eventually_succeeds():
    slept, sleep = recorder()
    call = Flaky(cause="quota", fail_times=2)

    assert with_retry(call, sleep=sleep, notify=lambda _: None) == "ok"
    assert call.attempts == 3
    assert slept == list(RETRY_DELAYS[:2])  # backoff grows, and is not slept past success


def test_gives_up_after_the_last_delay_and_re_raises():
    slept, sleep = recorder()
    call = Flaky(cause="timeout", fail_times=99)

    with pytest.raises(LLMBackendError):
        with_retry(call, sleep=sleep, notify=lambda _: None)

    assert call.attempts == len(RETRY_DELAYS) + 1  # one initial try, then one per delay
    assert slept == list(RETRY_DELAYS)


def test_a_non_transient_cause_is_re_raised_at_once():
    """A bad key fails identically on the next attempt — retrying only wastes time."""
    slept, sleep = recorder()
    call = Flaky(cause="auth", fail_times=99)

    with pytest.raises(LLMBackendError):
        with_retry(call, sleep=sleep, notify=lambda _: None)

    assert call.attempts == 1
    assert slept == []


def test_delays_and_causes_are_overridable():
    slept, sleep = recorder()
    call = Flaky(cause="rate", fail_times=1)

    assert with_retry(call, causes=("rate",), delays=(0.5,), sleep=sleep,
                      notify=lambda _: None) == "ok"
    assert slept == [0.5]


def test_notify_reports_each_retry():
    messages: list[str] = []
    call = Flaky(cause="connection", fail_times=2)

    with_retry(call, sleep=lambda _: None, notify=messages.append)

    assert len(messages) == 2
    assert "connection" in messages[0]
