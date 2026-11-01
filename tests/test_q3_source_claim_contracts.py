"""Q3 source-contract invariants across telemetry and historical command witnesses.

These tests are offline negative controls, NOT factual accuracy scores and
NOT authority to turn on the command/lighting/heating publication path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from source_claim_contract import SCHEMA, admit_source_claim_plan
from proof_carrying_answer import admit_model_claim_plan
from recorded_command_claim_contract import (
    attested_recorded_command_claims, admit_recorded_command_plan,
)


REQUEST = "Why did device ID 9911 turn OFF at 1 November 2026 20:00 GMT?"


def plan(*claim_ids: str) -> str:
    return json.dumps({"schema": SCHEMA, "claim_ids": list(claim_ids)})


def receipt(
    device_id="9911", app_id="4012", when="2026-11-01T20:00:10+00:00",
    name="command-off", effect="read",
):
    return {
        "success": True, "effect": effect, "mutates": False,
        "sub_tool": "hub_list_device_events",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": device_id, "hoursBack": 24}},
        "details": {"observedEvents": [{
            "name": name, "type": "command", "date": when,
            "producedBy": {"appId": app_id, "name": "Synthetic Controller"},
        }]},
    }


def test_generic_plan_accepts_only_host_source_facts_and_requires_caveats():
    facts = {
        "command": "An app issued a command.",
        "limitations": "No physical confirmation exists.",
        "next_check": "Inspect a bounded device acknowledgement.",
    }
    accepted, reason = admit_source_claim_plan(
        plan("command", "limitations", "next_check"),
        facts, {"command", "limitations", "next_check"},
    )
    assert reason == "source-claim-plan-admitted"
    assert accepted == "\n\n".join(facts.values())
    for bad in (
        plan("command", "limitations", "made_up"),
        plan("command", "command", "limitations"),
        plan("command", "limitations", "next_check") + "\nThe actuator moved.",
        json.dumps({"schema": SCHEMA, "claim_ids": ["command", "limitations",
                                                    "next_check"],
                    "model_prose": "It definitely happened."}),
        plan("command", "limitations"),
    ):
        output, why = admit_source_claim_plan(
            bad, facts, {"command", "limitations", "next_check"},
        )
        assert output is None and why != "source-claim-plan-admitted"
    assert admit_source_claim_plan(
        plan("command", "limitations", "next_check"),
        facts, {"missing_requirement"},
    )[0] is None


def test_recorded_command_witness_is_issuer_only_not_caused_or_executed():
    facts = attested_recorded_command_claims(REQUEST, [receipt()])
    assert set(facts) == {
        "recorded_command", "upstream_unknown", "execution_unknown",
    }
    answer, reason = admit_recorded_command_plan(
        plan("recorded_command", "upstream_unknown", "execution_unknown"),
        REQUEST, [receipt()],
    )
    assert reason == "source-claim-plan-admitted"
    assert "app 4012" in answer
    assert "device 9911" in answer
    assert "does not independently establish delivery" in answer
    assert "does not establish what triggered the app" in answer
    assert "Synthetic Controller" not in answer


def test_command_witness_never_substitutes_non_target_or_outside_window():
    for r in (
        receipt(device_id="9999"),
        receipt(when="2026-11-01T22:00:10+00:00"),
        receipt(name="switch"),
        receipt(effect="write"),
    ):
        assert attested_recorded_command_claims(REQUEST, [r]) == {}
    assert not attested_recorded_command_claims(
        "Why did a light turn OFF at 1 November 2026 20:00 GMT?", [receipt()],
    )
    assert not attested_recorded_command_claims(
        REQUEST, [receipt(), receipt(app_id="4013")],
    )
    assert not attested_recorded_command_claims(
        "Why did device ID 9911 and device ID 9912 turn OFF "
        "at 1 November 2026 20:00 GMT?", [receipt()],
    )


def test_cross_domain_adapter_does_not_infer_physical_cause():
    facts = attested_recorded_command_claims(REQUEST, [receipt()])
    assert not admit_recorded_command_plan(
        plan("recorded_command", "upstream_unknown", "physical_execution_proven"),
        REQUEST, [receipt()],
    )[0]
    assert admit_recorded_command_plan(
        plan("recorded_command", "upstream_unknown", "execution_unknown"),
        REQUEST, [receipt(name="switch")],
    ) == (None, "no-source-claims")
    assert not admit_recorded_command_plan(
        plan("recorded_command", "upstream_unknown", "execution_unknown"),
        REQUEST, [receipt(device_id="9999")],
    )[0]


def test_telemetry_adapter_cannot_claim_every_device_is_offline():
    normalized = {
        "deviceId": "9911", "deviceLabel": "Test Relay",
        "reportedDeviceState": {
            "deviceId": "9911",
            "source": "targeted-hubitat-device-state",
            "isPhysicalConnectivityProof": False,
            "reportedAttributes": {"healthStatus": "online"},
        },
        "returnedEvents": 1, "stateEventCount": 1,
        "commandCount": 0, "truncated": False,
        "eventHistoryComplete": False,
    }
    output, reason = admit_model_claim_plan(
        plan("reported_health", "cause_unverified", "next_readonly"),
        normalized, {"rootCauseVerified": False},
    )
    assert reason == "source-claim-plan-admitted"
    assert "healthStatus=online" in output
    assert "stored health state is offline" not in output
    assert "physical endpoint" in output
