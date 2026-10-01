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


def _live_evidence() -> list[dict]:
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "logCount": 100,
                "logs": [
                    {
                        "date": "2026-10-01 14:07:17.297",
                        "level": "INFO",
                        "message": "app|2084|System alert: Hub C8 - Low Memory &lt;200MB|Event: Hub Info (C8 Pro) freeMemory 917.38",
                    }
                ],
                "hostDerivedTiming": {
                    "sameSecondClusters": [
                        {
                            "second": "2026-10-01 14:07:02",
                            "rowCount": 16,
                            "distinctSourceCount": 8,
                            "spanMs": 94,
                            "sources": ["Octopus Live Meter Energy Today", "Octopus Meter Current Power"],
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
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"deviceId": "7934", "since": "6h", "limit": 120},
            },
            "details": {
                "logCount": 3,
                "logs": [
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
                            "timingKind": "irregular_intervals",
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
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"appId": "4129", "since": "6h", "limit": 120},
            },
            "details": {
                "logCount": 47,
                "logs": [
                    {
                        "date": f"2026-10-01 {hour:02d}:{minute:02d}:58.300",
                        "level": "INFO",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 accepted config push at http://192.168.1.143:8080/d1/config: HTTP 200",
                    }
                    for hour, minute in (
                        (14, 0), (14, 0), (13, 50), (13, 45), (13, 40),
                        (13, 30), (13, 30), (13, 20), (13, 15), (13, 10),
                        (13, 0), (13, 0), (12, 50), (12, 45), (12, 40),
                        (12, 30), (12, 30), (12, 20), (12, 15), (12, 10),
                    )
                ],
            },
        },
    ]


LIVE_01682_MESSAGE = """### Hubitat Performance Analysis

**System Metrics**
*   **Free Memory:** 916.76 MB

**Performance Statistics**
*   **Devices:** 383 total.
    *   **Google Nest Hub:** Highest returned `pctTotal` (3.651%) and `pctBusy` (38.2%), with an `averageMs` of 177.45ms.
    *   **LG webOS TV:** `pctTotal` of 1.016% and `pctBusy` of 10.6%, with an `averageMs` of 3050.69ms.
*   **Apps:** 200 total.
    *   **SenseCap D1 Settings:** Highest returned `pctTotal` (0.959%) and `pctBusy` (20.5%), with an `averageMs` of 27.63ms.

**Observations**
*   **SenseCap D1 Settings (App 4129):** Scoped logs show HTTP config pushes to `192.168.1.143:8080/d1/config` occurring approximately every 5 to 10 minutes (e.g., 13:10, 13:15, 13:20, 13:30, 13:40, 13:45, 14:00).
*   **Octopus Live Meter:** Observed 16 log rows generated within a single second (14:07:02).
*   **System Logs:** A log entry from `app|2084` reported "Low Memory <200MB" at 14:07:17, though the accompanying event value was 917.38 MB.

**Diagnostic Hypotheses**
*   **SenseCap D1 Activity:** The `pctBusy` value of 20.5% for app 4129 is consistent with the observed recurring HTTP config pushes.
*   **LG TV Latency:** The `averageMs` of 3050.69ms for the LG webOS TV suggests possible latency in device communication or response times.

**Recommended Inspections**
1.  Inspect the cited integration/device configuration first.
2.  **LG webOS TV:** Inspect the network connectivity and driver settings to investigate the 3-second average execution time.
3.  **Octopus Live Meter:** Inspect the device configuration to determine if the burst of 16 events per second is expected behavior.
4.  **System Alert App (App 2084):** Inspect the logic of the memory alert to determine why it triggered a "Low Memory" message while free memory was above 900 MB.
"""


def test_live_01682_inline_shape_is_evidence_gated_without_numbered_headings() -> None:
    corrected, changed = guard_format_independent_performance_diagnostics(
        LIVE_01682_MESSAGE,
        _live_evidence(),
    )
    assert changed is True

    # Measured values survive.
    for value in ("916.76 MB", "3.651%", "38.2%", "3050.69ms", "20.5%", "27.63ms"):
        assert value in corrected

    # Adaptive cadence is authoritative anywhere in the answer, not only inside a
    # Diagnostic Hypotheses section.
    assert "every 5 to 10 minutes" not in corrected
    assert "47 log rows in 6h" in corrected
    assert "No host-derived regular cadence was established" in corrected

    # Inline bullet hypotheses are classified by entity/evidence, not heading shape.
    assert "consistent with the observed recurring" not in corrected
    assert "do not establish that this activity caused" in corrected
    assert "suggests possible latency" not in corrected
    assert "No target-scoped diagnostic evidence was read for this outlier" in corrected

    # Unsupported mechanism-specific action is replaced with an evidence-gathering step.
    assert "Inspect the network connectivity and driver settings" not in corrected
    assert "Collect target-scoped diagnostic evidence" in corrected

    # One same-second cluster is not a recurring rate or literal simultaneity.
    assert "16 events per second" not in corrected
    assert "16 log rows observed within one reported second" in corrected

    # A threshold-labelled app event is not proof that the threshold fired.
    assert "why it triggered a \"Low Memory\" message" not in corrected
    assert "processing/logging a freeMemory event of 917.38 MB" in corrected
    assert "does not establish that its <200MB condition evaluated true" in corrected


def test_validator_reports_evidence_first_for_live_01682_shape() -> None:
    corrected, issues = validate_synthesis(LIVE_01682_MESSAGE, _live_evidence())
    assert "performance_evidence_first" in issues
    assert "every 5 to 10 minutes" not in corrected
    assert "suggests possible latency" not in corrected
    assert "16 events per second" not in corrected
    assert "why it triggered" not in corrected


def test_regular_cadence_claim_remains_allowed_when_host_establishes_it() -> None:
    evidence = _live_evidence()
    evidence.append(
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {"tool": "hub_get_logs", "args": {"deviceId": "5383", "since": "6h", "limit": 120}},
            "details": {
                "logCount": 12,
                "logs": [
                    {
                        "date": "2026-10-01 14:07:23.374",
                        "level": "INFO",
                        "message": "dev|5383|Halo3000x socket power|Halo3000x socket power ActivePower is 7.3 W",
                    }
                ] * 12,
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Halo3000x socket power",
                            "sourceRef": "dev|5383",
                            "signal": "ActivePower",
                            "timingKind": "regular_cadence",
                            "regularCadence": True,
                            "approxCadenceSeconds": 10,
                        }
                    ]
                },
            },
        }
    )
    message = "* **Halo3000x socket power:** Regular cadence; approximately every 10 seconds."
    corrected, changed = guard_format_independent_performance_diagnostics(message, evidence)
    assert changed is False
    assert corrected == message
