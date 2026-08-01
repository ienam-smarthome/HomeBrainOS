from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from confirmation_store import ConfirmationStore  # noqa: E402


def queued(store: ConfirmationStore, session_id: str = "session"):
    return store.queue(
        session_id,
        [("hub_restart", {"device": "1"})],
        [{"role": "user", "content": "restart"}],
        {"role": "assistant", "tool_calls": []},
    )


def test_confirmation_is_session_scoped_and_consumed_once():
    store = ConfirmationStore()
    pending = queued(store, "first")

    assert store.consume("other", "confirm") is None
    assert store.consume("first", "yes proceed") is pending
    assert store.consume("first", "confirm") is None


def test_new_question_cancels_pending_confirmation():
    store = ConfirmationStore()
    queued(store)

    assert store.consume("session", "what is the hub status?") is None
    assert "session" not in store.pending


def test_expired_confirmation_is_purged_before_consumption():
    now = [100.0]
    store = ConfirmationStore(10, clock=lambda: now[0])
    queued(store)
    now[0] = 111.0

    assert store.consume("session", "confirm") is None
    assert store.pending == {}


def test_queue_copies_mutable_action_and_message_inputs():
    store = ConfirmationStore()
    arguments = {"device": "1", "waitFor": {"attribute": "switch"}}
    messages = [{"role": "user", "content": "restart"}]
    assistant = {"role": "assistant", "tool_calls": []}

    pending = store.queue(
        "session",
        [("hub_restart", arguments)],
        messages,
        assistant,
    )
    arguments["device"] = "changed"
    arguments["waitFor"]["attribute"] = "changed"
    messages[0]["content"] = "changed"
    assistant["role"] = "changed"

    assert pending.actions[0][1] == {
        "device": "1",
        "waitFor": {"attribute": "switch"},
    }
    assert pending.messages[0]["content"] == "restart"
    assert pending.assistant_message["role"] == "assistant"


def test_capacity_evicts_the_soonest_expiring_session():
    now = [0.0]
    store = ConfirmationStore(
        30,
        max_pending_sessions=2,
        clock=lambda: now[0],
    )
    queued(store, "first")
    now[0] = 1.0
    queued(store, "second")
    now[0] = 2.0
    queued(store, "third")

    assert set(store.pending) == {"second", "third"}
