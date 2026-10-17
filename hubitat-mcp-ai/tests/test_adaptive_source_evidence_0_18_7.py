"""Cross-domain objective coverage: implementation code != historical device cause."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from adaptive_investigation_policy import source_evidence_request
from general_evidence_completion import assess_task_source_coverage
from general_task_engine import GeneralTaskPlan
from shared_investigation_completion import apply_shared_investigation_completion
from tool_executor import ToolExecutor
from mcp_client import MCPToolResult


QUESTION = (
    "Inspect the actual Groovy source code for installed app 4019. "
    "Explain the getter and state expiry; read-only."
)


def _outcome(evidence):
    return SimpleNamespace(
        request_class="live-read",
        route="unified-mcp-agent",
        message="The installed code has not been verified.",
        evidence=evidence,
        metrics={"outcome":"success","counters":{}},
        investigation_coverage=None,
    )


def test_code_objective_not_mislabelled_causal_device_history():
    assert source_evidence_request(QUESTION)
    rows = [{
        "tool":"hub_read_apps_code", "sub_tool":"hub_get_app_config",
        "success":True, "effect":"read", "mutates":False,
    }]
    result = apply_shared_investigation_completion(_outcome(rows), QUESTION)
    coverage = result.investigation_coverage
    assert coverage["domain"] == "source_code"
    assert coverage["status"] == "source-unverified"
    assert coverage["sourceCoverage"]["missingSourceKinds"] == ["source_code"]
    assert result.metrics["outcome"] == "unresolved"
    assert "device_history" not in str(coverage)
    assert "command_history" not in str(coverage)


def test_successful_call_without_text_is_not_source_evidence():
    receipt = {
        "tool":"homebrain_read_groovy_source", "success":True,
        "effect":"read", "mutates":False,
        "details":{"sourceRetrieved":False},
    }
    result = apply_shared_investigation_completion(_outcome([receipt]), QUESTION)
    assert result.investigation_coverage["evidenceComplete"] is False


def test_retrieved_source_segment_is_not_full_code_verification():
    receipt = {
        "tool":"homebrain_read_groovy_source", "success":True,
        "effect":"read", "mutates":False,
        "details":{"sourceRetrieved":True},
    }
    result = apply_shared_investigation_completion(_outcome([receipt]), QUESTION)
    assert result.investigation_coverage["evidenceComplete"] is True
    assert result.investigation_coverage["fullImplementationVerified"] is False
    assert result.investigation_coverage["status"] == "source-segment-observed"
    assert result.metrics["outcome"] == "success"
    assert "device_history" not in str(result.investigation_coverage)


def test_tool_result_preserves_only_boolean_source_receipt():
    result = MCPToolResult(
        name="homebrain_read_groovy_source", arguments={"appId":"4019"},
        raw={}, text="", data={
            "sourceRetrieved":True,
            "report":"private int getMotionLockoutDurationMinutes(){}",
            "filePath":"/private/mcp-source-app-1453.groovy",
        }, is_error=False,
    )
    assert ToolExecutor.result_details(result) == {"sourceRetrieved":True}


def test_model_planner_can_request_source_code_evidence():
    import json
    result = GeneralTaskPlan.from_model(json.dumps({
        "version":"1", "domain":"code", "operation":"investigate",
        "objective":"Review implementation", "skills":["code_management"],
        "capabilityQueries":["source reader"],
        "evidenceGoals":["Read actual code"],
        "requiredEvidenceKinds":["source_code"],
    }))
    assert result is not None
    assert "source_code" in result.required_evidence_kinds
