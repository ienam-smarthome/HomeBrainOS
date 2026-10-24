"""0.18.90: source-objective fidelity, app runtime evidence and bounded repair.

Replays App 3977's 0.18.89 false "method=body" and physical-device
runtime requirements. All tests are pure; no Hubitat read/write is issued.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from investigation_objective import (
    resolve_primary_objective, requested_groovy_method_symbol,
)
from source_analysis_completion import (
    source_answer_focus, source_runtime_evidence_status,
)
from shared_investigation_completion import apply_shared_investigation_completion
from final_answer_coordinator import FinalAnswerCoordinator


QUESTION = (
    "READ-ONLY: For installed app 3977 inspect the actual Groovy method body, "
    "especially setReportData and its callers. Explain the observed "
    "LimitExceededException involving device 7182; correlate it with the "
    "app configuration, execution logs and available runtime measurements. "
    "Do not change anything."
)


def receipt(tool, args, *, count=None):
    details = {"logCount": count} if count is not None else {}
    return {
        "tool": "hub_read_diagnostics",
        "sub_tool": tool, "arguments": {"tool": tool, "args": args},
        "details": details,
        "success": True, "mutates": False, "effect": "read",
    }


SCOPED = [
    receipt("hub_get_app_config", {"appId": "3977"}),
    receipt("hub_get_logs", {"appId": "3977", "since": "24h", "limit": 100}, count=0),
    receipt("hub_get_logs", {"deviceId": "7182", "since": "24h", "limit": 100}, count=0),
    receipt("hub_get_performance_stats", {"type": "app"}),
]
SOURCE = {
    "tool": "homebrain_read_groovy_source",
    "success": True, "mutates": False, "effect": "read",
    "arguments": {"appId": "3977", "symbols": ["setReportData"]},
    "details": {
        "sourceRetrieved": True, "fullImplementationVerified": True,
        "verifiedCharacters": 81240, "declaredTotalCharacters": 81240,
        "verifiedPages": 2, "sourceCodeId": "1410",
        "verifiedCandidateMethodBodies": [],
    },
}


def test_generic_method_body_is_never_treated_as_a_symbol():
    assert requested_groovy_method_symbol(QUESTION) == "setReportData"
    assert requested_groovy_method_symbol(
        "Read the Groovy method body for app 3977 and explain errors"
    ) is None
    assert requested_groovy_method_symbol(
        "Inspect method body and method setReportData in app 3977"
    ) == "setReportData"
    assert resolve_primary_objective(QUESTION).method_symbol == "setReportData"
    assert source_answer_focus(
        QUESTION, "setReportData raises no verified causal conclusion. "
        "LimitExceededException was recorded previously."
    )["satisfied"] is True
    no_name = source_answer_focus(
        "Read Groovy method body for app 3977 and investigate "
        "LimitExceededException.",
        "LimitExceededException was observed, method is not yet identified.",
    )
    assert no_name["method"] is None
    assert no_name["satisfied"] is True
    assert "named_method_not_addressed" not in no_name["missing"]


def test_installed_app_runtime_is_not_physical_device_monitoring():
    actual = source_runtime_evidence_status(QUESTION, SCOPED)
    assert actual["required"] is True
    assert actual["satisfied"] is True
    assert actual["missing"] == []
    assert actual["scope"] == "installed_app_source"
    assert actual["historicalEventConfirmed"] is False
    assert actual["boundedLogCounts"] == {"app_logs": 0, "device_logs": 0}
    assert "device_state" not in actual["checked"]
    assert "device_history" not in actual["missing"]


def test_app_runtime_missing_specific_log_query_is_partial_not_guessed():
    available = [SCOPED[0], SCOPED[1]]
    status = source_runtime_evidence_status(QUESTION, available)
    assert status["satisfied"] is False
    assert status["missing"] == ["device_logs"]
    assert status["historicalEventConfirmed"] is False


def test_full_source_does_not_certify_missing_method_excerpt():
    model_answer = (
        "The exact setReportData body has not been independently verified. "
        "The previous LimitExceededException names app 3977, but "
        "the current bounded app/device logs returned no rows. "
        "Callers and the triggering execution remain uncertain."
    )
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message=model_answer, evidence=[SOURCE, *SCOPED],
        metrics={"outcome": "success", "counters": {}},
    )
    result = apply_shared_investigation_completion(outcome, QUESTION)
    cov = result.investigation_coverage
    assert cov["primaryObjective"]["method"] == "setReportData"
    assert cov["answerFocus"]["method"] == "setReportData"
    assert cov["answerFocus"]["satisfied"] is True
    assert cov["runtimeEvidence"]["satisfied"] is True
    assert cov["methodBodyCoverage"]["status"] == "not-certified-by-source-span-receipts"
    assert cov["analysisStatus"] == "requested-method-excerpt-unverified"
    assert cov["questionResolved"] is False
    assert "device_state" not in result.message
    assert "device_history" not in result.message
    assert "setReportData" in result.message


@pytest.mark.asyncio
async def test_source_final_synthesis_repairs_off_objective_once():
    calls = []
    answers = [
        "Here are generic system statistics, without an app method diagnosis.",
        "The setReportData method source needs inspection. "
        "A LimitExceededException was historically reported, "
        "but its triggering call and caller are unverified.",
    ]
    async def chat(messages, tools):
        assert tools == []
        calls.append(messages)
        return {"content": answers.pop(0)}
    co = FinalAnswerCoordinator(chat, evidence_supplier=lambda: [])
    response = await co.answer([{"role": "user", "content": QUESTION}])
    assert len(calls) == 2
    assert "setReportData" in response
    assert "LimitExceededException" in response
    assert "SOURCE-OBJECTIVE REPAIR" in str(calls[-1])
