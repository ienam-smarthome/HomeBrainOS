"""Cross-device regressions for typed pre-synthesis causal answer composition."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

import pytest
from causal_answer_plan import (
    build_causal_answer_plan,
    render_causal_answer_plan,
    guard_causal_answer_claim_boundaries,
)
from final_answer_coordinator import FinalAnswerCoordinator
from request_metrics import RequestMetrics
from test_independent_transition_provenance_0_17_15 import (
    OFF_QUESTION, _records, _MCP, _run,
)


def _graph(n=2, verified=False):
    return {
        "scope": "single-observed-event",
        "focus": {"subject": "Example Light", "on": "2026-10-12T08:16:10+01:00",
                  "off": "2026-10-12T08:18:23+01:00", "durationSeconds": 133},
        "controllerCandidate": {
            "label": "Example Remote", "status": "repeated-temporal-association",
            "event": "2026-10-12T08:16:10.943+01:00",
            "signedDeltaMs": 82.0, "recordedOrder": "controller-event-after-light-state",
            "repeatedAlignedStarts": 3, "directControllerToDeviceMappingProven": False,
        },
        "postOnCommands": [],
        "transitionEvidence": {
            "off": {
                "observed": True, "time": "2026-10-12T08:18:23+01:00",
                "directCommand": {"producer": {"id": "5", "type": "app"}} if verified else None,
                "state": {"reporter": {"label": "Example Bridge"}},
                "commandHistory": {
                    "checked": True, "eventCount": n,
                    "result": "recorded-command-off-events" if n else "zero-recorded-command-off-events",
                },
                "sensorCorrelations": [
                    {"sensor": "Example FP300", "value": "inactive", "signedDeltaMs": -69.0},
                    {"sensor": "Example Soft Sensor", "value": "inactive", "signedDeltaMs": 949.0},
                ],
                "notifiedListenerContext": {
                    "configuration": {"checked": True, "excerpts": []},
                    "executionLogs": {"checked": True, "observedRows": 0},
                },
                "appProducerContext": {
                    "configuration": {"checked": False},
                    "executionLogs": {"checked": False},
                },
                "internalTimerExecutionVerified": False,
            }
        },
        "offHypotheses": {
            "status": "direct-producer-recorded" if verified else "producer-unresolved",
            "sensorTimerComparisons": [
                {"sensor": "Example FP300", "elapsedBeforeOffMs": 69.0,
                 "configuredDelayMs": 5000.0, "assessment": "too-soon-for-new-timer"},
                {"sensor": "Example Soft Sensor", "elapsedBeforeOffMs": -949.0,
                 "configuredDelayMs": 5000.0, "assessment": "edge-after-off"},
            ],
            "historicalConfigVerified": False, "hypotheses": [
                {"id": "internal-rule", "status": "not-proven"}
            ],
        },
    }


def test_plan_preserves_returned_command_count_without_claiming_no_hub_action():
    plan = build_causal_answer_plan(_graph(), OFF_QUESTION)
    command = plan["evidence"]["offCommand"]
    assert command["returnedCommandEvents"] == 2
    assert command["kind"] == "bounded-command-history-checked"
    assert "older events" in command["interpretation"]
    assert plan["evidence"]["offBoundary"]["reporterRole"] == "reports-state-not-proven-command-issuer"
    assert plan["evidence"]["onControllerContext"]["recordedOrder"] == "controller-event-after-light-state"
    assert not plan["evidence"]["onControllerContext"]["mappingVerified"]
    assert plan["evidence"]["timerComparisons"][0]["assessment"] == "too-soon-for-new-timer"
    rendered = render_causal_answer_plan(_graph(), OFF_QUESTION)
    assert "HOST PRE-SYNTHESIS" in rendered
    assert "timing feasibility" in rendered


def test_guard_rejects_absolute_off_issuance_and_false_zero_history():
    draft = (
        "No \`off\` command was issued by the hub.\n"
        "The command history for this specific transition returned zero entries.\n"
    )
    fixed, changed = guard_causal_answer_claim_boundaries(draft, _graph(), OFF_QUESTION)
    assert changed
    assert "does not prove that the hub issued no command" in fixed
    assert "returned 2 recorded command events" in fixed
    assert "returned zero entries" not in fixed


def test_zero_matching_events_is_not_zero_returned_rows():
    draft = "There are zero matching command events for the requested OFF."
    fixed, changed = guard_causal_answer_claim_boundaries(draft, _graph(), OFF_QUESTION)
    assert not changed
    assert fixed == draft


def test_on_only_mixed_or_unknown_scope_not_rewritten():
    draft = "No \`off\` command was issued by the hub."
    for question in (
        "Why did Example Light turn ON?",
        "Explain Example Light ON and OFF.",
        "What happened yesterday?",
    ):
        assert build_causal_answer_plan(_graph(), question) is None
        assert guard_causal_answer_claim_boundaries(draft, _graph(), question) == (draft, False)


def test_direct_verified_off_producer_is_not_suppressed():
    draft = "The app sent off()."
    assert guard_causal_answer_claim_boundaries(draft, _graph(verified=True), OFF_QUESTION) == (draft, False)


@pytest.mark.asyncio
async def test_coordinator_supplies_pre_synthesis_plan_in_single_round():
    rows, _ = await _run(_records(), _MCP(off_events=[]),
                         question=OFF_QUESTION, transition="off")
    calls = []
    async def fake_chat(messages, tools):
        calls.append((messages, tools))
        return {"content": (
            "The focal OFF state was observed. Its command producer is unverified. "
            "Sensor inactivity is a temporal correlation, not verified cause."
        )}
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        coord = FinalAnswerCoordinator(fake_chat, evidence_supplier=lambda: rows)
        answer = await coord.answer([{"role": "user", "content": OFF_QUESTION}])
        counters = metrics.snapshot()["counters"]
    finally:
        metrics.reset(token)
    assert len(calls) == 1, counters
    plan_messages = [
        m["content"] for m in calls[0][0] if isinstance(m, dict)
        and "HOST PRE-SYNTHESIS CAUSAL ANSWER PLAN" in str(m.get("content") or "")
    ]
    assert len(plan_messages) == 1
    assert "reported-state" not in answer.lower() or "producer" in answer.lower()
    assert "timerComparisons" in plan_messages[0]
