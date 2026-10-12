"""Generic evidence-completion and cross-format certainty regressions.

The live 0.17.15 OFF-only test made ten model rounds and broadened across
unrelated rooms although its exact target, OFF command page, app logs, config
and FP300/Soft Sensor event timing were already checked. Its prose and certainty
table then falsely inferred that missing records PROVED no Hubitat role and
that the external automation route was likely. Test the source/claim contract
rather than making a Bedroom-specific final answer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_completion_policy import (  # noqa: E402
    evaluate_causal_completion,
    requested_transition_scope,
)
from causal_certainty_contract import guard_off_certainty_contract  # noqa: E402
from causal_evidence_graph import (  # noqa: E402
    build_causal_evidence_graph, supports_one_pass_deep_synthesis,
)
from causal_investigation_engine import (  # noqa: E402
    has_local_requested_off_correlation,
)
from causal_claim_verification import verify_causal_claims  # noqa: E402
from api_response_builder import build_agent_response  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from test_independent_transition_provenance_0_17_15 import (  # noqa: E402
    OFF_QUESTION, QUESTION as ON_QUESTION,
    _records, _MCP, _run,
)


OFF_EXTERNAL = OFF_QUESTION.replace(
    "possible alternative causes", "possible external causes"
)
OFF_SYNONYM = OFF_QUESTION.replace(
    "possible alternative causes", "potential non-Hubitat explanations"
)

ON_AND_OFF_DRAFT = """Investigation Summary:
The turn-on is strongly associated with the physical dimmer button.
The OFF event lacks a proven command producer.

| Transition | Time | Proven Actor | Likely Actor | Evidence |
|---|---|---|---|---|
| ON | 08:16:10 | None | Bedroom dimmer | Repeated button timing |
| OFF | 08:18:23 | None | Motion-based automation | FP300 inactive 69ms before OFF |
"""

OFF_ONLY_DRAFT = """The investigation of why the light switched OFF at 08:18 concludes the
initiator remains unresolved, as no command was issued by Hubitat.

### 1. Confirmed Evidence
- No Hubitat Command: There is no recorded off command for this window. This confirms that no Hubitat-native rule, app or manual dashboard interaction triggered the transition.
- App Reaction: Its execution logs were empty, confirming it did not issue the command.
### 3. Alternative Causes
- Physical Interaction: Ruled out. No button push was recorded.
- Hubitat App: The empty execution logs prove this app did not initiate the OFF event.

| Element | Status | Detail |
|---|---|---|
| Command Producer | Unresolved | No matched Hubitat command |
| Trigger | Likely External | FP300 inactive 69ms before OFF |
| Confirmed | State Change | Hue Bridge reported OFF |
| Likely | Causal Link | FP300 \\rightarrow External Automation \\rightarrow Light OFF |
"""


def _local_off_analysis():
    return {
        "transition": "off",
        "requestedBoundary": "2026-10-12T08:18:23.830+0100",
        "sensors": [{
            "label": "Generic Room FP Sensor",
            "relevantCorrelations": [{
                "boundaryRole": "end",
                "subjectTransition": "2026-10-12T08:18:23.830+0100",
                "sensorEvent": "2026-10-12T08:18:23.761+0100",
                "eventValue": "inactive",
                "signedDeltaSeconds": -.069,
            }],
        }],
    }


@pytest.mark.asyncio
async def test_off_only_completion_uses_evidence_not_request_wording():
    rows, _ = await _run(_records(), _MCP(off_events=[]),
                         question=OFF_EXTERNAL, transition="off")
    graph = build_causal_evidence_graph(rows, OFF_EXTERNAL)
    assert requested_transition_scope(OFF_EXTERNAL) == "off"
    for question in (OFF_EXTERNAL, OFF_SYNONYM, OFF_QUESTION):
        decision = evaluate_causal_completion(graph, question)
        assert decision["complete"], decision
        assert decision["outcome"] == "completed-unresolved"
        assert decision["absenceOfLoggedCommandIsNotExclusion"]
        assert supports_one_pass_deep_synthesis(graph, question)
    assert not graph["transitionEvidence"]["off"]["directCommand"]


@pytest.mark.asyncio
async def test_off_completion_requires_checked_sources_not_proven_actor():
    rows, _ = await _run(_records(), _MCP(off_events=[]),
                         question=OFF_EXTERNAL, transition="off")
    graph = build_causal_evidence_graph(rows, OFF_EXTERNAL)
    for name in (
        "room-sensor-evidence-checked",
        "off-event-log-window-checked",
        "relevant-app-configuration-checked",
        "off-command-checked-or-proven",
    ):
        changed = dict(graph)
        changed["transitionEvidence"] = {
            **graph["transitionEvidence"],
            "off": dict(graph["transitionEvidence"]["off"]),
        }
        off = changed["transitionEvidence"]["off"]
        if name == "room-sensor-evidence-checked":
            changed["otherSensorEvidenceChecked"] = False
        elif name == "off-event-log-window-checked":
            off["notifiedListenerContext"] = {
                **off["notifiedListenerContext"],
                "executionLogs": {"checked": False}
            }
        elif name == "relevant-app-configuration-checked":
            off["notifiedListenerContext"] = {
                **off["notifiedListenerContext"],
                "configuration": {"checked": False}
            }
        else:
            off["commandHistory"] = {"checked": False, "result": "not-checked"}
        decision = evaluate_causal_completion(changed, OFF_EXTERNAL)
        assert not decision["complete"] and name in decision["unchecked"]


def test_room_off_edge_stops_cross_room_expansion_but_is_not_proof():
    a = _local_off_analysis()
    assert has_local_requested_off_correlation(a)
    a["sensors"][0]["relevantCorrelations"][0]["signedDeltaSeconds"] = 6
    assert not has_local_requested_off_correlation(a)
    a["sensors"][0]["relevantCorrelations"][0]["signedDeltaSeconds"] = .949
    assert has_local_requested_off_correlation(a)
    a["sensors"][0]["relevantCorrelations"][0]["boundaryRole"] = "start"
    assert not has_local_requested_off_correlation(a)
    a["sensors"][0]["relevantCorrelations"][0]["boundaryRole"] = "end"
    a["sensors"][0]["relevantCorrelations"][0]["subjectTransition"] = (
        "2026-10-12T08:10:42.000+0100"
    )
    assert not has_local_requested_off_correlation(a)
    a["transition"] = "on"
    assert not has_local_requested_off_correlation(a)


def test_all_history_off_investigation_preserves_on_versus_off_table_certainty():
    graph = build_causal_evidence_graph(_records(), ON_QUESTION)
    result, corrected = guard_off_certainty_contract(
        ON_AND_OFF_DRAFT, graph, ON_QUESTION
    )
    assert corrected
    assert "ON | 08:16:10 | None | Bedroom dimmer" in result
    assert "Motion-based automation" not in result
    assert "OFF | 08:18:23" in result
    assert "Unverified" in result
    assert "no OFF command owner established" in result


def test_off_only_categorical_exclusions_and_invented_external_path_are_corrected():
    graph = build_causal_evidence_graph(_records(), OFF_EXTERNAL)
    fixed, changed = guard_off_certainty_contract(
        OFF_ONLY_DRAFT, graph, OFF_EXTERNAL
    )
    assert changed
    assert "no command was issued by Hubitat" not in fixed
    assert "confirms that no Hubitat-native rule" not in fixed
    assert "empty, confirming it did not" not in fixed
    assert "Physical Interaction: Ruled out" not in fixed
    assert "logs prove this app did not" not in fixed
    assert "Likely External" not in fixed
    assert "FP300 \\rightarrow External Automation" not in fixed
    assert "| Trigger | Unverified |" in fixed
    assert "| Likely | Unverified |" in fixed
    assert "temporal correlation" in fixed
    assert "No matched Hubitat command" in fixed
    assert "Hue Bridge reported OFF" in fixed
    again, changed = guard_off_certainty_contract(
        fixed, graph, OFF_EXTERNAL
    )
    assert again == fixed and not changed


@pytest.mark.asyncio
async def test_final_verifier_and_api_preserve_same_unresolved_off_verdict():
    rows, _ = await _run(_records(), _MCP(off_events=[]),
                         question=OFF_EXTERNAL, transition="off")
    # Production host correlation receipts explicitly carry the unique focal
    # requested boundary. Keep that binding so API serialization can re-scope
    # its final safety check without being passed arbitrary model user text.
    next(row for row in rows if
         row.get("tool") == "homebrain_causal_secondary_correlation"
    )["details"]["requestedBoundary"] = "2026-10-12T08:16:10.861+0100"
    corrected, issues = verify_causal_claims(OFF_ONLY_DRAFT, rows, OFF_EXTERNAL)
    assert "causal_off_certainty_contract" in issues
    assert "Likely External" not in corrected
    assert "logs prove" not in corrected

    outcome = SimpleNamespace(
        message=OFF_ONLY_DRAFT, evidence=rows,
        metrics={"outcome": "success", "counters": {"model_rounds": 1}},
        route="unified-mcp-agent", request_class="live-read",
    )
    result = build_agent_response(
        outcome, model="model", elapsed_ms=14000, version="0.17.16",
    )
    assert "Likely External" not in result["message"]
    assert "| Trigger | Unverified |" in result["message"]


@pytest.mark.asyncio
async def test_verified_off_evidence_finalizes_locally_in_one_model_round():
    rows, _ = await _run(_records(), _MCP(off_events=[]),
                         question=OFF_EXTERNAL, transition="off")
    calls = []
    async def fake_chat(messages, tools):
        calls.append((messages, tools))
        return {"content": OFF_ONLY_DRAFT}
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        coordinator = FinalAnswerCoordinator(
            fake_chat, evidence_supplier=lambda: rows
        )
        answer = await coordinator.answer([{
            "role": "user", "content": OFF_EXTERNAL
        }])
        counter = metrics.snapshot()["counters"]
    finally:
        metrics.reset(token)
    assert "Likely External" not in answer
    assert len(calls) == 1, counter
    assert counter.get("synthesis_localized_corrections") == 1
    assert counter.get("synthesis_repair_rounds", 0) == 0


def test_without_unique_focal_event_contract_does_not_guess():
    rows = _records()
    graph = build_causal_evidence_graph(
        rows, "Why did an unknown light go off sometime last week?"
    )
    assert graph["scope"] != "single-observed-event"
    unchanged, changed = guard_off_certainty_contract(
        OFF_ONLY_DRAFT, graph, OFF_EXTERNAL
    )
    assert not changed and unchanged == OFF_ONLY_DRAFT
