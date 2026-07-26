from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from assistant_contracts import VerificationOutcome
from verification_service import coerce_bool, deep_field, verify_boolean_state


def test_write_response_verifies_requested_state():
    result = verify_boolean_state(
        expected=True,
        field_names=("paused",),
        write_payload={"result": {"paused": True}},
    )
    assert result.outcome is VerificationOutcome.COMPLETED
    assert result.verified is True
    assert result.observed is True
    assert result.source == "write response"


def test_independent_readback_verifies_when_write_omits_state():
    result = verify_boolean_state(
        expected=False,
        field_names=("disabled",),
        write_payload={"success": True},
        readback_payload={"rules": [{"id": 2844, "disabled": False}]},
    )
    assert result.outcome is VerificationOutcome.COMPLETED
    assert result.verified is True
    assert result.source == "inventory read-back"


def test_accepted_command_remains_sent_when_state_is_unavailable():
    result = verify_boolean_state(
        expected=True,
        field_names=("disabled",),
        write_payload={"success": True},
    )
    assert result.outcome is VerificationOutcome.SENT
    assert result.verified is False
    assert result.observed is None
    assert result.accepted_only is True


def test_conflicting_observed_state_is_not_verified():
    result = verify_boolean_state(
        expected=True,
        field_names=("paused",),
        write_payload={"paused": False},
        readback_payload={"paused": False},
    )
    assert result.outcome is VerificationOutcome.SENT
    assert result.verified is False
    assert result.observed is False


def test_failed_command_never_reports_sent_or_completed():
    result = verify_boolean_state(
        expected=True,
        field_names=("paused",),
        write_payload={"paused": True},
        command_failed=True,
    )
    assert result.outcome is VerificationOutcome.FAILED
    assert result.verified is False
    assert result.observed is None


def test_nested_field_and_boolean_coercion_are_shared():
    payload = {"data": [{"attributes": {"disabled": "true"}}]}
    assert deep_field(payload, ("disabled",)) == "true"
    assert coerce_bool("true") is True
    assert coerce_bool("false") is False
    assert coerce_bool("unknown") is None
