"""Live 0.18.82 comprehensive-audit regression from 23 October 2026."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit_ai_advisory_guard import calibrate_audit_ai_advisory
from automation_status_service import AutomationStatusOutcome
from api_response_builder import build_agent_response


HOST_REPORT = """
- Logs: 200 returned rows (requested lookback: 24 hours, at most 200 rows).
- **Log window saturated:** all 200 requested rows were returned. Older errors
in the 24-hour period may have been displaced by newer events.
### Temporary user-reported device condition
- SenseCap D1: intentionally switched off (no power), user-reported unpowered.
### Performance leaders (not automatic faults)
- Device Tasmota Discovery Listener (ID 7292): pctBusy=24.7%.
- App SenseCap D1 Settings (ID 4129): pctBusy=21.2%.
Performance data is a top-ranked sample, not an audit of every device or app.
- App performance source: 20 top-ranked rows returned.
"""
BAD_ADVISORY = """Based on the provided diagnostic report, there is no evidence that Life360 (app 4061), Device Status Report (app 3977), or Octopus Energy (app 3933) are causing excessive Hubitat load.

### Strongest Evidence-Backed Findings

**1. Performance Risk: Target apps are not high-load contributors**
* **Observed Evidence:** None of the three target apps appear in the top-20 sample.
* **Practical Impact:** These apps are unlikely to be the primary drivers of system latency or CPU contention compared to the listed performance leaders.
* **Certainty:** High (relative to the provided sample).

**2. Errors: No LimitExceededException observed**
* **Observed Evidence:** A review of the 200 returned log rows and scoped diagnostic findings shows no instances of LimitExceededException for any app ID, including 4061, 3977, or 3933. The only recorded warnings relate to device watchdogs and a paused automation.
* **Practical Impact:** There is no evidence of API rate-limiting or runtime integration failures for these specific applications.
* **Certainty:** High (for the provided log sample).

**3. Expected Condition: SenseCap D1 load is a known state**
* **Practical Impact:** High load or transport failures associated with this app/device are expected and do not indicate an unexplained system fault.
* **Certainty:** Absolute (based on user-supplied configuration).
* **Next Read-Only Test:** No test required until the device is powered back on.

### Target App Summary
| App Name | App ID | LimitExceededException Observed? | Performance Sample Status |
| --- | --- | --- | --- |
| Life360 | 4061 | **No** | Not in top 20 |
| Device Status Report | 3977 | **No** | Not in top 20 |
| Octopus Energy | 3933 | **No** | Not in top 20 |
"""


def test_replay_repairs_unjustified_absence_and_absolute_confidence():
    fixed, reasons = calibrate_audit_ai_advisory(BAD_ADVISORY, HOST_REPORT)
    assert set(reasons) == {
        "topn_absence", "saturated_logs", "user_reported_not_causal",
        "overconfident_certainty",
    }
    assert "there is no evidence that Life360" not in fixed
    assert "are not high-load contributors" not in fixed
    assert "unlikely to be the primary drivers" not in fixed
    assert "shows no instances of" not in fixed
    assert "The only recorded warnings" not in fixed
    assert "API rate-limiting or runtime integration failures" not in fixed
    assert "High load or transport failures associated" not in fixed
    assert "Absolute (based on" not in fixed
    assert "| **No** |" not in fixed
    assert "Not shown in bounded log sample" in fixed
    assert "top-ranked sample does not establish" in fixed
    assert "saturated page does not exclude" in fixed
    assert "attribution of app load to that state is unverified" in fixed


def test_guard_never_invents_errors_when_sample_is_empty():
    fixed, _ = calibrate_audit_ai_advisory(BAD_ADVISORY, HOST_REPORT)
    assert "App 4061 generates excessive hub load" not in fixed
    assert "App 3977 generates excessive hub load" not in fixed
    assert "confirmed current fault" not in fixed


def test_no_repair_of_already_calibrated_advice():
    value = (
        "The three named apps were not returned in a top-ranked performance sample. "
        "The available rows cannot establish current low resource use or "
        "full 24-hour exception coverage. SenseCap D1 is reportedly unpowered."
    )
    assert calibrate_audit_ai_advisory(value, HOST_REPORT) == (value, ())


def test_no_saturated_log_repair_without_report_proving_saturation():
    value = "### Target App Summary\n| Life360 | 4061 | **No** | Not in top 20 |\n"
    fixed, reasons = calibrate_audit_ai_advisory(value, "Small log sample; no evidence of saturation.")
    assert fixed == value and reasons == ()


def test_model_reported_only_when_provider_attribution_is_verified():
    outcome = AutomationStatusOutcome(
        message="Comprehensive Hubitat audit — read-only.",
        route="comprehensive-system-audit",
        ai_analysis_status="completed",
        ai_analysis_model="gemma4:31b",
        ai_analysis_provider="ollama-cloud",
        ai_advisory_repairs=("topn_absence",),
    )
    result = build_agent_response(
        outcome, model="configured-not-verified", elapsed_ms=100,
        version="0.18.83",
    )
    assert result["model"] == "gemma4:31b"
    assert result["ai_analysis"]["model_verified"] is True
    assert result["ai_analysis"]["provider"] == "ollama-cloud"
    assert result["ai_analysis"]["evidence_calibration"] == ["topn_absence"]
    assert result["evidence_validation"]["audit_ai_advisory_calibrated"] is True


def test_completed_but_provider_unknown_does_not_guess_model_name():
    outcome = AutomationStatusOutcome(
        message="A valid advisory.",
        route="comprehensive-system-audit", ai_analysis_status="completed",
    )
    result = build_agent_response(
        outcome, model="configured-not-verified", elapsed_ms=100,
        version="0.18.83",
    )
    assert result["model"] is None
    assert result["ai_analysis"]["model_verified"] is False
    assert "audit_ai_advisory_calibrated" not in result["evidence_validation"]


def test_disabled_or_timeout_audit_never_claims_model_participation():
    for status in ("disabled_by_configuration", "timed_out", "unavailable", "empty_response"):
        outcome = AutomationStatusOutcome(
            message="Host evidence only",
            route="comprehensive-system-audit", ai_analysis_status=status,
            ai_analysis_model="gemma4:31b",
        )
        result = build_agent_response(
            outcome, model="configured-not-verified", elapsed_ms=100,
            version="0.18.83",
        )
        assert result["model"] is None
        assert result["ai_analysis"]["status"] == status
