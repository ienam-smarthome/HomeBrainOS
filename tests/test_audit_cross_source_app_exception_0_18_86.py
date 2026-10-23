"""0.18.85 audit replay: app 3977 error surfaced in dev|7182 rows, not appId=3977."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from health_audit_service import _reconcile_requested_app_exception_sources, render_comprehensive_system_audit
from audit_ai_advisory_guard import calibrate_audit_ai_advisory


def _checks():
    return [
        {"id": "4061", "performance": "pctBusy=7.1",
         "log_summary": "2 exact source-ID rows of 2 returned; 0 ERROR; 0 LimitExceededException"},
        {"id": "3977", "performance": "pctBusy=10.6; averageMs=107090.14",
         "log_summary": "0 exact source-ID rows of 0 returned; 0 ERROR; 0 LimitExceededException"},
        {"id": "3933", "performance": "pctBusy=5.6",
         "log_summary": "19 exact source-ID rows of 19 returned; 0 ERROR; 1 WARN"},
    ]


def _device():
    return {
        "kind": "device", "id": "7182", "name": "Device Status Report Display",
        "matching_rows": 24,
        "groups": [{
            "level": "error", "count": 24,
            "summary": (
                "dev|7182|Device Status Report Display|"
                "com.hubitat.app.exception.LimitExceededException: "
                "App 3977 generates excessive hub load on line 64 "
                "(method setReportData)"
            ),
        }],
    }


def test_cross_source_device_exception_preserves_zero_direct_app_rows():
    checks = _checks()
    _reconcile_requested_app_exception_sources(checks, [_device()])
    assert checks[0]["log_summary"].endswith("0 LimitExceededException")
    assert checks[2]["log_summary"].endswith("1 WARN")
    app = checks[1]["log_summary"]
    assert "0 exact source-ID rows of 0 returned" in app
    assert "24 matched log row(s) from device 7182" in app
    assert "explicitly name this app in LimitExceededException" in app
    assert "timestamp coverage unverified" in app
    assert "24 independent incidents" not in app


def test_cross_source_does_not_misattribute_or_invent_evidence():
    for item in (
        {**_device(), "kind": "app"},
        {"kind": "device", "id": "7182", "groups": [{
            "count": 24, "summary": (
                "dev|7182|Display|LimitExceededException: "
                "App 3888 generates excessive hub load"
            )}]},
        {"kind": "device", "id": "7182", "groups": [{
            "count": 24, "summary": (
                "dev|7182|Display|INFO App 3977 generates excessive hub load"
            )}]},
        {"kind": "device", "id": "7182", "error": "hub offline", "groups": _device()["groups"]},
    ):
        checks = _checks()
        _reconcile_requested_app_exception_sources(checks, [item])
        assert checks == _checks()
    # Mere mention of the app in the free-text payload is not a source attribution.
    checks = _checks()
    _reconcile_requested_app_exception_sources(checks, [{
        "kind": "device", "id": "7182", "groups": [{
            "count": 24,
            "summary": "dev|9999|Other|LimitExceededException: App 3977 generates excessive hub load",
        }],
    }])
    assert checks == _checks()


HOST = """### Requested app checks — bounded, source-specific
- App 3977: 0 exact source-ID rows of 0 returned. Additional device-originated
evidence: 24 matched log rows from device 7182 explicitly name app 3977 in
LimitExceededException: App 3977 generates excessive hub load on line 64.
### Offline-device evidence (identity-grounded)
- Bedroom 3 Mesh reported offline; verify upstream telemetry.
### Performance leaders (not automatic faults)
- App 3977: averageMs=107090.14.
Performance data is a top-ranked sample.
"""
ADVISORY = """**1. Error: App 3977 (Device Status Report) Load Exception**
* **Observed Evidence:** 24 log rows explicitly report LimitExceededException in App 3977.
* **Practical Impact:** Hubitat's internal load protection is actively throttling this app to prevent system-wide instability.

**2. Bedroom 3 Mesh**
* **Practical Impact:** The device is currently unreachable and unable to trigger or receive commands.

**3. Performance Risk**
* **Practical Impact:** Extremely high average execution times for a single app increase the risk of triggering the LimitExceededException observed above.
"""


def test_calibration_catches_live_causal_overclaims_but_retains_exceptions():
    fixed, reasons = calibrate_audit_ai_advisory(ADVISORY, HOST)
    assert set(reasons) == {
        "throttling_effect_unverified",
        "offline_command_effect_unverified",
        "runtime_exception_causality_unverified",
    }
    assert "24 log rows explicitly report" in fixed
    assert "actively throttling this app" not in fixed
    assert "unable to trigger or receive commands" not in fixed
    assert "increase the risk of triggering" not in fixed
    assert "actual command reachability" in fixed
    assert "whether it throttled ongoing calls" in fixed
    assert "does not prove which operation caused each exception" in fixed


def test_no_guard_without_host_evidence():
    assert calibrate_audit_ai_advisory(ADVISORY, "") == (ADVISORY, ())
    assert calibrate_audit_ai_advisory(
        "**App 3977:** 24 explicit excessive load errors observed.",
        HOST,
    ) == ("**App 3977:** 24 explicit excessive load errors observed.", ())


def test_report_includes_both_scopes_after_reconciliation():
    checks = _checks()
    _reconcile_requested_app_exception_sources(checks, [_device()])
    snapshot = {
        "checked_at": "2026-10-23T23:10:25+00:00",
        "sections": {
            "devices": {"total": 0, "available": True},
            "automations": {"total": 0, "available": True},
            "logs": {"entries_checked": 0, "checked_hours": 24, "available": True},
        }, "issues": [], "status": "healthy",
    }
    message = render_comprehensive_system_audit(
        snapshot, None, requested_app_checks=checks
    )
    assert "Requested app checks" in message
    assert "24 matched log row(s) from device 7182" in message
    assert "0 exact source-ID rows of 0 returned" in message
