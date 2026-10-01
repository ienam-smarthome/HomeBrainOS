from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_diagnostic_format_guard import (  # noqa: E402
    guard_format_independent_performance_diagnostics,
)
from synthesis_validator import validate_synthesis  # noqa: E402


def _live_01683_evidence() -> list[dict]:
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "logCount": 100,
                "logs": [],
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Halo3000x socket power",
                            "sourceRef": "dev|5383",
                            "signal": "ActivePower",
                            "observationCount": 10,
                            "timingKind": "regular_cadence",
                            "intervalCount": 9,
                            "medianIntervalSeconds": 10,
                            "minIntervalSeconds": 9.949,
                            "maxIntervalSeconds": 10.101,
                            "regularCadence": True,
                            "approxCadenceSeconds": 10,
                        }
                    ],
                    "sameSecondClusters": [
                        {
                            "second": "2026-10-01 15:25:02",
                            "rowCount": 25,
                            "distinctSourceCount": 14,
                            "spanMs": 509,
                            "sources": ["Octopus Live Meter Energy", "Octopus Meter Current Power"],
                        }
                    ],
                },
            },
        },
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {"tool": "hub_get_logs", "args": {"deviceId": "7934", "since": "6h", "limit": 120}},
            "details": {
                "logCount": 9,
                "logs": [
                    {
                        "date": "2026-10-01 15:00:51.309",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 13",
                    },
                    {
                        "date": "2026-10-01 15:00:50.913",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 18",
                    },
                    {
                        "date": "2026-10-01 15:00:50.082",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 13",
                    },
                    {
                        "date": "2026-10-01 15:00:49.405",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 8",
                    },
                    {
                        "date": "2026-10-01 15:00:48.774",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 13",
                    },
                    {
                        "date": "2026-10-01 15:00:47.695",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 8",
                    },
                    {
                        "date": "2026-10-01 12:59:19.819",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 13",
                    },
                    {
                        "date": "2026-10-01 12:55:01.272",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 50",
                    },
                    {
                        "date": "2026-10-01 12:55:01.254",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is 50",
                    },
                ],
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Google Nest Hub  - [Google Nest Hub]",
                            "sourceRef": "dev|7934",
                            "signal": "volume",
                            "observationCount": 9,
                            "timingKind": "irregular_intervals",
                            "intervalCount": 8,
                            "medianIntervalSeconds": 0.754,
                            "minIntervalSeconds": 0.018,
                            "maxIntervalSeconds": 7287.876,
                            "regularCadence": False,
                        }
                    ]
                },
            },
        },
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {"tool": "hub_get_logs", "args": {"appId": "4129", "since": "6h", "limit": 120}},
            "details": {
                "logCount": 26,
                "logs": [
                    {
                        "date": f"2026-10-01 {hour:02d}:{minute:02d}:{second:02d}.300",
                        "level": "INFO",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 accepted config push at http://192.168.1.143:8080/d1/config: HTTP 200",
                    }
                    for hour, minute, second in (
                        (15, 20, 58), (15, 15, 1), (15, 10, 58), (15, 0, 58), (15, 0, 1),
                        (14, 50, 58), (14, 45, 1), (14, 40, 58), (14, 30, 58), (14, 30, 1),
                        (14, 20, 58), (14, 15, 1), (14, 10, 58), (14, 0, 58), (14, 0, 1),
                        (13, 50, 58), (13, 45, 1), (13, 40, 58), (13, 30, 58), (13, 30, 1),
                    )
                ],
            },
        },
    ]


LIVE_01683_MESSAGE = """### Hubitat Performance Analysis

**System Metrics**
*   **Free Memory:** 898.4 MB
*   **Internal Temperature:** 44.1°C
*   **Database Size:** 214 MB

**Log Observations**
*   **Cadence:** Regular cadence; median interval 10 seconds; approximately every 10 seconds; observed range 9.949–10.101 seconds.
*   **Event Clusters:** At 15:25:02, 25 log rows were recorded from 14 distinct sources within a 509ms span.

---

### Diagnostic Hypotheses & Recommendations

**1. Google Nest Hub Resource Usage**
*   **Finding:** Highest device `pctBusy` (36.7%).
*   **Evidence:** Diagnostic logs show multiple volume updates occurring within seconds (e.g., six updates between 15:00:47 and 15:00:51).
*   **Diagnostic interpretation:** The scoped logs show repeated `volume is value` activity, but they do not establish that this activity caused the measured performance statistics or reveal the implementation mechanism.
Inspect the cited integration/device configuration first.

**2. SenseCap D1 Settings Resource Usage**
*   **Finding:** Highest app `pctBusy` (20.1%).
*   **Evidence:** Diagnostic logs show HTTP config pushes to `192.168.1.143` occurring every 5 to 10 minutes.
*   **Diagnostic interpretation:** The scoped logs show repeated `SenseCap D1 accepted config push at endpoint HTTP value` activity, but they do not establish that this activity caused the measured performance statistics or reveal the implementation mechanism.
*   **Verification:** Review the app configuration to determine if this push interval is expected or if it can be adjusted.

**3. LG webOS TV Execution Time**
*   **Finding:** High `averageMs` (3051.17 ms).
*   **Conclusion:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
*   **Verification:** Inspect network connectivity and API response logs for the LG webOS TV.
"""


def test_numbered_entity_subheadings_preserve_section_modes_and_child_target_context() -> None:
    corrected, changed = guard_format_independent_performance_diagnostics(
        LIVE_01683_MESSAGE,
        _live_01683_evidence(),
    )
    assert changed is True

    # Source attribution is explicit for the only host-established regular cadence.
    assert "Halo3000x socket power ActivePower" in corrected
    assert "approximately every 10 seconds" in corrected

    # SenseCap child Evidence inherits the SenseCap target and cannot invent cadence.
    assert "occurring every 5 to 10 minutes" not in corrected
    assert "26 log rows in 6h" in corrected
    assert "No host-derived regular cadence was established" in corrected
    assert "do not establish that this activity caused" in corrected

    # LG is an unscoped entity subheading inside the same combined diagnostic/
    # recommendations section, so its Verification child cannot prescribe a
    # network/API-specific investigation.
    assert "Inspect network connectivity and API response logs" not in corrected
    assert "Collect target-scoped diagnostic evidence" in corrected
    assert "mechanism remains unresolved" in corrected

    # Existing good Nest interpretation is retained rather than borrowing SenseCap.
    assert "Google Nest Hub Resource Usage" in corrected
    assert "repeated `volume is value` activity" in corrected


def test_validator_applies_context_inheritance_to_01683_live_shape() -> None:
    corrected, issues = validate_synthesis(LIVE_01683_MESSAGE, _live_01683_evidence())
    assert "performance_evidence_first" in issues
    assert "occurring every 5 to 10 minutes" not in corrected
    assert "Inspect network connectivity and API response logs" not in corrected
    assert "Halo3000x socket power ActivePower" in corrected


def test_child_field_without_new_entity_keeps_current_scoped_target() -> None:
    message = """### Diagnostic Hypotheses & Recommendations

**2. SenseCap D1 Settings Resource Usage**
*   **Finding:** Highest app pctBusy.
*   **Evidence:** HTTP pushes occurring every 5 to 10 minutes.
*   **Verification:** Review whether the push interval is expected.
"""
    corrected, _ = guard_format_independent_performance_diagnostics(message, _live_01683_evidence())
    assert "every 5 to 10 minutes" not in corrected
    assert "26 log rows in 6h" in corrected


def test_numbered_unscoped_entity_clears_previous_scoped_target_without_leaving_section() -> None:
    message = """### Diagnostic Hypotheses & Recommendations

**2. SenseCap D1 Settings Resource Usage**
*   **Evidence:** Repeated config push activity.

**3. LG webOS TV Execution Time**
*   **Conclusion:** The mechanism remains unresolved.
*   **Verification:** Inspect network connectivity and API response logs.
"""
    corrected, _ = guard_format_independent_performance_diagnostics(message, _live_01683_evidence())
    assert "Collect target-scoped diagnostic evidence" in corrected
    assert "SenseCap" in corrected
