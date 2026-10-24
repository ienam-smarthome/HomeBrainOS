"""Architecture regression: one objective governs MCP synthesis and evidence checks.

Replays real 0.18.88 App 3977 source/exception failure without Hubitat writes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from investigation_objective import resolve_primary_objective
from historical_causal_claim_guard import assess_historical_claims
from shared_investigation_completion import apply_shared_investigation_completion
from synthesis_validator import validate_synthesis


REQUEST = (
    "READ-ONLY: Investigate actual Groovy source for installed App 3977. "
    "Find method setReportData, inspect line 64 and callers, and explain "
    "possible causes of LimitExceededException from device 7182. "
    "Compare the source to scoped runtime logs. Do not modify anything."
)
RULE = (
    "Perform comprehensive read-only existing Rule Machine app 4246 audit. "
    "Compare ordered triggers and actions and show actual source fields."
)
GOOD = (
    "In the retrieved Groovy source, setReportData is a candidate method "
    "requiring review of the body and its callers. "
    "LimitExceededException in the device-originated log names App 3977, "
    "but a direct app-scoped log query does not establish the triggering "
    "callback or which operation caused the excessive load. "
    "The cause remains a hypothesis pending scoped execution evidence."
)


def _outcome(answer: str, *, method_shown: bool):
    return SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read", message=answer,
        metrics={"outcome": "success", "counters": {}},
        evidence=[{
            "tool": "homebrain_read_groovy_source",
            "success": True,
            "evidence_kind": "groovy_source_investigation_evidence",
            "arguments": {"appId": "3977", "symbols": ["setReportData"]},
            "details": {
                "sourceRetrieved": True,
                "fullImplementationVerified": True,
                "verifiedCharacters": 81240,
                "declaredTotalCharacters": 81240,
                "verifiedPages": 2,
                "sourceCodeId": "1410",
                "verifiedCandidateMethodBodies": (
                    ["setReportData"] if method_shown else []
                ),
            },
        }],
    )


def test_one_request_objective_disambiguates_all_overlapping_vocabulary():
    objective = resolve_primary_objective(REQUEST)
    assert objective.domain == "source_code"
    assert objective.installed_app_id == "3977"
    assert objective.method_symbol == "setReportData"
    assert objective.excessive_load_requested is True
    rule = resolve_primary_objective(RULE)
    assert rule.domain == "existing_rule_verification"
    assert not rule.is_source


def test_same_app_load_statement_is_not_historical_device_command():
    reply = (
        "App 3977 executed setReportData, sent report updates, and caused "
        "excessive hub load during a report callback. A LimitExceededException "
        "was recorded, but the specific call chain is unverified."
    )
    assert assess_historical_claims(
        reply, [], command_only=True
    )["unverifiedCommandActors"] == []


def test_spontaneous_claimed_real_historical_device_command_still_checked():
    for message in (
        "App 3977 issued an OFF command to device 7182 on October 24.",
        "App 3977 switched device 7182 off at 07:05.",
        "App 3977 sent a switch-off command to device 7182.",
    ):
        assert assess_historical_claims(
            message, [], command_only=True
        )["unverifiedCommandActors"] == ["3977"]


def test_full_file_and_keyword_answer_do_not_prove_method_body_review():
    result = apply_shared_investigation_completion(
        _outcome(GOOD, method_shown=False), REQUEST
    )
    coverage = result.investigation_coverage
    assert coverage["sourceCoverage"]["sourceKindsChecked"] is True
    assert coverage["fullImplementationVerified"] is True
    assert coverage["answerFocus"]["satisfied"] is True
    assert coverage["methodBodyCoverage"]["status"] == "not-certified-by-source-span-receipts"
    assert coverage["questionResolved"] is False
    assert coverage["analysisAnswerVerified"] is False
    assert coverage["analysisStatus"] == "requested-method-excerpt-unverified"


def test_bounded_verified_candidate_body_can_satisfy_structural_coverage():
    result = apply_shared_investigation_completion(
        _outcome(GOOD, method_shown=True), REQUEST
    )
    coverage = result.investigation_coverage
    assert coverage["primaryObjective"] == {
        "kind": "source_code", "installedAppId": "3977", "method": "setReportData",
    }
    assert coverage["methodBodyCoverage"]["status"] == "balanced-candidate-method-body-shown"
    assert coverage["questionResolved"] is True
    assert "LimitExceededException" in result.message
    assert "Historical cause not established" not in result.message


def test_broad_performance_repairs_do_not_consume_code_diagnosis():
    candidate = (
        "Source function setReportData may do expensive work. "
        "LimitExceededException is named in dev|7182 records; "
        "no event provenance for the offending invocation was established."
    )
    fixed, issues = validate_synthesis(
        candidate, [], original_user=REQUEST, causal=False,
        primary_objective="source_code",
    )
    assert fixed == candidate
    assert not any(issue.startswith("performance") for issue in issues)


def test_final_model_and_api_share_same_objective_without_extra_rewrite():
    main = (APP / "app.py").read_text(encoding="utf-8")
    final = (APP / "final_answer_coordinator.py").read_text(encoding="utf-8")
    assert "primary_objective = resolve_primary_objective(request.message)" in main
    assert "if primary_objective.is_source:" in main
    assert "objective = resolve_primary_objective(original_user)" in final
    assert "not objective.is_source\n            and _performance_semantic_validation_needed" in final
    assert "PRIMARY INVESTIGATION OBJECTIVE — GROOVY SOURCE" in final
