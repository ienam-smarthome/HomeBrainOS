"""v0.18.88: full Groovy retrieval cannot satisfy an unrelated Rule Machine answer."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groovy_source_investigation import requested_groovy_app_id
from targeted_rule_scope_policy import is_existing_rule_verification_request
from source_analysis_completion import source_answer_focus
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "READ-ONLY: Investigate the actual Groovy source for installed App 3977 "
    "(Device Status Report). Find method setReportData and inspect line 64, "
    "its callers, scheduling and relevant configuration. Explain possible causes "
    "of the observed LimitExceededException errors emitted through device 7182. "
    "First retrieve and verify the source code, then compare it with available "
    "runtime logs. Clearly state what is proven and what remains uncertain. "
    "Do not modify anything."
)

WRONG = (
    "**Read-only existing-rule verification** — no modifying calls. "
    "App 3977: stopped=false, 0 local variables. "
    "Complete triggers, ordered actions and nested IF structure unverified."
)


def test_ambiguous_phrase_is_source_first_not_rule_machine():
    assert requested_groovy_app_id(REQUEST) == "3977"
    # "compare" and "configuration" collide with old Rule Machine classifier.
    assert is_existing_rule_verification_request(REQUEST)
    # Production orchestrator explicitly gives source intent priority.
    text = (ROOT / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "not source_investigation\n            and is_existing_rule_verification_request" in text
    assert "not source_investigation\n            and requires_rule_logic_inspection" in text


def test_method_focus_rejects_irrelevant_rule_report():
    focus = source_answer_focus(REQUEST, WRONG)
    assert focus["required"] is True
    assert focus["satisfied"] is False
    assert focus["method"] == "setReportData"
    assert set(focus["missing"]) == {
        "named_method_not_addressed",
        "requested_load_error_not_addressed",
    }


def test_relevant_method_answer_passes_keyword_focus_but_not_source_proof():
    answer = (
        "The setReportData Groovy method must be examined for the "
        "LimitExceededException reported at line 64. The available "
        "runtime evidence does not yet establish the triggering call."
    )
    focus = source_answer_focus(REQUEST, answer)
    assert focus["required"] and focus["satisfied"]
    assert "not certification" in focus["note"].replace("is not certification", "not certification")


def test_full_workbench_with_wrong_answer_remains_unresolved():
    outcome = SimpleNamespace(
        route="unified-mcp-agent",
        request_class="live-read",
        message=WRONG,
        metrics={"outcome": "success", "counters": {}},
        evidence=[{
            "tool": "homebrain_read_groovy_source",
            "sub_tool": None,
            "arguments": {"appId": "3977", "symbols": ["setReportData"]},
            "success": True,
            "evidence_kind": "groovy_source_investigation_evidence",
            "mutates": False,
            "effect": "read",
            "details": {
                "sourceRetrieved": True,
                "fullImplementationVerified": True,
                "verifiedCharacters": 81240,
                "declaredTotalCharacters": 81240,
                "verifiedPages": 2,
                "sourceCodeId": "1410",
            },
        }],
    )
    result = apply_shared_investigation_completion(outcome, REQUEST)
    coverage = result.investigation_coverage
    assert coverage["domain"] == "source_code"
    assert coverage["questionResolved"] is False
    assert coverage["objectiveSatisfied"] is False
    assert coverage["analysisAnswerVerified"] is False
    assert coverage["analysisStatus"] == "source-answer-off-objective"
    assert coverage["answerFocus"]["method"] == "setReportData"
    assert "did not address" in result.message
    assert "ordered actions" not in result.message


def test_source_question_skips_generic_performance_rewrite():
    path = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if requested_groovy_app_id(request.message) is not None:" in path
    assert "return outcome\n        return await finalize_performance_api_outcome(" in path
