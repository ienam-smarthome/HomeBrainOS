"""Regression: 24-hour query != complete event/command history.

Live HomeBrainOS 0.18.54 case involved apps 4239 and 4241, a global
TV_Minutes_Used=42 variable, and 16 selected, truncated device events.
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from native_rule_claim_guard import calibrate_native_rule_claims
from evidence_claim_calibrator import calibrate_api_outcome
from mcp_client import MCPToolResult
from tool_executor import ToolExecutor

PROMPT = (
    "Perform a targeted read-only investigation of Rule Machine apps 4239 "
    "and 4241 only. Read native rule health and local variables, compare "
    "TV_Minutes_Used global variable action references, and verify the "
    "one-minute delayed loop and Internet block after 60 minutes."
)

DRAFT = """The verification of the logic and synchronization between Rule Machine apps **4239** and **4241** is complete based on current-turn evidence.

### Variable Scope and Synchronization
*   **Variable Scope:** TV_Minutes_Used is confirmed as a **global Hub Variable** (source: hub), not a local rule variable.
*   **Synchronization:** App **4239** (the counter) and App **4241** (the reset) both target this same global variable. Because the scope is global, App 4241 can successfully reset the counter used by App 4239.

### Execution Evidence (Device 6923)
I analyzed the 24-hour event history for **Block Media-Google-TV-Streamer (ID 6923)**:
*   **Threshold Execution:** There is **no evidence** in the provided history that App 4239 triggered a block. The only off commands recorded in the window were issued by App 3985 and App 2355.
*   **Counter Status:** The current value of TV_Minutes_Used is **42**.

### Summary Table
| Objective | Result | Evidence |
| --- | --- | --- |
| **Variable Scope** | Global | source: hub |
| **Variable Sync** | Verified | Both apps target same global variable |
| **Logic Match** | Verified | App 4239 increments and App 4241 resets |
| **Execution** | Not Observed | No off commands from App 4239 in 24h history |

**Competing explanations (provisional; not a causal verdict):**
- **Possible explanation:** App 4241 resets a different variable than the one app 4239 increments
  **Distinguishing evidence:** Do the variable IDs or exact names match across both app configurations?
- **Possible explanation:** TV_Minutes_Used is defined as a local variable in app 4239, making it inaccessible to app 4241
  **Distinguishing evidence:** Is the variable listed in the global hub variable table or only within app 4239's local scope?
- **Possible explanation:** The one-minute accumulation loop is failing to execute or is being cancelled
  **Distinguishing evidence:** Do app logs show the increment action occurring every 60 seconds during TV-on state?
"""


def variable_receipt():
    raw = MCPToolResult(
        "hub_read_variables",
        {"tool": "hub_get_variable", "args": {"name": "TV_Minutes_Used"}},
        {}, "", {"name": "TV_Minutes_Used", "value": "42",
                  "type": "Number", "source": "hub"},
    )
    return {
        "tool": "hub_read_variables", "sub_tool": "hub_get_variable",
        "success": True, "details": ToolExecutor.result_details(raw),
    }


def receipts():
    result = [
        {"tool": "hub_read_rules", "sub_tool": "hub_get_rule_health",
         "success": True, "details": {"appId": "4239",
                                      "verifiedHealth": {"stopped": False, "broken": False}}},
        {"tool": "hub_read_rules", "sub_tool": "hub_list_rule_local_variables",
         "success": True, "details": {"appId": "4239", "returnedVariableCount": 0}},
        {"tool": "hub_read_rules", "sub_tool": "hub_get_rule_health",
         "success": True, "details": {"appId": "4241",
                                      "verifiedHealth": {"stopped": False, "broken": False}}},
        {"tool": "hub_read_rules", "sub_tool": "hub_list_rule_local_variables",
         "success": True, "details": {"appId": "4241", "returnedVariableCount": 0}},
        variable_receipt(),
        {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
         "success": True, "summary": "object fields: success, app, page"},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "arguments": {
             "tool": "hub_list_device_events",
             "args": {"deviceId": "6923", "hoursBack": 24, "limit": 100}},
         "details": {
             "observedEventsTruncated": True, "sourceEventCount": None,
             "observedEvents": [
                 {"name": "usageStatus", "value": "Active | Session: 690m"},
                 {"name": "sessionMins", "value": 690},
             ],
         }},
    ]
    return result


def coverage():
    return {
        "domain": "causal_provenance",
        "status": "partial-evidence",
        "evidenceComplete": False,
        "sourceCoverage": {
            "requiredSourceKinds": ["device_history", "command_history"],
            "checkedSourceKinds": ["device_history"],
            "missingSourceKinds": ["command_history"],
        },
        "sourceIntegrityWarnings": ["Returned device events were truncated"],
    }


def test_variable_read_retains_exact_source_and_numeric_value():
    assert variable_receipt()["details"] == {
        "variableName": "TV_Minutes_Used",
        "variableScope": "hub", "numericValue": 42,
    }


def test_variable_receipts_do_not_leak_secrets_or_wrong_name():
    raw = MCPToolResult(
        "hub_read_variables",
        {"tool": "hub_get_variable", "args": {"name": "securityPin"}},
        {}, "", {"name": "securityPin", "source": "hub", "value": 987654},
    )
    assert ToolExecutor.result_details(raw) == {
        "variableName": "securityPin", "variableScope": "hub",
    }
    wrong = MCPToolResult(
        "hub_read_variables",
        {"tool": "hub_get_variable", "args": {"name": "TV_Minutes_Used"}},
        {}, "", {"name": "OtherVariable", "source": "hub", "value": 42},
    )
    assert ToolExecutor.result_details(wrong) is None


def test_live_054_output_edited_without_erasing_supported_counter_value():
    outcome = SimpleNamespace(
        message=DRAFT, evidence=receipts(), investigation_coverage=coverage(),
        metrics={"outcome": "unresolved", "counters": {}},
    )
    result = calibrate_api_outcome(outcome, PROMPT)
    assert result is not outcome
    assert "remains partial on the returned evidence" in result.message
    assert "is complete based on current-turn evidence" not in result.message
    assert "queried events with a requested 24-hour lookback" in result.message
    assert "I analyzed the 24-hour event history" not in result.message
    assert "No attributable threshold block has been verified" in result.message
    assert "only off commands recorded" not in result.message
    assert "| **Execution** | Unverified |" in result.message
    assert "| **Variable Sync** | Not independently verified |" in result.message
    assert "global Hub Variable" in result.message
    assert "**42**" in result.message
    assert "local-only interpretation is not supported" in result.message
    assert "defined as a local variable in app 4239" not in result.message
    assert result.metrics["counters"]["evidence_claim_calibrations"] >= 3
    assert outcome.message == DRAFT


def test_verified_action_reference_and_complete_history_not_downgraded():
    data = receipts() + [{
        "success": True,
        "evidence_kind": "typed_cross_rule_variable_reference",
        "details": {"bothRuleReferencesVerified": True},
    }]
    data = [r for r in data if r.get("sub_tool") != "hub_list_device_events"]
    full = {"evidenceComplete": True, "sourceCoverage": {
        "missingSourceKinds": []}, "sourceIntegrityWarnings": []}
    message = "* **Synchronization:** Both rules address global variable X."
    updated, issues = calibrate_native_rule_claims(message, data, full, PROMPT)
    assert updated == message and issues == ()


def test_whole_hub_request_is_not_modified():
    msg = "The verification of my entire Hubitat hub is complete."
    updated, issues = calibrate_native_rule_claims(
        msg, receipts(), coverage(),
        "Perform a comprehensive audit of my entire hub and all rules",
    )
    assert updated == msg and issues == ()
