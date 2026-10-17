"""v0.18.24: do not fabricate an old automation command from truncated history."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from historical_causal_claim_guard import (
    assess_historical_claims, render_unverified_claim_warning,
)
from shared_investigation_completion import apply_shared_investigation_completion
from api_response_builder import build_agent_response


QUESTION = (
    "Investigate why Bedroom 3 Mesh (device 7103) is offline while "
    "MQTT reports connected. Verify Groovy driver source code 3686 and "
    "correlate with device history and logs, read-only."
)
MODEL_INVENTION = (
    "Best candidate (high confidence): The device stopped publishing after "
    "Power saving: Bedroom 3 Mesh off @night (appId 3950) issued an off() "
    "command at 01:30:01 on Oct 12. "
    "Device acknowledged: switch=off at 01:30:01. "
    "The watchdog then caused healthStatus=offline. "
    "Driver source code was not retrieved this turn."
)


def receipt(leaf, args, details):
    return {
        "tool": ("hub_read_apps_code" if leaf == "hub_get_source"
                 else "hub_read_diagnostics" if leaf == "hub_get_logs"
                 else "hub_read_devices"),
        "sub_tool": leaf, "arguments": {"tool": leaf, "args": args},
        "success": True, "mutates": False, "effect": "read",
        "details": details,
    }


def event(date="2026-10-17T14:58:59+01:00", app_id=3103, command="on"):
    return {
        "name": "command-"+command, "description": "Command called: "+command+"()",
        "type": "command", "date": date,
        "producedBy": {"name": "Room Button", "appId": app_id, "type": "app"},
    }


def live_receipts(older_command=False):
    events = [
        {"name":"deviceHealth","value":"stale",
         "date":"2026-10-17T16:39:50+01:00",
         "producedBy":{"deviceId":"7103", "type":"device"}},
        event(),
    ]
    if older_command:
        events.append(event("2026-10-12T01:30:01+01:00",3950,"off"))
    return [
        receipt("hub_get_source", {"id": 3686, "type":"driver"},
                {"sourceRetrieved":True, "sourceCodeId":"3686",
                 "offset":0,"chunkLength":20531,"totalLength":20531}),
        receipt("hub_get_device", {"deviceId":7103,"mode":"summary"}, {}),
        receipt("hub_list_device_events", {"deviceId":7103,"hoursBack":168},
                {"observedEvents":events, "observedEventsTruncated":True}),
        receipt("hub_get_logs", {"deviceId":7103,"since":"24h"},
                {"logCount":43,"logs":[{"date":"2026-10-17 16:35:59",
                 "level":"WARN",
                 "message":"Watchdog fired after 7869s without data"}]}),
    ]


def response(msg, receipts):
    return SimpleNamespace(
        message=msg, evidence=receipts, route="unified-mcp-agent",
        request_class="live-read",
        metrics={"outcome":"success","counters":{},"timings_ms":{},
                 "model_round_details":[{"model":"deepseek-v4-pro",
                                          "provider":"ollama-cloud"}]},
        investigation_coverage=None,
        choices=[], confirmation_required=False, confirmation_count=0,
        automation_items=[],
    )


def test_truncated_seven_day_history_does_not_verify_an_october_12_command():
    evidence = live_receipts()
    assessment = assess_historical_claims(MODEL_INVENTION, evidence)
    assert assessment["unverifiedCommandActors"] == ["3950"]
    assert assessment["historyTruncated"] is True
    assert assessment["sourceReadContradicted"] is True
    assert not assessment["historicalActionVerified"]
    note=render_unverified_claim_warning(assessment, evidence)
    assert "source code ID 3686" in note
    assert "event-history projection was truncated" in note
    assert "This does not prove those automations never ran" in note


def test_live_completed_reads_and_synthesis_still_unresolved_when_history_invented():
    result = apply_shared_investigation_completion(
        response(MODEL_INVENTION, live_receipts()), QUESTION,
    )
    meta = result.investigation_coverage
    assert meta["fullImplementationVerified"] is True
    assert meta["runtimeEvidence"]["satisfied"] is True
    assert meta["historicalCausalClaim"]["unverifiedCommandActors"] == ["3950"]
    assert meta["objectiveSatisfied"] is False
    assert meta["questionResolved"] is False
    assert meta["analysisAnswerVerified"] is False
    assert result.metrics["outcome"] == "unresolved"
    assert "Best candidate (high confidence)" not in result.message
    assert "historical command or automation execution" in result.message
    api = build_agent_response(
        result,model="deepseek-v4-pro",elapsed_ms=410029,version="0.18.24",
    )
    assert api["success"] is False
    assert api["outcome_presentation"]["value"] == "unresolved"
    assert api["model_usage"]["paid_rounds"] == 1
    assert api["investigation_coverage"]["fullImplementationVerified"] is True


def test_matching_event_provides_actor_command_support():
    evidence=live_receipts(older_command=True)
    assessment=assess_historical_claims(MODEL_INVENTION,evidence)
    assert assessment["unverifiedCommandActors"] == []
    assert assessment["historicalActionVerified"] is True


def test_app_config_and_source_id_cannot_replace_command_history():
    evidence=live_receipts()
    evidence.append(receipt("hub_get_app_config",{"appId":3950},
                            {"appId":3950, "enabled":True}))
    assessment=assess_historical_claims(MODEL_INVENTION,evidence)
    assert assessment["unverifiedCommandActors"] == ["3950"]


def test_event_from_wrong_date_does_not_prove_specific_october_12_action():
    rows=live_receipts()
    rows[2]["details"]["observedEvents"].append(
        event("2026-10-17T01:30:01+01:00",3950,"off")
    )
    assert assess_historical_claims(MODEL_INVENTION,rows)[
        "unverifiedCommandActors"
    ] == ["3950"]


def test_hypothesis_or_negation_is_not_execution_assertion():
    rows=live_receipts()
    cautious = (
        "The configuration names Power saving app 3950; it is unknown "
        "whether any off() command occurred on October 12."
    )
    # This conservative guard may still flag an app ID near a command word:
    # that is an unresolved claim, never proof that a command was sent.
    outcome=assess_historical_claims(cautious,rows)
    assert outcome["historicalActionVerified"] is False
    unrelated = "The source code for app 3950 defines an initialize() method."
    assert assess_historical_claims(unrelated,rows)["historicalActionVerified"] is True


def test_other_proven_history_does_not_support_named_app_attribution():
    rows=live_receipts()
    rows[2]["details"]["observedEvents"].append(
        event("2026-10-12T01:30:01+01:00",3103,"off")
    )
    assert assess_historical_claims(MODEL_INVENTION,rows)[
        "unverifiedCommandActors"
    ] == ["3950"]
