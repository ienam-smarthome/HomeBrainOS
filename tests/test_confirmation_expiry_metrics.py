from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from confirmation_store import ConfirmationStore  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def _queue(store: ConfirmationStore, session_id: str) -> None:
    store.queue(
        session_id,
        [("hub_restart", {"device": "1"})],
        [{"role": "user", "content": "restart"}],
        {"role": "assistant", "tool_calls": []},
    )


def test_expired_confirmation_is_counted_at_purge_boundary() -> None:
    now = [100.0]
    store = ConfirmationStore(10, clock=lambda: now[0])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        _queue(store, "first")
        _queue(store, "second")
        now[0] = 111.0

        assert store.consume("first", "confirm") is None
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["confirmation_expired"] == 2


def test_non_expired_and_cancelled_confirmations_are_not_counted() -> None:
    now = [100.0]
    store = ConfirmationStore(10, clock=lambda: now[0])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        _queue(store, "active")
        _queue(store, "cancelled")
        store.cancel("cancelled")

        assert store.consume("active", "confirm") is not None
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)

    assert "confirmation_expired" not in snapshot["counters"]


def test_expiry_outside_request_context_is_ignored() -> None:
    now = [100.0]
    store = ConfirmationStore(10, clock=lambda: now[0])
    _queue(store, "session")
    now[0] = 111.0

    assert store.pending == {}


def test_eviction_under_capacity_pressure_is_counted() -> None:
    """Under sustained pending-session pressure, the oldest pending
    confirmation (which may belong to a wholly different session than the
    one whose queue() call triggers the eviction) used to be dropped with
    no observability at all. `confirmation_evicted` makes that visible in
    the technical metrics panel without changing the eviction itself or
    affecting this request's own outcome classification.
    """

    now = [0.0]
    store = ConfirmationStore(30, max_pending_sessions=2, clock=lambda: now[0])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        _queue(store, "first")
        now[0] = 1.0
        _queue(store, "second")
        now[0] = 2.0
        _queue(store, "third")  # evicts "first"
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["confirmation_evicted"] == 1
    assert set(store.pending) == {"second", "third"}


def test_no_eviction_metric_when_under_capacity() -> None:
    now = [0.0]
    store = ConfirmationStore(30, max_pending_sessions=5, clock=lambda: now[0])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        _queue(store, "first")
        _queue(store, "second")
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)

    assert "confirmation_evicted" not in snapshot["counters"]
