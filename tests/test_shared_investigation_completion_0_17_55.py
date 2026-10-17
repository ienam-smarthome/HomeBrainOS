"""A single final evidence gate across direct, specialist and model-led routes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_agent_orchestrator import AgentOutcome  # noqa: E402
from observed_agent_outcome import build_observed_agent_outcome  # noqa: E402
from shared_investigation_completion import (  # noqa: E402
    apply_shared_investigation_completion,
)
from api_response_builder import build_agent_response  # noqa: E402


def receipt(tool: str, operation: str, args: dict,
            *, details: dict | None = None, success: bool = True) -> dict:
    row = {
        "tool": tool, "sub_tool": operation, "success": success,
        "mutates": False, "effect": "read",
        "arguments": {"tool": operation, "args": args},
    }
    if details is not None:
        row["details"] = details
    return row


def outcome(evidence: list[dict] | None = None, *,
            request_class: str = "live-read", coverage=None, status="success"):
    return AgentOutcome(
        message="Observed device state changes; upstream cause not established.",
        request_class=request_class,
        evidence=evidence or [],
        choices=[],
        investigation_coverage=coverage,
    )


def serialize(value):
    return build_agent_response(
        value, model="gemma4:31b", elapsed_ms=34, version="0.17.55",
    )


def test_observed_agent_preserves_domain_investigation_coverage():
    original = outcome(coverage={
        "domain": "device_telemetry", "evidenceComplete": False,
        "nextMissingSources": ["targeted device logs"],
    })
    observed = build_observed_agent_outcome(original, {
        "outcome": "success", "counters": {}, "timings_ms": {},
    })
    assert observed.investigation_coverage == original.investigation_coverage


def test_fastpath_causal_history_only_is_partial_in_api():
    observed = build_observed_agent_outcome(outcome([
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "7805", "attribute": "switch", "limit": 50,
        }),
        receipt("homebrain_device_history", "homebrain_device_history", {
            "name": "Livingroom Light 1", "attribute": "switch",
        }, details={
            "historySourceIntegrityVerified": False,
            "observedEventsTruncated": True,
        }),
    ]), {"outcome": "success", "counters": {"evidence_sufficiency_stop": 1},
         "timings_ms": {}})
    checked = apply_shared_investigation_completion(
        observed, "Why did Livingroom Light 1 come back on?",
    )
    response = serialize(checked)
    assert response["metrics"]["outcome"] == "unresolved"
    assert response["outcome_presentation"]["value"] == "unresolved"
    assert "command_history" in response["investigation_coverage"][
        "sourceCoverage"]["missingSourceKinds"]
    assert response["investigation_coverage"]["assessmentScope"] == (
        "all-api-routes-read-only"
    )
    assert any("Event-history completeness" in warning for warning in response[
        "investigation_coverage"]["sourceIntegrityWarnings"])
    assert response["message"].startswith("Observed device state changes")
    assert "Investigation completeness: partial" in response["message"]


def test_domain_contract_remains_partial_after_required_sources_checked():
    rows = [
        receipt("hub_read_devices", "hub_list_devices", {
            "labelFilter": "Bedroom 3 Mesh", "detailed": True,
        }),
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "7103", "hoursBack": 24,
        }),
        receipt("hub_read_diagnostics", "hub_get_logs", {
            "deviceId": "7103", "since": "30m",
        }, details={"logCount": 0, "logs": []}),
    ]
    prior = {
        "domain": "device_telemetry", "evidenceComplete": False,
        "status": "partial-evidence",
        "nextMissingSources": ["targeted device history/lastSeen"],
        "requirements": [{"key": "freshness", "state": "checked-unverified"}],
    }
    tested = build_observed_agent_outcome(
        outcome(rows, coverage=prior),
        {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    response = serialize(apply_shared_investigation_completion(
        tested, "Investigate Bedroom 3 Mesh. Explain its offline status, "
                "stale telemetry, and connection watchdog evidence.",
    ))
    coverage = response["investigation_coverage"]
    assert coverage["sourceCoverage"]["sourceKindsChecked"] is True
    assert coverage["evidenceComplete"] is False
    assert coverage["requirements"] == prior["requirements"]
    assert response["metrics"]["outcome"] == "unresolved"


def test_rule_proposal_never_becomes_historical_investigation():
    original = build_observed_agent_outcome(outcome([
        receipt("hub_get_tool_guide", "hub_get_tool_guide", {
            "section": "visual_rule_reference",
        }),
    ]), {"outcome": "success", "counters": {}, "timings_ms": {}})
    tested = apply_shared_investigation_completion(
        original,
        "Prepare a proposal for a motion trigger automation. "
        "Do not create anything.",
    )
    assert tested is original
    assert serialize(tested)["metrics"]["outcome"] == "success"


def test_write_and_confirmation_outcomes_not_modified_by_gate():
    original = build_observed_agent_outcome(
        outcome(request_class="write"),
        {"outcome": "unresolved", "counters": {}, "timings_ms": {}},
    )
    assert apply_shared_investigation_completion(
        original, "Why was this switch turned on?",
    ) is original


def test_shared_gate_does_not_replace_failed_outcome():
    original = build_observed_agent_outcome(
        outcome(), {"outcome": "failed", "counters": {}, "timings_ms": {}},
    )
    guarded = apply_shared_investigation_completion(
        original, "Why did Livingroom Light 1 turn off?",
    )
    assert guarded.metrics["outcome"] == "failed"


def test_non_investigative_room_lookup_not_assessed():
    original = build_observed_agent_outcome(
        outcome(), {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    assert apply_shared_investigation_completion(
        original, "Which rooms are configured on Hubitat?",
    ) is original


def test_explicit_command_event_read_is_not_confused_with_switch_event_read():
    from general_evidence_completion import assess_task_source_coverage
    read = [
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "7805", "attribute": "switch",
        }),
    ]
    assert assess_task_source_coverage(
        ("command_history",), read,
    ).missing == ("command_history",)
    read.append(receipt("hub_read_devices", "hub_list_device_events", {
        "deviceId": "7805", "attribute": "command-on",
    }))
    assert assess_task_source_coverage(
        ("command_history",), read,
    ).sources_checked is True


def test_device_telemetry_without_offline_keyword_still_gets_shared_coverage():
    from investigation_intelligence import plan_investigation

    question = (
        "Investigate Bedroom 3 Mesh. Check its reported state, last telemetry "
        "activity and recent device logs. Explain which conclusions are "
        "established and which remain unverified. Read-only."
    )
    plan = plan_investigation(question)
    assert plan is not None and plan.domain == "device_telemetry"
    evidence = [
        receipt("hub_read_devices", "hub_list_devices", {
            "labelFilter": "Bedroom 3 Mesh", "detailed": True,
        }),
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "7103", "hoursBack": 24,
        }, details={"observedEventsTruncated": True,
                    "historySourceIntegrityVerified": False}),
        receipt("hub_read_diagnostics", "hub_get_logs", {
            "since": "30m", "limit": 100,
        }, details={"logCount": 100}),
        receipt("hub_read_diagnostics", "hub_get_logs", {
            "appId": "4072", "since": "24h",
        }, details={"logCount": 0}),
    ]
    observed = build_observed_agent_outcome(outcome(evidence), {
        "outcome": "success", "counters": {}, "timings_ms": {},
    })
    result = serialize(apply_shared_investigation_completion(
        observed, question,
    ))
    source = result["investigation_coverage"]["sourceCoverage"]
    assert "device_logs" in source["missingSourceKinds"]
    assert "device_history" in source["checkedSourceKinds"]
    assert result["investigation_coverage"]["domain"] == "device_telemetry"
    assert result["metrics"]["outcome"] == "unresolved"
    assert result["metrics"]["counters"]["shared_completion_checked"] == 1


def test_prospective_rule_explanation_does_not_become_diagnostic_telemetry():
    from investigation_intelligence import plan_investigation

    assert plan_investigation(
        "Explain how to create a VRB rule for a hallway motion sensor."
    ) is None


def test_source_workbench_complete_outweighs_partial_direct_probe():
    """2026-10-17: direct 0..10000 must not mask four verified workbench pages."""
    evidence = [
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "1453", "type": "app", "offset": 0, "length": 10000,
        }, details={
            "sourceRetrieved": True, "offset": 0, "chunkLength": 10000,
            "totalLength": 186457, "sourceCodeId": "1453",
        }),
        receipt("homebrain_read_groovy_source", None, {
            "appId": "1453",
        }, details={
            "sourceRetrieved": False, "fullImplementationVerified": False,
            "verifiedCharacters": 0, "verifiedPages": 0,
        }),
        receipt("homebrain_read_groovy_source", None, {
            "appId": "4019",
        }, details={
            "sourceRetrieved": True, "fullImplementationVerified": True,
            "verifiedCharacters": 186457, "declaredTotalCharacters": 186457,
            "verifiedPages": 4, "sourceCodeId": "1453",
        }),
    ]
    observed = build_observed_agent_outcome(
        outcome(evidence), {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    answer = serialize(apply_shared_investigation_completion(
        observed, "Investigate the complete Groovy source for installed app 4019.",
    ))
    coverage = answer["investigation_coverage"]
    assert coverage["fullImplementationVerified"] is True
    assert coverage["chunkCoverage"] == {
        "fullImplementationVerified": True,
        "coverage": "complete",
        "chunksObserved": 4,
        "verifiedCharacters": 186457,
        "totalLength": 186457,
        "validationMethod": "local-source-workbench",
    }
    assert coverage["directChunkCoverage"]["coverage"] == "partial"
    assert coverage["directChunkCoverage"]["chunksObserved"] == 1
    assert coverage["objectiveSatisfied"] is True
    assert answer["metrics"]["outcome"] == "success"


def test_direct_complete_survives_partial_local_source_workbench():
    evidence = [
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "1099", "type": "app", "offset": 0, "length": 100,
        }, details={"sourceRetrieved": True, "offset": 0, "chunkLength": 100,
                    "totalLength": 200, "sourceCodeId": "1099"}),
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "1099", "type": "app", "offset": 100, "length": 100,
        }, details={"sourceRetrieved": True, "offset": 100, "chunkLength": 100,
                    "totalLength": 200, "sourceCodeId": "1099"}),
        receipt("homebrain_read_groovy_source", None, {"appId": "5551"},
                details={"sourceRetrieved": True, "fullImplementationVerified": False,
                         "verifiedCharacters": 100, "declaredTotalCharacters": 200,
                         "verifiedPages": 1, "sourceCodeId": "1099"}),
    ]
    observed = build_observed_agent_outcome(
        outcome(evidence), {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    answer = serialize(apply_shared_investigation_completion(
        observed, "Inspect complete Groovy source for installed app 5551.",
    ))
    coverage = answer["investigation_coverage"]
    assert coverage["fullImplementationVerified"] is True
    assert coverage["chunkCoverage"]["coverage"] == "complete"
    assert coverage["chunkCoverage"]["chunksObserved"] == 2
    assert coverage["workbenchChunkCoverage"]["coverage"] == "partial"


def test_workbench_full_flag_with_inconsistent_counts_fails_closed():
    evidence = [
        receipt("homebrain_read_groovy_source", None, {"appId": "5551"},
                details={"sourceRetrieved": True, "fullImplementationVerified": True,
                         "verifiedCharacters": 190, "declaredTotalCharacters": 200,
                         "verifiedPages": 2, "sourceCodeId": "1099"}),
    ]
    observed = build_observed_agent_outcome(
        outcome(evidence), {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    answer = serialize(apply_shared_investigation_completion(
        observed, "Inspect the complete Groovy source for installed app 5551.",
    ))
    coverage = answer["investigation_coverage"]
    assert coverage["fullImplementationVerified"] is False
    assert coverage["chunkCoverage"]["coverage"] == "partial"
    assert coverage["objectiveSatisfied"] is False
    assert answer["metrics"]["outcome"] == "unresolved"
