from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_native_logs import (  # noqa: E402
    causal_boundary_log_windows,
    correlate_native_log_boundaries,
    native_log_provenance_sufficient,
    render_native_log_correlation,
)
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def subject_evidence() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": "Dehumidifier 2",
            "attribute": "switch",
            "room": "Dehumidifier",
            "temporalAnalysis": {
                "intervalCount": 1,
                "observedIntervals": [{
                    "start": "2026-09-22T22:07:37.107+0100",
                    "end": "2026-09-22T22:38:13.489+0100",
                    "startNatural": "10:07 pm on Tuesday 22 September 2026",
                    "endNatural": "10:38 pm on Tuesday 22 September 2026",
                    "durationSeconds": 1836,
                    "duration": "31m",
                }],
            },
        },
    }


def log_receipt(rows: list[dict]) -> dict:
    return {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "evidence_kind": "authoritative_native_log_history",
        "details": {
            "logCount": len(rows),
            "logs": rows,
        },
    }


def native_evidence() -> list[dict]:
    return [
        subject_evidence(),
        log_receipt([
            {
                "date": "2026-09-22 22:07:37.195",
                "level": "INFO",
                "message": (
                    "app|3995|01. Humidity Controller|01. Humidity Controller: "
                    "Unit 2 manual: will turn OFF after 90 min"
                ),
            },
            {
                "date": "2026-09-22 22:07:37.159",
                "level": "INFO",
                "message": (
                    "app|3995|01. Humidity Controller|01. Humidity Controller: "
                    "DEV LOCK set [unit2]: manual for 5430s (manual run)"
                ),
            },
            {
                "date": "2026-09-22 22:07:37.002",
                "level": "INFO",
                "message": (
                    "dev|4222|Dehumidifier 2|Dehumidifier 2 turn on command"
                ),
            },
            {
                "date": "2026-09-22 22:07:36.926",
                "level": "INFO",
                "message": (
                    "dev|7129|Ikea Rodret (Livingroom)|Ikea Rodret (Livingroom) "
                    "button 2 (Off) was pushed [physical]"
                ),
            },
        ]),
        log_receipt([
            {
                "date": "2026-09-22 22:38:13.489",
                "level": "INFO",
                "message": (
                    "dev|4222|Dehumidifier 2|Dehumidifier 2 switch is off"
                ),
            },
            {
                "date": "2026-09-22 22:38:13.369",
                "level": "INFO",
                "message": (
                    "dev|4222|Dehumidifier 2|Dehumidifier 2 turn off command"
                ),
            },
            {
                "date": "2026-09-22 22:38:13.248",
                "level": "INFO",
                "message": (
                    "dev|7129|Ikea Rodret (Livingroom)|Ikea Rodret (Livingroom) "
                    "button 2 (Off) was pushed [physical]"
                ),
            },
        ]),
    ]


def test_native_log_windows_cover_start_and_end_with_correct_utc_offset() -> None:
    windows = causal_boundary_log_windows([subject_evidence()])

    assert windows == [
        {
            "timelineId": "T1",
            "boundaryRole": "start",
            "subjectBoundary": "2026-09-22T22:07:37.107000+01:00",
            "since": "2026-09-22T21:07:27.107000Z",
            "until": "2026-09-22T21:07:47.107000Z",
        },
        {
            "timelineId": "T1",
            "boundaryRole": "end",
            "subjectBoundary": "2026-09-22T22:38:13.489000+01:00",
            "since": "2026-09-22T21:38:03.489000Z",
            "until": "2026-09-22T21:38:23.489000Z",
        },
    ]


def test_repeated_physical_button_is_correlated_to_both_subject_commands() -> None:
    rows = correlate_native_log_boundaries(native_evidence())

    assert len(rows) == 2
    by_role = {row["boundaryRole"]: row for row in rows}

    start = by_role["start"]
    assert start["expectedAction"] == "on"
    assert start["command"]["commandToStateMs"] == 105.0
    assert start["controller"]["sourceId"] == "7129"
    assert start["controller"]["sourceLabel"] == "Ikea Rodret (Livingroom)"
    assert start["controller"]["button"] == "2"
    assert start["controller"]["controllerToCommandMs"] == 76.0
    assert start["controller"]["controllerToStateMs"] == 181.0
    assert start["appReactions"][0]["sourceLabel"] == "01. Humidity Controller"
    assert start["appReactions"][0]["afterCommandMs"] == 157.0

    end = by_role["end"]
    assert end["expectedAction"] == "off"
    assert end["command"]["commandToStateMs"] == 120.0
    assert end["controller"]["sourceId"] == "7129"
    assert end["controller"]["button"] == "2"
    assert end["controller"]["controllerToCommandMs"] == 121.0

    assert start["controller"]["fingerprint"] == "7129:2"
    assert end["controller"]["fingerprint"] == "7129:2"
    assert start["repeatedControllerPattern"] is True
    assert end["repeatedControllerPattern"] is True
    assert native_log_provenance_sufficient(rows) is True


def test_rendered_native_log_result_preserves_candidate_not_mapping_proof() -> None:
    rows = correlate_native_log_boundaries(native_evidence())
    rendered = render_native_log_correlation(rows)

    assert rendered is not None
    assert "same physical controller/input" in rendered
    assert "strongest initiating-control candidate" in rendered
    assert "does not independently prove the configured mapping" in rendered
    assert "downstream-app: 01. Humidity Controller" in rendered


def test_single_boundary_button_is_not_enough_for_early_finalization() -> None:
    evidence = native_evidence()[:2]
    rows = correlate_native_log_boundaries(evidence)

    assert len(rows) == 1
    assert rows[0]["boundaryRole"] == "start"
    assert rows[0]["repeatedControllerPattern"] is False
    assert native_log_provenance_sufficient(rows) is False


def test_native_log_metrics_are_supported_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_native_log_reads", 2)
        metrics.increment("causal_native_log_correlations", 2)
        metrics.increment("causal_repeated_controller_pattern")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    rows = present_request_metrics(snapshot)
    assert {"label": "Causal native-log reads", "value": "2"} in rows
    assert {"label": "Causal native-log correlations", "value": "2"} in rows
    assert {"label": "Repeated controller patterns", "value": "1"} in rows


def test_superseded_empty_subject_history_does_not_shadow_scoped_retry() -> None:
    empty_first_pass = {
        "tool": "homebrain_device_history",
        "success": True,
        "arguments": {"name": "dehumidifier 2"},
        "details": {
            "label": "Dehumidifier 2",
            "attribute": "switch",
            "attributeInferred": True,
            "hoursBack": 24,
            "sourceEventCount": 20,
            "temporalAnalysis": {
                "intervalCount": 0,
                "observedIntervals": [],
                "unboundedActiveInterval": False,
                "openActiveInterval": False,
                "openActiveStart": None,
            },
        },
    }
    corrected_retry = subject_evidence()
    corrected_retry["arguments"] = {
        "name": "Dehumidifier 2",
        "attribute": "switch",
        "limit": 50,
        "hours_back": 24,
    }

    windows = causal_boundary_log_windows(
        [empty_first_pass, corrected_retry]
    )

    assert windows == [
        {
            "timelineId": "T1",
            "boundaryRole": "start",
            "subjectBoundary": "2026-09-22T22:07:37.107000+01:00",
            "since": "2026-09-22T21:07:27.107000Z",
            "until": "2026-09-22T21:07:47.107000Z",
        },
        {
            "timelineId": "T1",
            "boundaryRole": "end",
            "subjectBoundary": "2026-09-22T22:38:13.489000+01:00",
            "since": "2026-09-22T21:38:03.489000Z",
            "until": "2026-09-22T21:38:23.489000Z",
        },
    ]


def test_later_controller_history_cannot_replace_anchored_causal_subject() -> None:
    controller_history = {
        "tool": "homebrain_device_history",
        "success": True,
        "arguments": {"name": "Ikea Rodret (Livingroom)", "attribute": "switch"},
        "details": {
            "label": "Ikea Rodret (Livingroom)",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 1,
                "observedIntervals": [{
                    "start": "2026-09-22T22:07:36.900+0100",
                    "end": "2026-09-22T22:07:37.300+0100",
                    "durationSeconds": 0,
                    "duration": "0s",
                }],
            },
        },
    }

    windows = causal_boundary_log_windows(
        [subject_evidence(), controller_history]
    )

    assert len(windows) == 2
    assert windows[0]["subjectBoundary"] == (
        "2026-09-22T22:07:37.107000+01:00"
    )
    assert windows[1]["subjectBoundary"] == (
        "2026-09-22T22:38:13.489000+01:00"
    )
