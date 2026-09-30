from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from log_evidence_compactor import compact_log_evidence  # noqa: E402
from performance_log_observation_guard import (  # noqa: E402
    guard_performance_log_observations,
)


def _row(date: str, message: str) -> dict:
    return {"date": date, "level": "INFO", "message": message}


def test_host_classifies_regular_irregular_and_gap_timing() -> None:
    logs = [
        _row("2026-09-30 16:45:00.000", "dev|1|Regular Sensor|Regular Sensor value is 1"),
        _row("2026-09-30 16:45:10.000", "dev|1|Regular Sensor|Regular Sensor value is 2"),
        _row("2026-09-30 16:45:20.000", "dev|1|Regular Sensor|Regular Sensor value is 3"),
        _row("2026-09-30 16:45:00.000", "dev|2|Irregular Sensor|Irregular Sensor motion is active"),
        _row("2026-09-30 16:45:01.000", "dev|2|Irregular Sensor|Irregular Sensor motion is inactive"),
        _row("2026-09-30 16:45:10.000", "dev|2|Irregular Sensor|Irregular Sensor motion is active"),
        _row("2026-09-30 16:45:00.000", "dev|3|Gap Sensor|Gap Sensor energy is 10 kWh"),
        _row("2026-09-30 16:46:00.020", "dev|3|Gap Sensor|Gap Sensor energy is 11 kWh"),
    ]
    details = compact_log_evidence({"logs": logs, "count": len(logs)})
    facts = {
        (row["sourceRef"], row["signal"]): row
        for row in details["hostDerivedTiming"]["cadence"]
    }

    regular = facts[("dev|1", "value")]
    irregular = facts[("dev|2", "motion")]
    gap = facts[("dev|3", "energy")]

    assert regular["timingKind"] == "regular_cadence"
    assert regular["regularCadence"] is True
    assert regular["approxCadenceSeconds"] == 10

    assert irregular["timingKind"] == "irregular_intervals"
    assert irregular["regularCadence"] is False
    assert "approxCadenceSeconds" not in irregular

    assert gap["timingKind"] == "observed_gap"
    assert gap["observedGapSeconds"] == 60.02
    assert "regularCadence" not in gap


def test_guard_separates_live_regular_irregular_and_gap_wording() -> None:
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "details": {
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Halo3000x socket power",
                            "sourceRef": "dev|5383",
                            "signal": "ActivePower",
                            "timingKind": "regular_cadence",
                            "medianIntervalSeconds": 9.995,
                            "minIntervalSeconds": 8.887,
                            "maxIntervalSeconds": 10.017,
                            "regularCadence": True,
                            "approxCadenceSeconds": 10,
                        },
                        {
                            "source": "Linptech Kitchen sensor",
                            "sourceRef": "dev|7778",
                            "signal": "motion",
                            "timingKind": "irregular_intervals",
                            "medianIntervalSeconds": 2.048,
                            "minIntervalSeconds": 1.01,
                            "maxIntervalSeconds": 9.61,
                            "regularCadence": False,
                        },
                        {
                            "source": "Hallway FP300 lux",
                            "sourceRef": "dev|7753",
                            "signal": "illuminance",
                            "timingKind": "irregular_intervals",
                            "medianIntervalSeconds": 5.736,
                            "minIntervalSeconds": 3.934,
                            "maxIntervalSeconds": 14.676,
                            "regularCadence": False,
                        },
                        {
                            "source": "Energy Sensor",
                            "sourceRef": "dev|9000",
                            "signal": "energy",
                            "timingKind": "observed_gap",
                            "observedGapSeconds": 60.02,
                        },
                    ]
                }
            },
        }
    ]
    message = (
        "*   **Observed Cadence:**\n"
        "    *   `Halo3000x socket power` (ActivePower): Median interval of 9.995 seconds (approximate cadence of 10 seconds).\n"
        "    *   `Linptech Kitchen sensor` (motion): Median interval of 2.048 seconds.\n"
        "    *   `Hallway FP300 lux` (illuminance): Median interval of 5.736 seconds.\n"
        "    *   `Energy Sensor` (energy): Updates were observed approximately every 60 seconds."
    )

    corrected, changed = guard_performance_log_observations(message, evidence)

    assert changed is True
    assert "Observed Timing" in corrected
    assert "Observed Cadence" not in corrected
    assert "Regular cadence" in corrected
    assert "approximately every 10 seconds" in corrected
    assert "Irregular observed intervals; median 2.048 seconds; observed range 1.01–9.61 seconds" in corrected
    assert "Irregular observed intervals; median 5.736 seconds; observed range 3.934–14.676 seconds" in corrected
    assert corrected.count("No regular cadence was established.") == 2
    assert "Single observed gap: 60.02 seconds" in corrected
    assert "This does not establish a recurring cadence." in corrected


def test_legacy_timing_rows_without_timing_kind_still_fail_closed() -> None:
    evidence = [
        {
            "sub_tool": "hub_get_logs",
            "success": True,
            "details": {
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Legacy Sensor",
                            "sourceRef": "dev|42",
                            "signal": "motion",
                            "medianIntervalSeconds": 4.5,
                            "minIntervalSeconds": 1.0,
                            "maxIntervalSeconds": 12.0,
                            "regularCadence": False,
                        }
                    ]
                }
            },
        }
    ]

    corrected, changed = guard_performance_log_observations(
        "* **Legacy Sensor:** motion cadence was about every 4.5 seconds.",
        evidence,
    )

    assert changed is True
    assert "Irregular observed intervals" in corrected
    assert "No regular cadence was established." in corrected
    assert "every 4.5 seconds" not in corrected
