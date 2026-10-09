from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_api_finalizer import (
    _performance_review_coverage,
    _repair_unattributed_performance_recommendations,
)
from performance_host_plan import is_whole_hub_optimization_request


def _evidence() -> list[dict]:
    return [
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_performance_stats",
            "success": True, "arguments": {
                "tool": "hub_get_performance_stats",
                "args": {"limit": 20, "sortBy": "pct", "type": "both"},
            },
        },
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_jobs",
            "success": True, "arguments": {"tool": "hub_get_jobs"},
        },
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_logs",
            "success": True, "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "logCount": 100, "hostDerivedTiming": {
                    "sameSecondClusters": [
                        {"rowCount": 38}, {"rowCount": 49}
                    ]
                }
            },
        },
    ]


def test_exact_whole_hub_prompt_requires_coverage_qualifiers():
    prompt = (
        "Review all devices, hub rules, apps, automations and all logs/events "
        "and suggest how to optimize and make the hub more efficient."
    )
    assert is_whole_hub_optimization_request(prompt)
    notes = _performance_review_coverage(_evidence())
    assert "requested up to 20 entries" in notes
    assert "Scheduled jobs were retrieved" in notes
    assert "not establish a CPU bottleneck" in notes
    assert "100 rows against its 100-row cap" in notes
    assert "38, 49 rows" in notes
    assert "did not independently inspect every installed app" in notes
    assert "Rule Machine action" in notes
    assert "verified savings" in notes


def test_unsaturated_logs_do_not_claim_log_truncation():
    evidence = _evidence()
    evidence[2]["details"]["logCount"] = 42
    notes = _performance_review_coverage(evidence)
    assert "100-row cap" not in notes
    assert "Scheduled jobs were retrieved" in notes


def test_no_successful_sources_have_no_pretend_coverage():
    evidence = [{"sub_tool": "hub_get_jobs", "success": False}]
    assert _performance_review_coverage(evidence) == ""


def test_deleted_app_query_error_does_not_imply_persistent_mcp_dependency():
    message = (
        "**Diagnostic Hypotheses**\n"
        "* **MCP Rule Server Configuration:** The measured mechanism remains unresolved.\n"
        "    * **Verification:** Inspect the MCP Rule Server configuration for "
        "references to app IDs 2954 and 2597.\n"
        "\n**Recommended Inspection Steps**\n"
        "1. **MCP Rule Server:** Verify if the references to missing apps "
        "(2954, 2597) are expected or can be removed to reduce error logging.\n"
        "2. **Power Monitoring:** Inspect meter reporting.\n"
    )
    fixed, changed = _repair_unattributed_performance_recommendations(message, _evidence())
    assert changed
    assert "Trace the caller and input parameters" in fixed
    assert fixed.count("Trace the caller and input parameters") == 2
    assert "can be removed" not in fixed
    assert "not evidence that MCP Rule Server retains those IDs" in fixed
    assert "2. **Power Monitoring:**" in fixed


def test_configuration_evidence_preserves_dependency_inspection_hypothesis():
    original = (
        "1. **MCP Rule Server:** Verify if the references to missing apps "
        "(2954, 2597) are expected or can be removed to reduce error logging."
    )
    evidence = _evidence() + [
        {"sub_tool": "hub_get_app_config", "success": True,
         "evidence_kind": "configuration_read"}
    ]
    assert _repair_unattributed_performance_recommendations(original, evidence) == (
        original, False
    )
