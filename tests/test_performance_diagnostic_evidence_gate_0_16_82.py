from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_diagnostic_evidence_gate import (  # noqa: E402
    classify_adaptive_diagnostics,
    guard_performance_diagnostic_hypotheses,
    render_diagnostic_evidence_gate,
)
from synthesis_validator import validate_synthesis  # noqa: E402


def _adaptive_evidence() -> list[dict]:
    return [
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
                            "medianIntervalSeconds": 129.283,
                            "minIntervalSeconds": 0.018,
                            "maxIntervalSeconds": 258.547,
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
                "logCount": 37,
                "logs": [
                    {
                        "date": f"2026-10-01 12:{minute:02d}:58.300",
                        "level": "INFO",
                        "message": "app|4129|SenseCap D1 Settings|SenseCap D1 accepted config push at http://192.168.1.143:8080/d1/config: HTTP 200",
                    }
                    for minute in (0, 10, 15, 20, 30, 40, 45, 50, 55, 59)
                ],
            },
        },
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "hostDerivedTiming": {
                    "sameSecondClusters": [
                        {
                            "second": "2026-10-01 13:06:02",
                            "rowCount": 16,
                            "distinctSourceCount": 9,
                            "spanMs": 640,
                            "sources": ["Octopus Live Meter Energy", "Octopus Live Meter Power"],
                        }
                    ]
                }
            },
        },
    ]


def test_classifies_sparse_nest_and_repeated_sensecap_without_inventing_mechanism() -> None:
    targets = classify_adaptive_diagnostics(_adaptive_evidence())
    assert len(targets) == 2
    nest, sensecap = targets
    assert nest["scopeId"] == "7934"
    assert nest["classification"] == "sparse_or_neutral"
    assert nest["logCount"] == 3
    assert nest["hasRegularCadence"] is False
    assert sensecap["scopeId"] == "4129"
    assert sensecap["classification"] == "repeated_activity"
    assert sensecap["logCount"] == 37
    assert "accepted config push" in sensecap["activityLabel"].casefold()
    assert sensecap["hasRegularCadence"] is False


def test_gate_contract_makes_unresolved_a_valid_diagnostic_result() -> None:
    contract = render_diagnostic_evidence_gate(_adaptive_evidence())
    assert "Unresolved' is a valid diagnostic result" in contract
    assert "sparse_or_neutral" in contract
    assert "do not infer polling" in contract.casefold()
    assert "repeated_activity" in contract
    assert "do not invent 'every X' timing" in contract


LIVE_01681_MESSAGE = """### Hubitat Performance Analysis

**Device Performance**
*   **Highest Resource Usage:** The **Google Nest Hub** has the highest measured `pctTotal` (3.838%) and `pctBusy` (39.3%) among devices.
*   **Execution Latency:** The **LG webOS TV** shows a high average execution time of 3050.63ms, despite a lower `pctTotal` (1.017%).

**App Performance**
*   **Highest Resource Usage:** **SenseCap D1 Settings** has the highest measured `pctTotal` (0.951%) and `pctBusy` (21.1%) among apps.

### Diagnostic Hypotheses

**1. SenseCap D1 Configuration Frequency**
*   Finding: SenseCap D1 Settings has the highest returned app busy percentage; this ranking is measured, but this turn does not establish an implementation mechanism from it.
*   **Evidence:** Diagnostic logs show "accepted config push" messages occurring consistently every 5 to 10 minutes (e.g., 12:10, 12:15, 12:20, 12:30, 12:40, 12:45, 12:50, 13:00).
*   **Hypothesis:** The high `pctBusy` for this app is consistent with the observed frequency of configuration pushes.
*   **Verification:** Inspect the app settings to determine if this push interval is expected or configurable.

**2. LG webOS TV Latency**
*   **Finding:** The LG webOS TV has an average execution time exceeding 3 seconds.
*   **Hypothesis:** This suggests possible network latency or slow response times from the TV's API.
Inspect the cited integration implementation/configuration first.

**3. Google Nest Hub Activity**
*   **Finding:** The Google Nest Hub has the highest `pctBusy` (39.3%) of all devices.
*   **Hypothesis:** This suggests frequent polling or state updates, though the provided diagnostic logs only show occasional volume changes.
Inspect the cited integration/device configuration first.

### Recommended Next Steps
1. Inspect the cited integration/device configuration first.
2. **Connectivity Audit:** Investigate the **LG webOS TV** to determine why average execution times are ~3 seconds.
3. Inspect the cited integration/device configuration first.
4. **Cluster Analysis:** Determine if the simultaneous reporting of **Octopus Live Meter** devices is expected behavior for the integration.
"""


def test_full_01681_live_shape_becomes_evidence_gated_not_plausibility_gated() -> None:
    corrected, changed = guard_performance_diagnostic_hypotheses(
        LIVE_01681_MESSAGE,
        _adaptive_evidence(),
    )
    assert changed is True

    # The measured facts survive.
    for measured in ("3.838%", "39.3%", "3050.63ms", "0.951%", "21.1%"):
        assert measured in corrected

    # Neutral labels replace unsupported resource/severity language.
    assert "Highest Resource Usage" not in corrected
    assert "Highest returned performance percentages" in corrected
    assert "high average execution time" not in corrected

    # SenseCap keeps useful repeated-activity evidence, but raw timestamps cannot
    # become a model-authored cadence or a causal explanation of busy percentage.
    assert "consistently every 5 to 10 minutes" not in corrected
    assert "37 log rows" in corrected
    assert "No host-derived regular cadence was established" in corrected
    assert "do not establish that this activity caused" in corrected

    # LG was not adaptively read at all, so its mechanism must remain unresolved.
    assert "possible network latency" not in corrected
    assert "No target-scoped diagnostic evidence was read for this outlier" in corrected

    # Nest was read but yielded only sparse neutral volume observations.
    assert "frequent polling or state updates" not in corrected
    assert "returned 3 non-diagnostic log observation(s)" in corrected
    assert "mechanism remains unresolved" in corrected

    # Same-second evidence must not be promoted into literal simultaneity.
    assert "simultaneous reporting" not in corrected
    assert "same-second clustered reporting" in corrected


def test_validator_reports_structural_diagnostic_gate_as_evidence_first_repair() -> None:
    corrected, issues = validate_synthesis(LIVE_01681_MESSAGE, _adaptive_evidence())
    assert "performance_evidence_first" in issues
    assert "possible network latency" not in corrected
    assert "frequent polling or state updates" not in corrected


def test_failure_signal_allows_calibrated_hypothesis_but_not_stronger_proof() -> None:
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {"tool": "hub_get_logs", "args": {"appId": "4129", "since": "6h", "limit": 120}},
            "details": {
                "logCount": 4,
                "logs": [
                    {
                        "date": "2026-10-01 10:00:00.000",
                        "level": "WARN",
                        "message": "app|4129|SenseCap D1 Settings|HTTP 408 timeout while pushing config",
                    },
                    {
                        "date": "2026-10-01 10:05:00.000",
                        "level": "ERROR",
                        "message": "app|4129|SenseCap D1 Settings|No route to host",
                    },
                ],
            },
        }
    ]
    targets = classify_adaptive_diagnostics(evidence)
    assert targets[0]["classification"] == "diagnostic_signal"
    contract = render_diagnostic_evidence_gate(evidence)
    assert "HTTP 408" in contract
    assert "no route to host" in contract
    assert "calibrated hypothesis" in contract
    assert "worker-thread blocking" in contract
