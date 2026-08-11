from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_classification import requests_mutation  # noqa: E402


def test_polite_modal_verb_phrasing_without_please_is_recognised_as_mutation():
    """Regression test: requests_mutation() only recognised imperative
    phrasing ("lock the front door") or "please"-suffixed phrasing
    ("please lock the front door") as a mutation request -- polite
    modal-verb phrasing without "please" fell through unrecognised. This
    gates whether the identity-manifest grounding context gets injected
    for a legitimately mutating request.
    """

    assert requests_mutation("can you lock the front door") is True
    assert requests_mutation("would you set the thermostat to 68") is True
    assert requests_mutation("could you turn off the kitchen light") is True
    assert requests_mutation("will you unlock the back door") is True
    assert requests_mutation("can you please lock the front door") is True


def test_polite_modal_verb_phrasing_for_a_read_only_question_is_not_a_mutation():
    """A polite modal-verb question that isn't asking for a state change at
    all must still be accepted -- only known mutating verbs after the
    modal phrase should count."""

    assert requests_mutation("can you tell me the temperature") is False
    assert requests_mutation("would you check the front door status") is False
