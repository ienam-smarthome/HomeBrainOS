"""0.18.90 replay: source-verified call site, invented packet-size failure cause.

The real user output asserted that Hubitat LimitExceededException "typically"
means exceeding Zigbee/Z-Wave payload/character limits, despite lacking a
driver-source receipt or a verified device mapping. These tests are pure.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from source_exception_causality_guard import (
    guard_unverified_source_exception_mechanism,
)
from synthesis_validator import validate_synthesis
from api_response_builder import build_agent_response


SOURCE = [{
    "tool": "homebrain_read_groovy_source",
    "success": True, "mutates": False, "effect": "read",
    "arguments": {"appId": "3977", "symbols": ["setReportData"]},
    "details": {
        "sourceRetrieved": True, "fullImplementationVerified": True,
        "verifiedCharacters": 81240,
        "declaredTotalCharacters": 81240,
        "sourceCodeId": "1410",
    },
}]
RAW_MODEL = """Based on the retrieved source code and performance diagnostics:
**Verified Implementation:** The method setReportData is not defined in App 3977.
**Call Site (Line 820):** reportDisplayDevice.setReportData(reportText, offlineCount, lowBatteryCount, motionCount)

**Likely Cause:** The reportText argument is a dynamic string. In Hubitat, a LimitExceededException typically occurs when a command payload exceeds the maximum character limit allowed by the device transport protocol (e.g., Zigbee or Z-Wave packet limits).
**Mechanism:** Once this string exceeds the device buffer or protocol limit, the hub throws the exception.
* **Practical Impact:** Such high execution times often indicate that the app is waiting on a device response that is timing out.
| **Exception Cause** | **Hypothesis** | reportText string length exceeding transport/device limits. |
The setReportData driver body was not examined. The triggering call remains unverified.
"""


def test_exact_live_packet_limit_story_is_calibrated_without_erasing_callsite():
    fixed, repairs = guard_unverified_source_exception_mechanism(RAW_MODEL, SOURCE)
    assert "source_unsupported_payload_limit_cause" in repairs
    assert "source_unverified_wait_causality" in repairs
    assert "reportDisplayDevice.setReportData(" in fixed
    assert "The setReportData driver body was not examined" in fixed
    assert "LimitExceededException typically occurs" not in fixed
    assert "hub throws the exception" not in fixed
    assert "string length exceeding transport/device limits" not in fixed
    assert "often indicate that the app is waiting" not in fixed
    assert "not established" in fixed
    assert "not proof" in fixed


def test_no_unnecessary_repair_for_cautious_or_unrelated_answer():
    cautious = (
        "A LimitExceededException does not prove a payload or transport "
        "limit; no driver source verified the size of reportText."
    )
    assert guard_unverified_source_exception_mechanism(cautious, SOURCE) == (
        cautious, (),
    )
    normal = "App 3977 has high average execution time; cause unverified."
    assert guard_unverified_source_exception_mechanism(normal, SOURCE) == (
        normal, (),
    )


def test_driver_source_receipt_prevents_clobbering_actual_driver_analysis():
    verified_driver_source = {
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
        "arguments": {
            "tool": "hub_get_source",
            "args": {"type": "driver", "id": "987"},
        },
        "success": True, "mutates": False, "effect": "read",
    }
    assert guard_unverified_source_exception_mechanism(
        RAW_MODEL, SOURCE + [verified_driver_source],
    ) == (RAW_MODEL, ())


def test_source_synthesis_flags_mechanism_for_model_revision():
    corrected, issues = validate_synthesis(
        RAW_MODEL, SOURCE,
        original_user=(
            "Inspect installed app 3977 Groovy method setReportData and "
            "explain LimitExceededException"
        ),
        primary_objective="source_code",
    )
    assert "source_unsupported_payload_limit_cause" in issues
    assert "reportDisplayDevice.setReportData(" in corrected


def test_final_api_rechecks_mechanism_if_ai_reintroduces_bad_claim():
    outcome = SimpleNamespace(
        message=RAW_MODEL, route="unified-mcp-agent",
        request_class="live-read",
        evidence=SOURCE,
        metrics={"outcome": "unresolved", "counters": {}},
        investigation_coverage={
            "domain": "source_code", "questionResolved": False,
            "status": "full-source-observed",
        },
    )
    result = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=29404,
        version="0.18.91",
    )
    assert (
        "source_unsupported_payload_limit_cause" in
        result["evidence_validation"]["source_exception_mechanism_calibrated"]
    )
    assert "reportDisplayDevice.setReportData(" in result["message"]
    assert "typically occurs when a command payload" not in result["message"]
    assert "hub throws the exception" not in result["message"]


def test_genuine_app_source_does_not_masquerade_as_device_source():
    direct_app = {
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
        "arguments": {
            "tool": "hub_get_source",
            "args": {"id": "1410", "type": "app"},
        },
        "success": True, "mutates": False, "effect": "read",
    }
    _, repairs = guard_unverified_source_exception_mechanism(
        RAW_MODEL, SOURCE + [direct_app],
    )
    assert "source_unsupported_payload_limit_cause" in repairs
