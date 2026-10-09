import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from performance_api_finalizer import _repair_scheduler_probe_history_inference


def _report():
    return {
        "secondaryDeviceSource": {
            "probeMayEmitExpectedNotFoundLogs": True,
            "probedExamples": ["2065", "6910", "6911", "6913", "6918", "6921"],
        }
    }


def test_repairs_orphan_diagnosis_and_cleanup_from_probe_history():
    draft = """### Identified Unnecessary Work & Diagnostic Hypotheses

**1. MCP Rule Server (App 4151) Orphaned Device Requests**
* **Observation:** logs show Device not found for IDs 6918, 6921 and 2065.
* **Diagnostic Hypothesis:** The MCP Rule Server is polling devices that no longer exist.
* **Verification:** Inspect the MCP Rule Server configuration for references to these device IDs.
* **Recommendation:** Remove orphaned device references from the app configuration.
"""
    fixed, changed = _repair_scheduler_probe_history_inference(draft, _report())
    assert changed is True
    assert "Orphaned Device Requests" not in fixed
    assert "no longer exist" not in fixed
    assert "Remove orphaned" not in fixed
    assert "Do not infer deletion" in fixed
    assert "diagnostic side effects from an earlier request" in fixed


def test_does_not_repair_without_probe_provenance_flag():
    draft = "**1. MCP Rule Server Orphaned Device Requests**\n"
    fixed, changed = _repair_scheduler_probe_history_inference(
        draft, {"secondaryDeviceSource": {"probedExamples": ["2065"]}}
    )
    assert fixed == draft
    assert changed is False


def test_unrelated_rule_server_error_is_preserved():
    draft = """**1. MCP Rule Server Runtime Error**
* **Observation:** unrelated transport timeout for request abc.
"""
    fixed, changed = _repair_scheduler_probe_history_inference(draft, _report())
    assert fixed == draft
    assert changed is False


def test_repairs_live_016147_recommendation_table_shape():
    draft = """### Efficiency Recommendations

| Target | Observation | Recommended Inspection Step |
| :--- | :--- | :--- |
| **MCP Rule Server (4151)** | Repeated `[ERROR]` logs for missing devices; highest app `pctTotal` (1.981%). | Inspect app configuration to remove references to the six missing device IDs. |
The target-scoped diagnostic read returned 13 non-diagnostic log observation(s).
| **Unattributed Jobs** | 42 instances of `sendEventReminder`. | Inspect source. |
"""
    fixed, changed = _repair_scheduler_probe_history_inference(draft, _report())
    assert changed is True
    assert "Inspect app configuration to remove references" not in fixed
    assert "do not prove orphaned devices" in fixed
    assert "Do not remove references from this evidence" in fixed
    assert "| **Unattributed Jobs**" in fixed
