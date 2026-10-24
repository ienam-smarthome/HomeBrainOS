"""0.18.101: model-chosen read objective outranks incidental keyword classifiers.

No writes are executed. Direct controls remain guarded by independent host
authorization; only one pre-existing no-tools read interpretation is reused.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, active_request_interpretation,
    set_request_interpretation, reset_request_interpretation,
)
from adaptive_investigation_policy import (
    model_led_investigation_request, source_evidence_request,
)
from device_incident_depth import is_connectivity_root_cause_request
from targeted_rule_scope_policy import (
    is_existing_rule_verification_request,
    is_new_rule_design_review_request, is_targeted_rule_investigation,
)
from mcp_agent_orchestrator import _explicit_mutation_request

def scoped(question: str, kind: str):
    return set_request_interpretation(
        question, ReadRouteDecision(
            "model_led", "model_choice", objective=kind,
            target="installed device", purpose="verify evidence",
        ),
    )


def test_semantic_objective_allows_ordinary_root_cause_wording():
    question = "What accounts for the contradictory state of device 7103?"
    assert not model_led_investigation_request(question)
    token = scoped(question, "device_connectivity")
    try:
        assert model_led_investigation_request(question)
        assert is_connectivity_root_cause_request(question)
        assert not source_evidence_request(question)
    finally:
        reset_request_interpretation(token)
    assert not model_led_investigation_request(question)


def test_source_code_is_a_model_objective_not_incidental_word():
    question = (
        "Audit Bedroom 3 Mesh app 3999 logs and Groovy source, "
        "but determine why its telemetry is stale."
    )
    token = scoped(question, "device_connectivity")
    try:
        assert model_led_investigation_request(question)
        assert not source_evidence_request(question)
        assert not is_existing_rule_verification_request(question)
        assert not is_new_rule_design_review_request(question)
    finally:
        reset_request_interpretation(token)

    question = "Read the implementation of installed app 3977."
    token = scoped(question, "source_code")
    try:
        assert source_evidence_request(question)
        assert model_led_investigation_request(question)
    finally:
        reset_request_interpretation(token)


def test_model_suppresses_legacy_read_router_keywords():
    question = (
        "Please investigate the exact configuration of app 4239; "
        "do not design any automation."
    )
    token = scoped(question, "device_connectivity")
    try:
        assert not is_existing_rule_verification_request(question)
        assert not is_new_rule_design_review_request(question)
        assert model_led_investigation_request(question)
    finally:
        reset_request_interpretation(token)


def test_direct_device_command_is_never_promoted_into_investigation():
    for question in (
        "Turn on TV", "Switch off living room lights",
        "Set Bedroom 1 thermostat to 21 degrees",
    ):
        assert _explicit_mutation_request(question)
        token = scoped(question, "source_code")
        try:
            assert not model_led_investigation_request(question)
            assert not source_evidence_request(question)
        finally:
            reset_request_interpretation(token)


def test_request_context_does_not_leak_between_concurrent_goals():
    a = "Explain device A malfunction"
    b = "Check device B status"
    token = scoped(a, "device_connectivity")
    try:
        assert model_led_investigation_request(a)
        assert active_request_interpretation(b) is None
    finally:
        reset_request_interpretation(token)


@pytest.mark.asyncio
async def test_ai_interprets_targeted_rule_incident_before_word_router(monkeypatch):
    import app
    question = (
        "Review app 3999 configuration and runtime logs to determine "
        "why the Bedroom 3 Mesh device is offline. Read-only."
    )
    assert is_targeted_rule_investigation(question)
    observed = []

    async def decide(_chat, prompt):
        observed.append(("interpreted", prompt))
        return ReadRouteDecision(
            "model_led", "model_choice", objective="device_connectivity",
            target="Bedroom 3 Mesh",
            purpose="identify missing telemetry cause",
        )

    async def agent_response(*_args, **_kwargs):
        choice = active_request_interpretation(question)
        assert choice is not None
        assert choice.objective == "device_connectivity"
        assert model_led_investigation_request(question)
        assert not is_existing_rule_verification_request(question)
        observed.append(("agent", choice.objective))
        return SimpleNamespace(
            message="Missing telemetry cause remains unverified.",
            route="unified-mcp-agent", request_class="live-read",
            evidence=[], choices=[], confirmation_required=False,
        )

    monkeypatch.setattr(app, "decide_read_route", decide)
    monkeypatch.setattr(app.agent, "process_user_request_result", agent_response)
    result = await app._agent_request(app.ChatRequest(prompt=question))
    assert result.route == "unified-mcp-agent"
    assert observed == [("interpreted", question), ("agent", "device_connectivity")]
    assert active_request_interpretation(question) is None


def test_model_ownership_does_not_change_host_write_gate():
    src = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "interpreted_kind == \"rule_design_review\"" in src
    assert "interpreted_kind == \"existing_rule_verification\"" in src
    assert "not _explicit_mutation_request(user_prompt)" in src
    assert "not self._mutation_requested_by_user.get()" in src
