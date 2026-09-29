from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_evidence_first import (  # noqa: E402
    build_performance_synthesis_contract,
    guard_evidence_first_performance,
)
from synthesis_validator import (  # noqa: E402
    consume_performance_repair_issues,
    validate_synthesis,
)
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def _receipt(sub_tool: str) -> dict:
    return {
        "tool": "hub_manage_logs",
        "sub_tool": sub_tool,
        "success": True,
        "arguments": {"tool": sub_tool},
    }


def test_01677_raw_log_rows_do_not_author_an_exact_manual_update_count() -> None:
    draft = (
        "**Octopus Live Meter:** Five separate device updates occurred within a "
        "167ms window (`23:12:02.672` to `23:12:02.839`)."
    )

    corrected, changed = guard_evidence_first_performance(draft)

    assert changed is True
    assert "Five separate device updates" not in corrected
    assert "Multiple updates were recorded within the cited time window" in corrected
    assert "23:12:02.672" in corrected
    assert "23:12:02.839" in corrected


def test_01677_contract_forbids_job_claims_when_no_job_source_was_read() -> None:
    evidence = [
        _receipt("hub_get_metrics"),
        _receipt("hub_get_performance_stats"),
        _receipt("hub_get_logs"),
    ]

    contract = build_performance_synthesis_contract(evidence)

    assert "No current-turn scheduler/job source is present" in contract
    assert "Do not state job counts, alignment, cadence" in contract
    assert "Do not manually derive an exact update/event count from raw log rows" in contract


def test_01677_contract_allows_literal_job_facts_when_job_source_exists() -> None:
    contract = build_performance_synthesis_contract([_receipt("hub_get_jobs")])

    assert "A current-turn scheduler/job source is present" in contract
    assert "report only the returned job facts" in contract


def test_01677_metric_rows_split_agent_and_finalizer_model_rounds() -> None:
    consume_performance_repair_issues()
    rows = present_request_metrics(
        {
            "outcome": "success",
            "counters": {
                "model_rounds": 4,
                "tool_calls": 3,
                "performance_api_deterministic_repair": 1,
            },
            "timings_ms": {
                "total": 25409,
                "performance_api_model": 10125,
                "performance_api_finalize": 10237,
            },
        }
    )

    assert {"label": "Model rounds", "value": "4"} in rows
    assert {"label": "Agent model rounds", "value": "3"} in rows
    assert {"label": "Performance synthesis model rounds", "value": "1"} in rows
    assert {"label": "Deterministic performance repairs", "value": "1"} in rows


def test_01677_performance_repair_reason_is_fixed_vocabulary_and_consumed_once() -> None:
    consume_performance_repair_issues()
    evidence = [_receipt("hub_get_performance_stats")]
    corrected, issues = validate_synthesis(
        "Google Nest Hub is the primary consumer of execution time.",
        evidence,
    )
    assert "primary consumer of execution time" not in corrected
    assert "performance_evidence_first" in issues

    metrics = {
        "outcome": "success",
        "counters": {
            "model_rounds": 3,
            "performance_api_deterministic_repair": 1,
        },
        "timings_ms": {"performance_api_model": 6000},
    }
    first_rows = present_request_metrics(metrics)
    assert {
        "label": "Performance repair reason",
        "value": "Evidence-first performance contract",
    } in first_rows

    second_rows = present_request_metrics(metrics)
    assert not any(row.get("label") == "Performance repair reason" for row in second_rows)
