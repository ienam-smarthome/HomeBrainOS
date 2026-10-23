"""Replays source-scoped targeted-app and reasoning gaps in the 0.18.84 audit."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from health_audit_service import (
    _requested_audit_app_ids, _requested_app_statistics,
)
from audit_ai_advisory_guard import calibrate_audit_ai_advisory
from audit_reasoning_context import build_audit_reasoning_packet


USER_QUESTION = (
    "Perform a comprehensive READ-ONLY audit of my entire Hubitat system "
    "using live evidence and AI reasoning. Pay particular attention to "
    "Life360 (app 4061), Device Status Report (app 3977), "
    "Octopus Energy (app 3933), and any other significant findings."
)


def test_explicit_named_app_ids_are_bounded_in_user_order():
    assert _requested_audit_app_ids(USER_QUESTION) == ("4061", "3977", "3933")
    assert _requested_audit_app_ids(
        "Check app 3977, APP #3933, app 3977 and app 4061"
    ) == ("3977", "3933", "4061")
    assert _requested_audit_app_ids(
        "app 1, app 4061 app 3977 app 3933 app 4151"
    ) == ("4061", "3977", "3933")
    assert _requested_audit_app_ids("all apps and scheduled jobs") == ()


def test_top20_absence_is_unknown_not_an_inferred_no_load():
    stats = {"appStats": [
        {"id": 4129, "pctBusy": 21.1, "pctTotal": 80.558, "averageMs": 1367.46},
        {"id": 3933, "pctBusy": 2.3, "pctTotal": 7, "averageMs": 15},
    ]}
    absent = _requested_app_statistics("4061", stats)
    assert "actual load unknown" in absent
    assert "healthy" not in absent and "zero" not in absent
    present = _requested_app_statistics("3933", stats)
    assert "pctBusy=2.3" in present
    assert "do not establish hub CPU utilisation" in present
    assert "unavailable" in _requested_app_statistics("3977", None)


HOST = """### Prioritised evidence-backed checks
- Confirm: Lighting Automation Heartbeat has old last-activity. An old last-activity timestamp alone cannot prove failover is broken.
### Offline-device evidence (identity-grounded)
- Bedroom 3 Mesh reports offline; verify upstream telemetry.
### Performance leaders (not automatic faults)
Performance data is a top-ranked sample, not an audit of every device or app.
"""
BAD_ADVISORY = """**1. Device Error: Bedroom 3 Mesh (ID 7103) Connectivity Failure**
* **Observed Evidence:** Device is reported as offline via healthStatus.
* **Practical Impact:** The device is currently unavailable for automation triggers or manual control.

**2. Performance Risk: High Resource Consumption**
* **Observed Evidence:** Tasmota Discovery Listener has pctBusy=23.9%.
* **Practical Impact:** These components are utilizing a larger fraction of the hub's available processing cycles compared to other sampled apps/devices.

**3. Health Warning: Stale Lighting Automation Heartbeat**
* **Observed Evidence:** The heartbeat was last seen in August.
* **Practical Impact:** If this heartbeat is intended to monitor system health or trigger failovers, the monitoring mechanism is currently non-functional.
"""


def test_actual_live_overclaims_are_corrected_without_erasing_observations():
    fixed, reasons = calibrate_audit_ai_advisory(BAD_ADVISORY, HOST)
    assert set(reasons) == {
        "offline_manual_control_unverified",
        "offline_root_cause_unverified",
        "heartbeat_cadence_unverified",
        "pctbusy_cpu_share_unverified",
    }
    assert "Connectivity Failure" not in fixed
    assert "unavailable for automation triggers or manual control" not in fixed
    assert "currently non-functional" not in fixed
    assert "larger fraction of the hub's available processing cycles" not in fixed
    assert "reported offline" in fixed
    assert "pctBusy=23.9%" in fixed
    assert "unverified without an expected reporting cadence" in fixed


def test_unchecked_sources_do_not_trigger_source_guard():
    assert calibrate_audit_ai_advisory(BAD_ADVISORY, "") == (BAD_ADVISORY, ())


def test_requested_app_section_is_prioritised_in_model_evidence_packet():
    report = """## Comprehensive Hubitat audit — ATTENTION
### Prioritised evidence-backed checks
- General warning.
### Coverage
- Apps: top-20 only.
### Requested app checks — bounded, source-specific
- App 4061: not present in top-ranked sample; load unknown; scoped ERROR row count unverified.
- App 3977: no source-confirmed rows in capped 6h response.
- App 3933: 1 exact source-ID-matched WARN row.
### Quiet devices
""" + ("- Sensor quiet.\n" * 1000)
    packet = build_audit_reasoning_packet(report)
    assert "### Requested app checks" in packet
    assert "App 4061" in packet and "App 3977" in packet and "App 3933" in packet
    assert len(packet) <= 14000
