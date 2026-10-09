import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from performance_api_finalizer import (
    _repair_scheduler_probe_history_inference,
    _repair_scheduler_unverified_absence_labels,
)


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


def test_repairs_live_016148_generic_recommendation_and_no_longer_present_hypothesis():
    draft = """### Identified Inefficiencies & Diagnostic Hypotheses

**1. Failed Device Lookups (MCP Rule Server)**
- **Observation:** Errors mention IDs 6921, 6918, 6911, 6913, 6910, and 2065.
- **Diagnostic Hypothesis:** The MCP Rule Server is attempting to poll devices that are no longer present in the hub inventory.

### Recommended Inspection Steps

- **Configuration Audit:** Review the MCP Rule Server (App 4151) settings to remove or update references to the missing device IDs (6921, 6918, 6911, 6913, 6910, 2065).
- **Reporting Review:** Keep this unrelated recommendation.
"""
    fixed, changed = _repair_scheduler_probe_history_inference(draft, _report())
    assert changed is True
    assert "no longer present in the hub inventory" not in fixed
    assert "remove or update references" not in fixed
    assert fixed.count("unresolved lookup observations only") >= 2
    assert "Keep this unrelated recommendation" in fixed


def test_repairs_live_016149_missing_orphan_deleted_scheduler_labels():
    draft = """| Candidate device (unverified) | 2065 (Not in inventory) | checkEventInterval | scheduler-key-pattern |
| Unresolved Devices | Jobs scheduled for missing entities | 43 candidate device IDs in scheduler not present in returned inventory |
3. **Orphaned Job Audit:** Investigate the 43 device IDs present in the scheduler but absent from the device inventory to determine if they are remnants of deleted devices.
"""
    fixed, changed = _repair_scheduler_unverified_absence_labels(draft, _report())
    assert changed is True
    assert "Not in inventory" not in fixed
    assert "missing entities" not in fixed
    assert "Orphaned Job Audit" not in fixed
    assert "deleted devices" not in fixed
    assert "not listed in returned device source; unresolved" in fixed
    assert "Unresolved Candidate Audit" in fixed


def test_repairs_live_016150_cleanup_heading_system_table_and_action_without_ids():
    draft = """| **System Errors** | MCP Rule Server: Multiple "Device not found" errors for IDs 6918, 6921, 6911, 6913, 6910, 2065 | Adaptive Diagnostic Logs |

* **Orphaned References:** The MCP Rule Server is explicitly logging errors when attempting to access six specific device IDs that were not present in the returned device inventory.

1. **MCP Rule Server Cleanup (Hypothesis):** The target-scoped diagnostic read did not establish a mechanism.
    * These device IDs are unresolved lookup observations only.
    * **Action:** Remove orphaned device references to reduce error log volume.
"""
    fixed, changed = _repair_scheduler_probe_history_inference(draft, _report())
    assert changed is True
    assert "**System Errors**" in fixed
    assert "Multiple \"Device not found\" errors" not in fixed
    assert "**Orphaned References:**" not in fixed
    assert "Remove orphaned device references" not in fixed
    assert "Do not infer deletion" in fixed
    assert "Do not remove references from this evidence" in fixed
