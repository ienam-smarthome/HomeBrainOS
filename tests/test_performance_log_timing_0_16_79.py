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


def _live_logs() -> list[dict]:
    logs = [
        _row(
            f"2026-09-30 08:48:{second:02d}.945",
            "dev|5383|Halo3000x socket power|Halo3000x socket power ActivePower is 6.9 W",
        )
        for second in (1, 11, 21, 31, 41)
    ]
    logs += [
        _row(
            stamp,
            "dev|5383|Halo3000x socket power|Halo3000x socket power CumulativeEnergyImported is 43.215 kWh",
        )
        for stamp in (
            "2026-09-30 08:46:26.778",
            "2026-09-30 08:47:26.778",
            "2026-09-30 08:48:26.798",
        )
    ]
    logs += [
        _row("2026-09-30 08:47:03.303", "dev|7440|Octopus Meter Cost Month|Octopus Live Meter Display Cost Month is online"),
        _row("2026-09-30 08:47:03.312", "dev|7432|Octopus Meter Energy Summary|Octopus Live Meter Display Summary value is T: 4.73 kWh"),
        _row("2026-09-30 08:47:03.329", "dev|7444|Octopus Meter Energy Month|Octopus Live Meter Display Month is online"),
        _row("2026-09-30 08:47:03.343", "dev|7438|Octopus Live Meter Cost Month|Octopus Live Meter Cost Month is online"),
    ]
    return logs


def test_host_derives_cadence_and_same_second_cluster_from_full_log_set() -> None:
    details = compact_log_evidence({"logs": _live_logs(), "count": len(_live_logs())})
    timing = details["hostDerivedTiming"]

    cadence = {
        (row["sourceRef"], row["signal"]): row
        for row in timing["cadence"]
    }
    active = cadence[("dev|5383", "ActivePower")]
    energy = cadence[("dev|5383", "CumulativeEnergyImported")]

    assert active["observationCount"] == 5
    assert active["approxCadenceSeconds"] == 10
    assert active["regularCadence"] is True
    assert energy["observationCount"] == 3
    assert energy["approxCadenceSeconds"] == 60
    assert energy["regularCadence"] is True

    cluster = next(
        row for row in timing["sameSecondClusters"]
        if row["second"] == "2026-09-30 08:47:03"
    )
    assert cluster["distinctSourceCount"] == 4
    assert cluster["rowCount"] == 4
    assert cluster["spanMs"] == 40


def test_guard_corrects_wrong_model_cadence_and_simultaneous_wording() -> None:
    details = compact_log_evidence({"logs": _live_logs(), "count": len(_live_logs())})
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "details": details,
        }
    ]
    message = (
        "* **Device 5383 (Halo3000x socket power):** `CumulativeEnergyImported` updates were observed approximately every 30 seconds.\n"
        "* **Octopus Live Meter Devices:** Multiple devices reported status and value updates simultaneously at 08:47:03."
    )

    corrected, changed = guard_performance_log_observations(message, evidence)

    assert changed is True
    assert "approximately every 60 seconds" in corrected
    assert "every 30 seconds" not in corrected
    assert "within the same reported second at 08:47:03" in corrected
    assert "simultaneously" not in corrected


def test_two_points_are_reported_as_a_gap_not_invented_cadence() -> None:
    logs = [
        _row("2026-09-30 08:47:26.778", "dev|5383|Halo3000x socket power|Halo3000x socket power CumulativeEnergyImported is 43.215 kWh"),
        _row("2026-09-30 08:48:26.798", "dev|5383|Halo3000x socket power|Halo3000x socket power CumulativeEnergyImported is 43.215 kWh"),
    ]
    details = compact_log_evidence({"logs": logs, "count": 2})
    fact = details["hostDerivedTiming"]["cadence"][0]

    assert "approxCadenceSeconds" not in fact
    assert fact["observedGapSeconds"] == 60.02
