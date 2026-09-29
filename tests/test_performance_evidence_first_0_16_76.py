from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_evidence_first import (  # noqa: E402
    build_performance_synthesis_contract,
    guard_evidence_first_performance,
)


LIVE_01675 = '''### Performance Analysis

**System Health & Metrics**
*   **Memory & Temperature:** The hub has 916,404 KB of free memory and an internal temperature of 46.9°C.
*   **Database:** The database size is 188 MB.
*   **Alerts:** There are no active health alerts.

**Execution Statistics**
*   **Devices:** Out of 383 devices, the **Google Nest Hub** is the primary consumer of execution time, accounting for 31.5% of the total (`pctTotal`), with an average execution time of 1,564.44ms across 13,352 calls.
*   **Apps:** Out of 200 apps, the **MCP Rule Server** has the highest execution impact at 2.04% of the total, with an average execution time of 702.76ms.
*   **State Size:** The **OpenWeatherMap Multi-API** device is flagged with a large state size (80,334).

**Job Scheduling & Log Observations**
*   **Job Clustering:** There is a high concentration of scheduled jobs firing at the same timestamp (e.g., 16:52:00 BST).
*   **Telemetry Frequency:** Logs show high-frequency updates from power monitoring devices.

### Recommended Improvements

1. **Integration Inspection (Google Nest Hub):** Investigate the driver or integration for the Google Nest Hub to determine why average execution times are high (~1.56s) and if the call volume (13,352) can be reduced.
2. **State Management (OpenWeatherMap):** Inspect the cited app implementation/configuration first.
'''


def test_01676_live_01675_qualitative_ranking_language_is_neutralized() -> None:
    corrected, changed = guard_evidence_first_performance(LIVE_01675)
    assert changed is True
    assert "primary consumer of execution time" not in corrected
    assert "highest execution impact" not in corrected
    assert "flagged with a large state size" not in corrected
    assert "high concentration of scheduled jobs" not in corrected
    assert "high-frequency updates" not in corrected
    assert "can be reduced" not in corrected

    assert "device with the highest returned pctTotal" in corrected
    assert "highest returned app pctTotal" in corrected
    assert "has a measured state size" in corrected
    assert "many scheduled jobs sharing timestamps" in corrected
    assert "repeated updates" in corrected
    assert "whether the observed call volume is expected or configurable" in corrected

    for measured in (
        "916,404 KB",
        "46.9°C",
        "188 MB",
        "31.5%",
        "1,564.44ms",
        "13,352 calls",
        "2.04%",
        "702.76ms",
        "80,334",
    ):
        assert measured in corrected


def test_01676_contract_prefers_canonical_units_and_literal_rankings() -> None:
    contract = build_performance_synthesis_contract([])
    assert "freeMemoryMB" in contract
    assert "report the canonical field" in contract
    assert "highest returned pctTotal/busy value" in contract
    assert "A numeric stateSize is not 'large'" in contract
    assert "Report shared timestamps directly" in contract
    assert "Report observed cadence numerically" in contract
    assert "whether it is expected/configurable" in contract
