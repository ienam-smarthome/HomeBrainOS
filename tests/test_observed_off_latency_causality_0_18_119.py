"""Regression: a child-app performance WARN is not a proven later OFF delay.

Read-only synthetic replay of the actual 2026-10-25 0.18.118 response:
FP400 and LWR01 inactive to controller OFF gaps ~30s, a separate
129,544ms Hubitat child-app WARN, and bounded switch ON intervals.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from api_response_builder import build_agent_response
from observed_long_method_guard import observed_long_method_warnings
from observed_off_latency_causality import guard_observed_off_latency_causality


VERDICT = (
    "Based on the available evidence, the most likely cause for Livingroom "
    "Light 1 staying ON longer than expected is severe execution delays "
    "within App 4019.\n\n"
    "### The Smoking Gun\n"
    "At 16:18:42, motionHandler ran for 129,544ms and prevented the OFF "
    "timer from starting promptly.\n\n"
    "**Conclusion:** The light stays on because App 4019 is failing to "
    "process motion events in a timely manner."
)


def row(tool, details, sub_tool=None):
    return dict(
        tool=tool, sub_tool=sub_tool, details=details,
        evidence_kind="tool_result", success=True,
        mutates=False, effect="read", arguments={},
    )


def event(name, time, value=None, app=None, listener=None):
    output = {
        "name": name, "value": value,
        "date": "2026-10-25T" + time + "+0000",
    }
    if app is not None:
        output["producedBy"] = {"type": "app", "id": str(app)}
    if listener is not None:
        output["triggered"] = [
            {"appId": listener, "handler": "motionHandler"},
        ]
    return output


def evidence(app="4019", *, sensor_listeners=True, gaps=True):
    t1 = "16:58:28.633" if gaps else "16:56:28.633"
    return [
        row("homebrain_device_history", {
            "label": "Livingroom Light 1", "attribute": "switch",
            "boundaryEvents": [
                event("command-off", "16:58:58.691", app=app),
                event("switch", "16:58:58.937", value="off"),
                event("command-off", "17:01:16.922", app=app),
                event("switch", "17:01:17.095", value="off"),
                # The first setLevel is AFTER the ON transition; no proof
                # that this app initiated the first ON.
                event("switch", "16:30:46.568", value="on"),
                event("command-setLevel", "16:30:46.603", app=app),
            ],
            "temporalAnalysis": {
                "observedIntervals": [
                    {"start": "2026-10-25T16:30:46.568+0000",
                     "end": "2026-10-25T16:58:58.937+0000"},
                    {"start": "2026-10-25T16:59:15.394+0000",
                     "end": "2026-10-25T17:01:17.095+0000"},
                ],
            },
        }),
        row("homebrain_device_history", {
            "label": "FP400 motion sensor", "attribute": "motion",
            "boundaryEvents": [
                event("motion", t1, value="inactive",
                      listener=int(app) if sensor_listeners else 4444),
            ],
        }),
        row("homebrain_device_history", {
            "label": "Matter LWR01 Livingroom Occupancy",
            "attribute": "motion",
            "boundaryEvents": [
                event("motion", "17:00:46.653", value="inactive",
                      listener=int(app) if sensor_listeners else 4444),
            ],
        }),
        row("hub_read_diagnostics", {
            "logCount": 1,
            "logs": [{
                "date": "2026-10-25 16:18:42.628",
                "level": "WARN",
                "message": (
                    "app|" + app +
                    "|Livingroom Light 1 (⚪ Lights Off, 🏃 Motion Active)|"
                    "method motionHandler of child app Livingroom Light 1 "
                    "ran for 129,544ms"
                ),
            }],
        }, sub_tool="hub_get_logs"),
    ]


def test_real_child_app_warn_variant_is_detected_as_typed():
    data = observed_long_method_warnings(evidence())
    assert data["4019"]["durations_ms"] == [129544]
    assert data["4019"]["methods"] == ("motionHandler",)
    assert data["4019"]["timestamps"] == ["2026-10-25 16:18:42.628"]


def test_confident_handler_lag_story_is_replaced_by_measured_timing():
    final, changed = guard_observed_off_latency_causality(VERDICT, evidence())
    assert changed
    assert "16:58:28.633" in final and "16:58:58.691" in final
    assert "30.058s later" in final
    assert "17:00:46.653" in final and "17:01:16.922" in final
    assert "30.269s later" in final
    assert "0.246s" in final and "0.173s" in final
    assert "129,544ms (129.544s)" in final
    assert "16:18:42.628" in final
    assert "28m 12s" in final
    assert "Root cause not independently verified" in final
    assert "Smoking Gun" not in final
    assert "The light stays on because" not in final
    assert "configuration" in final
    assert "physical absence" in final


def test_different_app_warn_cannot_explain_target_off_commands():
    rows = evidence()
    rows[-1]["details"]["logs"][0]["message"] = (
        "app|7777|Unrelated|method motionHandler of child app "
        "Unrelated ran for 129,544ms"
    )
    assert guard_observed_off_latency_causality(VERDICT, rows) == (VERDICT, False)


def test_missing_subscribed_sensor_evidence_does_not_upgrade_cause():
    assert guard_observed_off_latency_causality(
        VERDICT, evidence(sensor_listeners=False)
    ) == (VERDICT, False)


def test_mismatched_gaps_cannot_support_consistent_30_second_pattern():
    assert guard_observed_off_latency_causality(
        VERDICT, evidence(gaps=False)
    ) == (VERDICT, False)


def test_no_confident_perf_cause_preserves_model_text():
    text = "The 129,544ms warning is worth checking; no cause verified."
    assert guard_observed_off_latency_causality(text, evidence()) == (text, False)


def test_output_is_generic_with_another_controller_app_id():
    text, changed = guard_observed_off_latency_causality(
        VERDICT, evidence(app="9020")
    )
    assert changed
    assert "App 9020 issued OFF" in text
    assert "App 9020's motionHandler" in text
    assert "App 4019 issued OFF" not in text


def test_final_api_corrects_claim_and_exposes_evidence_validation():
    out = SimpleNamespace(
        message=VERDICT, evidence=evidence(),
        request_class="live-read", route="unified-mcp-agent",
        metrics={"outcome": "unresolved", "counters": {}, "timings_ms": {}},
        investigation_coverage={
            "domain": "causal_provenance",
            "status": "partial-evidence",
            "rootCauseVerified": None,
        },
    )
    response = build_agent_response(
        out, model="gemma4:31b", elapsed_ms=49126, version="0.18.119",
    )
    assert response["evidence_validation"]["unsupported_performance_cause_corrected"]
    assert response["outcome_presentation"]["value"] == "unresolved"
    assert "30.058s later" in response["message"]
    assert "30.269s later" in response["message"]
    assert "129,544ms" in response["message"]
    assert response["evidence"] == out.evidence
