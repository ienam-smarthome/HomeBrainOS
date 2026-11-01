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
    assert "Investigation completeness: partial" not in response["message"]
    assert response["investigation_coverage"]["presentation"] == "technical-only"
    assert any("unchecked source classes" in note for note in response["investigation_coverage"]["limitations"])


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


def test_provisional_comparisons_survive_evidence_safe_final_projection():
    prior = {
        "domain": "device_telemetry",
        "evidenceComplete": False,
        "hypothesisComparisonStatus": "model-proposed-source-checks-not-causal-verdicts",
        "hypothesisComparisons": [
            {
                "candidate": "Endpoint has no power",
                "discriminating_question": "Was a physical packet received?",
                "source_kind": "device_history",
                "source_state": "source-class-checked-verdict-unverified",
                "hypothesis_verdict": "unverified",
            },
            {
                "candidate": "Driver's MQTT status is cached",
                "discriminating_question": "Is the broker reporting a current connection?",
                "source_kind": "app_logs",
                "source_state": "source-class-not-checked",
                "hypothesis_verdict": "unverified",
            },
        ],
    }
    base = outcome([
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "7103", "hoursBack": 24, "limit": 20,
        }, details={"historySourceIntegrityVerified": False}),
    ], coverage=prior)
    observed = build_observed_agent_outcome(base, {
        "outcome": "success", "counters": {}, "timings_ms": {},
    })
    result = serialize(apply_shared_investigation_completion(
        observed, "Independently investigate why this device is offline and "
                  "compare competing explanations. Read-only.",
    ))
    coverage = result["investigation_coverage"]
    assert len(coverage["hypothesisComparisons"]) == 2
    assert coverage["hypothesisComparisonStatus"].startswith("model-proposed")
    assert "Competing explanations (provisional" in result["message"]
    assert "Endpoint has no power" in result["message"]
    assert "Driver's MQTT status is cached" in result["message"]
    assert "hypothesis still unverified" in result["message"]
    assert "relevant source class not checked" in result["message"]
    assert result["metrics"]["outcome"] == "unresolved"


def test_competing_explanations_do_not_appear_without_model_proposal():
    base = outcome(coverage={"domain": "device_telemetry", "evidenceComplete": False})
    observed = build_observed_agent_outcome(base, {
        "outcome": "unresolved", "counters": {}, "timings_ms": {},
    })
    result = serialize(apply_shared_investigation_completion(
        observed, "Why is this device offline?",
    ))
    assert "Competing explanations (provisional" not in result["message"]


def test_final_comparison_preserves_unverified_upstream_packet_proof_boundary():
    prior = {
        "domain": "device_telemetry",
        "evidenceComplete": False,
        "hypothesisComparisonStatus": "model-proposed-source-checks-not-causal-verdicts",
        "hypothesisComparisons": [
            {"candidate": "Endpoint is silent on MQTT",
             "discriminating_question": "Did the broker receive a device packet?",
             "source_kind": "device_logs",
             "required_origin": "upstream",
             "origin_state": "upstream-origin-not-independently-verified",
             "source_state": "source-class-checked-verdict-unverified",
             "hypothesis_verdict": "unverified"},
            {"candidate": "Hubitat driver cached an old status",
             "discriminating_question": "Is device state stale?",
             "source_kind": "device_state",
             "required_origin": "hubitat",
             "source_state": "source-class-checked-verdict-unverified",
             "hypothesis_verdict": "unverified"},
        ],
    }
    observed = build_observed_agent_outcome(
        outcome(coverage=prior),
        {"outcome": "unresolved", "counters": {}, "timings_ms": {}},
    )
    result = serialize(apply_shared_investigation_completion(
        observed, "Compare competing explanations for offline MQTT device. Read-only.",
    ))
    assert "independent upstream evidence has NOT been verified" in result["message"]
    assert "discriminator and hypothesis still unverified" in result["message"]
    assert result["metrics"]["outcome"] == "unresolved"


def test_telemetry_coverage_and_driver_source_do_not_pretend_root_cause_resolved():
    prior = {
        "domain": "device_telemetry",
        "evidenceComplete": True,
        "requirements": [{"key": "status", "state": "observed"}],
    }
    rows = [
        receipt("hub_read_devices", "hub_get_device", {"deviceId": "7103"}),
        receipt("hub_read_devices", "hub_list_device_events", {"deviceId": "7103"}),
        receipt("hub_read_diagnostics", "hub_get_logs", {
            "deviceId": "7103", "limit": 50,
        }, details={"logCount": 20}),
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "3686", "type": "driver",
        }, details={
            "sourceRetrieved": True, "sourceCodeId": "3686",
            "offset": 0, "chunkLength": 20531, "totalLength": 20531,
        }),
    ]
    observed = build_observed_agent_outcome(outcome(rows, coverage=prior), {
        "outcome": "unresolved", "counters": {}, "timings_ms": {},
    })
    answer = serialize(apply_shared_investigation_completion(
        observed,
        "Use paid model. Investigate why the MQTT device is offline and "
        "compare the most plausible causes using MCP evidence. Read-only.",
    ))
    coverage = answer["investigation_coverage"]
    assert coverage["sourceChecksComplete"] is True
    assert coverage["rootCauseVerified"] is False
    assert coverage["questionResolved"] is False
    source = coverage["additionalSourceCodeEvidence"]
    assert source["codeId"] == "3686"
    assert source["fullSourceAtRead"] is True
    assert source["methodBehaviourVerified"] is False
    # Technical provenance stays accessible without displacing the user's
    # diagnosis with source chunk bookkeeping.
    assert "Code ID 3686" not in answer["message"]
    assert "source-offset units" not in answer["message"]
    assert "Investigation depth still missing" not in answer["message"]
    # A source read without a typed mixed-history packet is not enough
    # to associate method-depth diagnostics with this target.
    assert "incidentReasoningDepth" not in coverage
    assert answer["metrics"]["outcome"] == "unresolved"



def test_telemetry_answer_keeps_technical_ledger_out_of_prose_for_any_device():
    from typed_device_history_evidence import render_target_device_evidence_answer

    summary = {
        "deviceId": "9911",
        "deviceLabel": "Anonymised Relay",
        "queryWindowHours": 24,
        "returnedEvents": 2,
        "commandCount": 0,
        "stateEventCount": 2,
        "commandGroups": [],
        "latestReturnedStateEvent": {
            "attribute": "deviceHealth",
            "value": "stale",
            "date": "2026-11-01T12:00:00+00:00",
            "producer": "Anonymised Relay",
        },
        "reportedDeviceState": {
            "observedAt": "2026-11-01T12:00:05+00:00",
            "reportedAttributes": {
                "healthStatus": "offline",
                "mqttStatus": "connected",
                "switch": "off",
            },
        },
        "historicalDataAgeSeconds": None,
        "truncated": False,
    }
    message = render_target_device_evidence_answer([], summary)
    assert "driver/broker connection can remain reported as connected" in message
    assert "not verified driver implementation" in message
    assert "Recorded command sources" not in message
    assert "Command outcomes:" not in message
    assert "No command invocation was returned" in message
    assert "physical command delivery" in message
    assert "deviceHealth=stale" in message
    assert "History integrity:" in message
    assert "not independently verified" in message


def test_telemetry_source_provenance_and_depth_preserved_in_json_not_answer():
    prior = {"domain": "device_telemetry", "evidenceComplete": False}
    rows = [
        receipt("hub_read_devices", "hub_list_devices", {
            "labelFilter": "Anonymised Relay",
        }, details={"reportedDeviceState": {
            "deviceId": "9911", "label": "Anonymised Relay",
            "source": "targeted-hubitat-device-state",
            "observedAt": "2026-11-01T12:00:05+00:00",
            "reportedAttributes": {
                "healthStatus": "offline",
                "mqttStatus": "connected",
            },
        }}),
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "9911", "hoursBack": 24,
        }, details={
            "historySourceIntegrityVerified": False,
            "observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T12:00:00+00:00",
                "producedBy": {
                    "type": "device", "label": "Anonymised Relay",
                    "id": "9911",
                },
            }],
        }),
        receipt("homebrain_device_history", "homebrain_device_history", {
            "name": "Anonymised Relay",
        }, details={
            "label": "Anonymised Relay", "hoursBack": 24,
            "observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T12:00:00+00:00",
                "producedBy": {
                    "type": "device", "label": "Anonymised Relay",
                    "id": "9911",
                },
            }],
            "historySourceIntegrityVerified": False,
        }),
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "9999", "type": "driver",
        }, details={
            "sourceRetrieved": True, "sourceCodeId": "9999",
            "offset": 0, "chunkLength": 1000, "totalLength": 1000,
        }),
    ]
    observed = build_observed_agent_outcome(outcome(rows, coverage=prior), {
        "outcome": "unresolved", "counters": {}, "timings_ms": {},
    })
    result = serialize(apply_shared_investigation_completion(
        observed, "Why is Anonymised Relay MQTT connected but device health offline?",
    ))
    cov = result["investigation_coverage"]
    assert cov["domain"] == "device_telemetry"
    boundary = cov["publicationBoundaryShadow"]
    assert boundary["strategy"] == "typed_target_history"
    assert boundary["replacementPerformed"] is True
    assert boundary["incomingVerifiedRawModelDraft"] is False
    assert boundary["factualQualityMeasured"] is False
    assert boundary["containsAnswerText"] is False
    assert "Observed device state changes" not in str(boundary)
    assert cov["rootCauseVerified"] is False
    assert cov["questionResolved"] is False
    assert cov["additionalSourceCodeEvidence"]["codeId"] == "9999"
    assert cov["additionalSourceCodeEvidence"]["methodBehaviourVerified"] is False
    assert cov["incidentReasoningDepth"]["driverMethodBehaviourVerified"] is False
    assert "Code ID 9999" not in result["message"]
    assert "Investigation depth still missing" not in result["message"]
    assert result["metrics"]["outcome"] == "unresolved"

def test_q1_clock_conflict_printed_once_but_retained_in_technical_coverage():
    """The same clock conflict must not be rendered twice by separate layers."""
    label = "Anonymised Socket"
    state = {
        "deviceId": "9911", "label": label,
        "observedAt": "2026-11-01T18:27:13+00:00",
        "source": "targeted-hubitat-device-state",
        "reportedAttributes": {
            "healthStatus": "offline",
            "mqttStatus": "connected",
            "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
            "dataAgeSeconds": "162325",
        },
    }
    rows = [
        receipt("hub_read_devices", "hub_list_devices", {
            "labelFilter": label, "detailed": True,
        }, details={"reportedDeviceState": state}),
        receipt("hub_read_devices", "hub_list_device_events", {
            "deviceId": "9911", "hoursBack": 24,
        }, details={
            "historySourceIntegrityVerified": False,
            "observedEventsTruncated": False,
            "observedEvents": [{
                "name": "deviceHealth",
                "value": "unknown",
                "date": "2026-11-01T18:23:57+00:00",
                "producedBy": {
                    "id": "9911", "type": "device", "label": label,
                },
            }],
        }),
    ]
    observed = build_observed_agent_outcome(
        outcome(rows, coverage={"domain": "device_telemetry",
                                "evidenceComplete": False}),
        {"outcome": "unresolved", "counters": {}, "timings_ms": {}},
    )
    answer = serialize(apply_shared_investigation_completion(
        observed, "Why is Anonymised Socket MQTT connected but health offline?",
    ))
    message = answer["message"]
    assert message.count("**Telemetry timing conflict:**") == 1
    assert "**Telemetry consistency:**" not in message
    assert message.index("**Working diagnosis:**") < message.index(
        "**Telemetry timing conflict:**"
    )
    assert message.index("**Telemetry timing conflict:**") < message.index(
        "**Latest returned state event:**"
    )
    coverage = answer["investigation_coverage"]
    assert coverage["telemetryClockConsistency"]["sourcesAgree"] is False
    assert coverage["telemetryClockConsistency"]["physicalTelemetryProven"] is False
    assert coverage["normalizedDeviceHistory"]["deviceId"] == "9911"
    assert coverage["rootCauseVerified"] is False
    assert coverage["questionResolved"] is False
    assert answer["metrics"]["outcome"] == "unresolved"


def test_q1_standalone_telemetry_renderer_keeps_clock_safety_guard():
    """Direct callers cannot accidentally lose evidence-limited age warnings."""
    from typed_device_history_evidence import render_target_device_evidence_answer

    summary = {
        "deviceId": "9911", "deviceLabel": "Anonymised Socket",
        "queryWindowHours": 24,
        "returnedEvents": 1, "commandCount": 0, "stateEventCount": 1,
        "commandGroups": [], "truncated": False,
        "latestReturnedStateEvent": {
            "attribute": "deviceHealth", "value": "unknown",
            "date": "2026-11-01T18:23:57+00:00",
            "producer": "Anonymised Socket",
        },
        "reportedDeviceState": {
            "observedAt": "2026-11-01T18:27:13+00:00",
            "reportedAttributes": {
                "healthStatus": "offline", "mqttStatus": "connected",
                "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                "dataAgeSeconds": "162325",
            },
        },
    }
    direct = render_target_device_evidence_answer([], summary)
    assert direct.count("**Telemetry consistency:**") == 1
    assert "Cached telemetry timestamps disagree:" in direct
    reliable = render_target_device_evidence_answer(
        [], summary, clock_check={"sourcesAgree": False,
            "metadataAgeHoursAtRead": 498.0, "reportedDataAgeHours": 45.1},
    )
    assert reliable.count("**Telemetry timing conflict:**") == 1
    assert "**Telemetry consistency:**" not in reliable
    assert "498.0 hours" in reliable
    agreeing = render_target_device_evidence_answer(
        [], summary, clock_check={"sourcesAgree": True},
    )
    assert "**Telemetry timing conflict:**" not in agreeing
    assert "**Telemetry consistency:**" not in agreeing


def test_failed_or_unverified_source_does_not_appear_as_verified_extra_code():
    prior = {"domain": "device_telemetry", "evidenceComplete": False}
    rows = [
        receipt("hub_read_apps_code", "hub_get_source", {
            "id": "3686", "type": "driver",
        }, details={
            "sourceRetrieved": False, "sourceCodeId": "3686",
            "offset": 0, "chunkLength": 999, "totalLength": 20531,
        }),
    ]
    observed = build_observed_agent_outcome(outcome(rows, coverage=prior), {
        "outcome": "unresolved", "counters": {}, "timings_ms": {},
    })
    answer = serialize(apply_shared_investigation_completion(
        observed, "Investigate why a device reports offline.",
    ))
    assert "additionalSourceCodeEvidence" not in answer["investigation_coverage"]
