"""End-to-end tests for causal-source calibration and compact UI Markdown.

Regression supplied by a real deep-reasoning answer for a single light event:
the model knew the direct app command but still ruled out upstream manual and
other app causes in bullets and a certainty table; it also mislabeled a
device-event row as native hub logs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from causal_attribution_guard import (  # noqa: E402
    guard_unproven_upstream_manual_exclusion,
    guard_causal_sensor_source_attribution,
)
from synthesis_validator import validate_synthesis  # noqa: E402
from webui import render_page  # noqa: E402

QUESTION = (
    "Investigate thoroughly why Example Light turned on at 07:53:36 on "
    "12 October. Check the controlling app and sensors. Read-only."
)


def _receipts(*, native_sensor_log: bool = False) -> list[dict]:
    return [
        {
            "tool": "homebrain_device_history", "success": True,
            "details": {
                "label": "Example Light",
                "attribute": "switch",
                "temporalAnalysis": {
                    "intervalCount": 1,
                    "observedIntervals": [{
                        "start": "2026-10-12T07:53:36.721+0100",
                        "end": "2026-10-12T08:10:58.185+0100",
                        "durationSeconds": 1041,
                    }],
                },
                "commandEvents": [{
                    "name": "command-setLevel",
                    "date": "2026-10-12T07:53:36.621+0100",
                    "description": "Command called: setLevel(50)",
                    "producedBy": {
                        "label": "Example Controller", "id": "1234", "type": "app"
                    },
                }],
            },
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True,
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"appId": "1234", "since": "2026-10-12T06:53:30Z"},
            },
            "details": {"logCount": 0, "logs": []},
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True,
            "arguments": {"tool": "hub_get_logs", "args": {"limit": 100}},
            "details": {
                "logCount": 1,
                "logs": [{
                    "date": "2026-10-12 07:53:36.542",
                    "message": (
                        "dev|7895|Example Occupancy|Example Occupancy motion is active"
                        if native_sensor_log else
                        "dev|7896|Example Lux|Example Lux illuminance is 37 lx"
                    ),
                }],
            },
        },
        {
            "tool": "homebrain_causal_trigger_correlation",
            "success": True,
            "arguments": {"appId": "1234", "deviceId": "7895", "attribute": "motion"},
            "details": {
                "label": "Example Occupancy",
                "attribute": "motion",
                "configured": True,
                "sensorEvent": "2026-10-12T07:53:36.542+0100",
                "stateBoundary": "2026-10-12T07:53:36.721+0100",
            },
        },
        {
            "tool": "homebrain_location_events",
            "success": True,
            "evidence_kind": "authoritative_location_event_history",
            "details": {"observedEvents": [{
                "name": "mode", "value": "Morning",
                "date": "2026-10-12T07:15:01+0100"
            }]},
        },
    ]


LIVE_DRAFT = (
    "### Investigation Result\n"
    "**The Producer:** The direct source is App 1234, ruling out "
    "manual physical interaction.\n"
    "#### 3. Evaluation of Alternative Causes\n"
    "*   **Manual Control:** **Ruled Out.** The producer is App 1234.\n"
    "*   **Mode Change:** **Ruled Out.** The mode changed earlier.\n"
    "*   **Other Automations:** **Ruled Out.** App 1234 sent the command.\n"
    "**The Trigger:** Hub logs show Example Occupancy motion is active at 07:53:36.\n"
    "| Element | Status | Evidence |\n"
    "| :--- | :--- | :--- |\n"
    "| **Controlling App** | **Confirmed** | Direct producer = App 1234. |\n"
    "| **Manual/Mode Cause** | **Ruled Out** | App 1234 and mode history. |\n"
)


def test_direct_app_does_not_exclude_manual_mode_or_other_upstream_causes():
    fixed, changed = guard_unproven_upstream_manual_exclusion(
        LIVE_DRAFT, _receipts()
    )
    assert changed
    assert "ruling out manual physical interaction" not in fixed
    assert "**Manual Control:** **Ruled Out**" not in fixed
    assert "**Mode Change:** **Ruled Out**" not in fixed
    assert "**Other Automations:** **Ruled Out**" not in fixed
    assert "| **Manual/Mode Cause** | **Not established** |" in fixed
    assert "upstream manual" in fixed
    assert "upstream automation" in fixed
    assert "Controlling App** | **Confirmed**" in fixed


def test_source_correction_requires_actual_native_sensor_log_row():
    draft = "**The Trigger:** Hub logs show Example Occupancy motion is active."
    fixed, changed = guard_causal_sensor_source_attribution(
        draft, _receipts(native_sensor_log=False)
    )
    assert changed
    assert "Recorded sensor event history shows" in fixed
    assert "Hub logs show" not in fixed
    supported, changed = guard_causal_sensor_source_attribution(
        draft, _receipts(native_sensor_log=True)
    )
    assert supported == draft
    assert not changed


def test_validation_of_user_draft_preserves_confirmed_producer_without_false_certainty():
    fixed, issues = validate_synthesis(
        LIVE_DRAFT, _receipts(), original_user=QUESTION, causal=True
    )
    assert "upstream_manual_exclusion" in issues
    assert "causal_source_attribution" in issues
    assert "App 1234" in fixed
    assert "| **Manual/Mode Cause** | **Not established** |" in fixed
    assert "Hub logs show Example Occupancy" not in fixed


def test_post_synthesis_serializer_keeps_the_same_causal_claims_grounded():
    outcome = SimpleNamespace(
        message=LIVE_DRAFT,
        evidence=_receipts(),
        metrics={"outcome": "success", "counters": {"model_rounds": 3}},
        route="unified-mcp-agent",
        request_class="live-read",
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=26000, version="0.17.9"
    )
    assert "**Manual Control:** **Ruled Out**" not in response["message"]
    assert "| **Manual/Mode Cause** | **Not established** |" in response["message"]
    assert "Hub logs show Example Occupancy" not in response["message"]
    assert "App 1234" in response["message"]


def test_ordinary_non_app_history_not_rewritten_as_app_source():
    only_sensor_history = [{
        "tool": "homebrain_device_history", "success": True,
        "details": {"label": "Other Device", "temporalAnalysis": {
            "intervalCount": 1,
            "observedIntervals": [{"start": "2026-10-12T07:00:00+0100"}],
        }},
    }]
    message = "* **Other Automations:** Ruled Out from verified system audit."
    fixed, changed = guard_unproven_upstream_manual_exclusion(
        message, only_sensor_history
    )
    assert not changed
    assert fixed == message


def test_webui_renders_deep_headings_and_math_arrows_as_readable_text():
    page = render_page("HomeBrain", "0.17.9")
    assert "function normalizeAnswerMarkup(value)" in page
    assert "normalizeAnswerMarkup(value).split" in page
    assert "normalizeAnswerMarkup(value).replace" in page
    assert "const heading=line.match(/^#{1,6}" in page
    assert "replace(/\\$\\s*\\\\rightarrow\\s*\\$/g,'→')" in page
    assert "replace(/\\$\\s*\\\\leftarrow\\s*\\$/g,'←')" in page
