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


def _evidence() -> list[dict]:
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
                            "observationCount": 15,
                            "timingKind": "irregular_intervals",
                            "intervalCount": 14,
                            "medianIntervalSeconds": 10.001,
                            "minIntervalSeconds": 9.93,
                            "maxIntervalSeconds": 20.013,
                            "regularCadence": False,
                        },
                        {
                            "source": "Halo3000x socket power",
                            "sourceRef": "dev|5383",
                            "signal": "CumulativeEnergyImported",
                            "observationCount": 3,
                            "timingKind": "regular_cadence",
                            "intervalCount": 2,
                            "medianIntervalSeconds": 60.002,
                            "minIntervalSeconds": 60.001,
                            "maxIntervalSeconds": 60.004,
                            "regularCadence": True,
                            "approxCadenceSeconds": 60,
                        },
                    ],
                    "sameSecondClusters": [
                        {
                            "second": "2026-10-01 15:47:02",
                            "rowCount": 20,
                            "distinctSourceCount": 11,
                            "spanMs": 120,
                            "sources": ["Octopus Live Meter Energy", "Octopus Live Meter Power"],
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
                        "date": f"2026-10-01 15:00:{second:02d}.000",
                        "level": "INFO",
                        "message": f"dev|7934|Google Nest Hub  - [Google Nest Hub]|Google Nest Hub  - [Google Nest Hub] volume is {value}",
                    }
                    for second, value in ((47, 8), (48, 13), (49, 8), (50, 13), (51, 18), (52, 13))
                ] + [
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
                "logCount": 31,
                "logs": [
                    {
                        "date": "2026-10-01 15:45:47.667",
                        "level": "WARN",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 live push failed (HTTP 408). Live updates are suspended; will retry automatically with backoff.",
                    },
                    {
                        "date": "2026-10-01 15:45:11.184",
                        "level": "WARN",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 config push failed (Connect to 192.168.1.143:80 failed: connect timed out). Config pushes paused for 5 minutes; live updates are NOT suspended.",
                    },
                ] + [
                    {
                        "date": f"2026-10-01 15:{minute:02d}:58.300",
                        "level": "INFO",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 accepted config push at http://192.168.1.143:8080/d1/config: HTTP 200",
                    }
                    for minute in (40, 30, 20, 15, 10, 0)
                ],
            },
        },
    ]


LIVE_01684_MESSAGE = """### Hubitat Performance Analysis

**Observations and Diagnostics**

**1. Google Nest Hub (Device 7934)**
*   **Confirmed Finding:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
*   **Diagnostic Evidence:** Scoped logs show six volume updates occurring between 15:00:47 and 15:00:51.
*   **Hypothesis:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
*   **Verification:** Inspect the source of these volume changes to determine if they are expected or caused by a loop/external integration.

**2. SenseCap D1 Settings (App 4129)**
*   **Confirmed Finding:** Intermittent network communication failures.
*   **Diagnostic Evidence:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
*   **Hypothesis:** Network instability or device unavailability is causing timeouts and subsequent retries, which may contribute to the app's `pctBusy` (20.1%).
*   **Verification:** Collect target-scoped diagnostic evidence for this outlier before choosing a mechanism-specific network, driver, polling, retry, timeout, or API investigation.

**3. General Log Observations**
*   **Cadence:** Halo3000x socket power CumulativeEnergyImported — Irregular observed intervals; median 10.001 seconds; observed range 9.93–20.013 seconds. No regular cadence was established.
*   **Clustering:** A cluster of 20 log rows from 11 distinct sources occurred within a 120ms span at 15:47:02.
"""


def test_semantic_child_roles_preserve_scoped_targets() -> None:
    corrected, changed = guard_format_independent_performance_diagnostics(LIVE_01684_MESSAGE, _evidence())
    assert changed is True

    # Nest was scoped: never claim otherwise. Its repeated volume activity remains
    # evidence-bounded rather than becoming a mechanism.
    assert "No target-scoped diagnostic evidence was read" not in corrected
    assert "9 log rows in 6h" in corrected
    assert "repeated `volume is value` activity" in corrected

    # SenseCap was scoped and contains explicit failure signals.
    assert "31 log rows in 6h" in corrected
    assert "HTTP 408" in corrected
    assert "timeout" in corrected.casefold()
    assert "support a calibrated failure/connectivity hypothesis" in corrected
    assert "contribution" in corrected
    assert "Collect target-scoped diagnostic evidence for this outlier" not in corrected
    assert "Use the existing scoped failure evidence" in corrected


def test_timing_source_and_numbers_are_rendered_from_same_host_fact() -> None:
    corrected, _ = guard_format_independent_performance_diagnostics(LIVE_01684_MESSAGE, _evidence())
    cadence_line = next(line for line in corrected.splitlines() if "**Cadence:**" in line)
    assert "CumulativeEnergyImported" in cadence_line
    assert "Regular cadence" in cadence_line
    assert "median interval 60.002 seconds" in cadence_line
    assert "approximately every 60 seconds" in cadence_line
    assert "60.001–60.004 seconds" in cadence_line
    assert "10.001" not in cadence_line
    assert "9.93" not in cadence_line


def test_label_variants_are_roles_not_new_subjects() -> None:
    message = """**Observations and Diagnostics**

**1. Google Nest Hub (Device 7934)**
* **Confirmed Finding:** No target-scoped diagnostic evidence was read for this outlier in this turn.
* **Diagnostic Evidence:** No target-scoped diagnostic evidence was read for this outlier in this turn.
* **Observed Evidence:** No target-scoped diagnostic evidence was read for this outlier in this turn.
* **Diagnostic Hypothesis:** Frequent polling is causing the high busy percentage.
"""
    corrected, _ = guard_format_independent_performance_diagnostics(message, _evidence())
    assert "No target-scoped diagnostic evidence was read" not in corrected
    assert "frequent polling" not in corrected.casefold()
    assert "9 log rows in 6h" in corrected


def test_validator_uses_single_consolidated_diagnostic_guard() -> None:
    corrected, issues = validate_synthesis(LIVE_01684_MESSAGE, _evidence())
    assert "performance_evidence_first" in issues
    assert "No target-scoped diagnostic evidence was read" not in corrected
    assert "median interval 60.002 seconds" in corrected
    assert "HTTP 408" in corrected
