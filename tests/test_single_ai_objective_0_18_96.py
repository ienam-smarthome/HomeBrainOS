"""0.18.96: one AI-interpreted user goal across routing, rules, tools and evidence.

Models choose the question's diagnostic subject. They cannot grant a write,
prove a device ID or change verified MCP evidence. Each context is local to
one request; malformed model output falls back to host-safe legacy handling.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_investigation_routing import (
    ReadRouteDecision, active_request_interpretation, decide_read_route,
    set_request_interpretation, reset_request_interpretation,
    without_request_interpretation,
)
from investigation_objective import resolve_primary_objective
from investigation_intelligence import plan_investigation
from device_incident_depth import is_connectivity_root_cause_request
from targeted_rule_scope_policy import (
    is_existing_rule_verification_request,
    is_new_rule_design_review_request,
)
from rule_authoring_service import RuleAuthoringService
from mcp_agent_orchestrator import _explicit_mutation_request


DEVICE_QUESTION = (
    "Why does Bedroom 3 Mesh report offline while MQTT says connected? "
    "Investigate thoroughly and examine the relevant automation behaviour. "
    "Use read-only MCP checks. Do not change anything."
)
DESIGN = (
    "Design a new automation for night motion lighting. "
    "Read-only design review; do not create it."
)
GROOVY = (
    "Investigate Groovy source code for installed App 3977 and "
    "the setReportData LimitExceededException."
)


def with_objective(question, kind):
    return set_request_interpretation(
        question,
        ReadRouteDecision(
            "model_led", "model_choice", objective=kind,
            target="Bedroom 3 Mesh", purpose="find actual root cause",
        ),
    )


def test_device_incident_remains_connectivity_without_rule_design():
    token = with_objective(DEVICE_QUESTION, "device_connectivity")
    try:
        assert active_request_interpretation(DEVICE_QUESTION).objective == "device_connectivity"
        assert is_connectivity_root_cause_request(DEVICE_QUESTION)
        assert not is_existing_rule_verification_request(DEVICE_QUESTION)
        assert not is_new_rule_design_review_request(DEVICE_QUESTION)
        assert not RuleAuthoringService.is_read_only_rule_design_request(DEVICE_QUESTION)
        contract = plan_investigation(DEVICE_QUESTION)
        assert contract is not None
        assert contract.domain == "device_telemetry"
        assert resolve_primary_objective(DEVICE_QUESTION).domain == "general"
    finally:
        reset_request_interpretation(token)
    assert active_request_interpretation(DEVICE_QUESTION) is None


def test_explicit_design_remains_proposal_only_with_separate_write_permissions():
    token = with_objective(DESIGN, "rule_design_review")
    try:
        assert plan_investigation(DESIGN).domain == "rule_design_review"
        assert RuleAuthoringService.is_read_only_rule_design_request(DESIGN)
        assert is_new_rule_design_review_request(DESIGN)
    finally:
        reset_request_interpretation(token)


def test_ai_cannot_relabel_an_imperative_as_safe_read():
    question = "Create a new Rule Machine automation right now."
    token = with_objective(question, "rule_design_review")
    try:
        assert _explicit_mutation_request(question)
        with without_request_interpretation():
            assert active_request_interpretation(question) is None
        assert active_request_interpretation(question).objective == "rule_design_review"
    finally:
        reset_request_interpretation(token)


def test_source_domain_keeps_real_app_instance_and_method_not_inferred_code_id():
    token = with_objective(GROOVY, "source_code")
    try:
        objective = resolve_primary_objective(GROOVY)
        assert objective.is_source
        assert objective.installed_app_id == "3977"
        assert objective.method_symbol == "setReportData"
        assert plan_investigation(GROOVY) is None
    finally:
        reset_request_interpretation(token)


def test_multiple_requests_do_not_see_each_others_objective():
    token = with_objective(DEVICE_QUESTION, "device_connectivity")
    try:
        assert active_request_interpretation(DESIGN) is None
        assert plan_investigation(DESIGN).domain == "rule_design_review"
    finally:
        reset_request_interpretation(token)


@pytest.mark.asyncio
async def test_model_interprets_target_and_purpose_in_same_no_tools_round():
    called = []
    async def model(messages, tools):
        called.append((messages, tools))
        return {"content": (
            '{"route":"model_led","objective":"device_connectivity",'
            '"target":"Bedroom 3 Mesh","purpose":"explain MQTT/offline mismatch"}'
        )}
    result = await decide_read_route(model, DEVICE_QUESTION)
    assert result.route == "model_led"
    assert result.objective == "device_connectivity"
    assert result.target == "Bedroom 3 Mesh"
    assert "offline mismatch" in result.purpose
    assert len(called) == 1 and called[0][1] == []


@pytest.mark.asyncio
async def test_unknown_or_invalid_interpretation_does_not_grant_authority():
    async def invalid(messages, tools):
        return {"content": '{"route":"system_audit","objective":"mutate_all_devices"}'}
    result = await decide_read_route(invalid, DEVICE_QUESTION)
    assert result.route == "model_led"
    assert result.objective == "general_investigation"
    async def old(messages, tools):
        return {"content": '{"route":"model_led"}'}
    legacy = await decide_read_route(old, DEVICE_QUESTION)
    assert legacy.objective == "general_investigation"


def test_code_wires_single_interpretation_into_all_stages():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    agent = (ROOT / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    finish = (ROOT / "final_answer_coordinator.py").read_text(encoding="utf-8")
    report = (ROOT / "shared_investigation_completion.py").read_text(encoding="utf-8")
    observed = (ROOT / "observed_agent_outcome.py").read_text(encoding="utf-8")
    assert "interpretation_token = set_request_interpretation(" in app
    assert "if (candidate_fast_path and not targeted_rule" in app
    assert '"model_led" if targeted_device else decision.route' in app
    assert "reset_request_interpretation(interpretation_token)" in app
    assert "interpreted_intent=outcome.interpreted_intent" in observed
    assert "interpreted_kind = interpreted.objective" in agent
    assert "interpreted_kind = interpreted.objective" in finish
    assert "interpreted_kind = interpreted.objective" in report
