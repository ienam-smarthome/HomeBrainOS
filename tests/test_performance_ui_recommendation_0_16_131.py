from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui import render_page
from performance_api_finalizer import (
    _normalize_recommendation_table,
    _repair_unattributed_performance_recommendations,
)


def test_webui_has_safe_native_markdown_tables_and_numbered_recommendations():
    html = render_page("HomeBrain", "0.16.131")
    assert "function markdownTableCells(" in html
    assert "function isMarkdownTableDivider(" in html
    assert "function renderMarkdownTable(" in html
    assert "renderMarkdownTable(lines,i,cells)" in html
    assert "table.className='answer-markdown-table'" in html
    assert "wrap.className='answer-table-wrap'" in html
    assert "wrap.setAttribute('aria-label','Scrollable results table')" in html
    assert "td=document.createElement('td')" in html
    assert "appendInline(td,value)" in html
    assert "const type=numbered?'ol':'ul'" in html
    assert ".answer-table-wrap{max-width:100%;overflow-x:auto" in html
    assert "innerHTML=" not in html  # Never insert provider-authored table cells as HTML.


def _timing_evidence():
    return [{
        "tool": "hub_manage_logs",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
        "details": {
            "hostDerivedTiming": {
                "cadence": [{
                    "source": "Halo3000x socket power",
                    "sourceRef": "dev|5383",
                    "signal": "ActivePower",
                    "medianIntervalSeconds": 10.0,
                    "timingKind": "irregular_intervals",
                }]
            }
        }
    }]


def test_observation_only_recommendation_becomes_source_specific_inspection():
    original = (
        "### Recommended Inspection Steps\n"
        "1. MCP Rule Server: Inspect the configuration of the MCP Rule Server "
        "to determine if it is referencing apps 2954, 2597, or 4206.\n"
        "2. Job Scheduling: Inspect the current job queue.\n"
        "3. Device Reporting: Irregular observed intervals; median 10 seconds; "
        "observed range 9.953–19.958 seconds. No regular cadence was established.\n"
        "4. LG webOS TV: Investigate average execution times.\n"
    )
    corrected, changed = _repair_unattributed_performance_recommendations(
        original, _timing_evidence(),
    )
    assert changed
    assert "Inspect Halo3000x socket power (ID 5383), ActivePower" in corrected
    assert "Recorded timing: Irregular observed intervals" in corrected
    assert "Trace the caller and arguments of the failed app-config" in corrected
    assert "do not explain its performance share" in corrected
    assert "4. LG webOS TV" in corrected


def test_unattributed_cadence_is_not_assigned_to_random_device():
    original = "3. Device Reporting: Irregular observed intervals; median 10 seconds."
    corrected, changed = _repair_unattributed_performance_recommendations(original, [])
    assert changed
    assert "Identify the exact device and signal" in corrected
    assert "Unattributed sampled timing" in corrected
    assert "Halo3000x" not in corrected


def test_real_configuration_evidence_preserves_cautious_dependency_check():
    text = (
        "1. MCP Rule Server: Inspect the configuration of the MCP Rule Server "
        "to determine if it is referencing apps 2954 and 2597."
    )
    evidence = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True,
        "evidence_kind": "configuration_read",
    }]
    assert _repair_unattributed_performance_recommendations(text, evidence) == (text, False)


def test_existing_table_preservation_remains_compatible_with_ui():
    message = (
        "| Entity | ID | pctBusy |\n"
        "| :--- | :--- | :--- |\n"
        "| LG webOS TV | 7486 | 16.8% |\n"
        "\n| Priority | Target | Evidence |\n"
        "| :--- | :--- | :--- |\n"
        "| High | App 4151 | 23.1% |\n"
    )
    assert _normalize_recommendation_table(message) == (message, False)
