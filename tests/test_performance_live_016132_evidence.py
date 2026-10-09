from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_api_finalizer import (
    _repair_unverified_app_cleanup_and_empty_scoped_reads,
)


def _evidence(*, zero_logs: bool = True, with_config: bool = False):
    receipts = [
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_logs",
            "success": True, "arguments": {
                "tool": "hub_get_logs",
                "args": {"deviceId": "7486", "since": "6h", "limit": 120},
            },
            "details": {
                "logCount": 0 if zero_logs else 3,
                "adaptiveTarget": {
                    "kind": "device", "id": "7486", "name": "LG webOS TV",
                },
            },
        },
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_logs",
            "success": True, "arguments": {
                "tool": "hub_get_logs",
                "args": {"appId": "4151", "since": "6h", "limit": 120},
            },
            "details": {"logCount": 8},
        },
    ]
    if with_config:
        receipts.append({
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
            "success": True, "evidence_kind": "configuration_read",
        })
    return receipts


LIVE_016132 = """**Diagnostic Hypotheses:**
1.  **MCP Rule Server Configuration:** The target-scoped diagnostic read returned 8 non-diagnostic log observation(s) and did not establish a mechanism for this measured outlier; the mechanism remains unresolved.
    *   *Verification:* Inspect MCP Rule Server configuration for references to apps 2954 and 2597.
2.  **LG webOS TV Latency:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
    *   No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.
3.  **Event Volume:** The Halo3000x socket is reporting power every 10 seconds.
    *   *Verification:* Confirm if this reporting frequency is required for current automations or if it is a configurable driver setting.

**Recommended Inspection Steps:**
*   **App Cleanup:** Verify if apps 2954 and 2597 were intentionally deleted and remove corresponding references in the MCP Rule Server.
*   **Job Staggering:** Review the cited integration configuration to determine whether the observed same-second cluster is expected.
"""


def test_regress_live_016132_cleanup_and_empty_log_contradictions():
    result, changed = _repair_unverified_app_cleanup_and_empty_scoped_reads(
        LIVE_016132, _evidence()
    )
    assert changed
    assert result.count("Trace which diagnostic request queried deleted apps") == 2
    assert "remove corresponding references" not in result
    assert "Inspect MCP Rule Server configuration for references" not in result
    assert "zero log rows do not prove normal operation" in result.lower()
    assert "returned no rows for 6h" in result
    assert result.count("No target-scoped diagnostic evidence was read") == 0
    assert "Next check: inspect driver configuration" in result
    assert "**Event Volume:** The Halo3000x socket" in result
    assert "**Job Staggering:**" in result


def test_do_not_invent_empty_log_read_when_target_data_unavailable():
    result, changed = _repair_unverified_app_cleanup_and_empty_scoped_reads(
        LIVE_016132, _evidence(zero_logs=False)
    )
    assert changed  # stale-app advice is still unsupported
    assert "No target-scoped diagnostic evidence was read" in result
    assert "returned no rows for 6h" not in result


def test_do_not_rewrite_persisted_reference_question_when_config_was_read():
    text = (
        "* **App Cleanup:** Verify if apps 2954 and 2597 were intentionally "
        "deleted and remove corresponding references in the MCP Rule Server.\n"
    )
    assert _repair_unverified_app_cleanup_and_empty_scoped_reads(
        text, _evidence(with_config=True)
    ) == (text, False)


def test_do_not_rewrite_log_evidence_as_configuration_change():
    text = (
        "**Errors:** Scoped logs of App 4151 show WARN for a slow internal "
        "GET, ERROR for hub_get_app_config failing to find apps 2954/2597 "
        "and invalid filter 'BROKEN'.\n"
    )
    assert _repair_unverified_app_cleanup_and_empty_scoped_reads(
        text, _evidence()
    ) == (text, False)


def test_zero_logs_for_different_device_cannot_falsely_clear_lg():
    evidence = _evidence()
    evidence[0]["details"]["adaptiveTarget"]["name"] = "Hallway TRV"
    result, changed = _repair_unverified_app_cleanup_and_empty_scoped_reads(
        LIVE_016132, evidence
    )
    assert changed
    assert "returned no rows for 6h" not in result
    assert "No target-scoped diagnostic evidence was read" in result
