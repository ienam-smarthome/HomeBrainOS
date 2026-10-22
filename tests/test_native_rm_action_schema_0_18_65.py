"""v0.18.65 live native RM proposal regression: canonical actions and safe timer."""
from __future__ import annotations
import copy
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from tool_registry import normalize_rule_machine_proposal, rule_machine_proposal_error

GATEWAY = "hub_manage_rule_machine"
START = {"type": "clock", "time": "23:00"}
END = {"type": "clock", "time": "06:00"}


def expr():
    return {"operator": "AND", "conditions": [
        {"capability": "Motion", "deviceIds": ["7978"], "state": "inactive"},
        {"capability": "Switch", "deviceIds": ["7805"], "state": "on"},
        {"capability": "Between two times", "start": START, "end": END},
    ]}


def triggers():
    return [
        {"capability": "Motion", "deviceIds": ["7978"], "state": "inactive"},
        {"capability": "Switch", "deviceIds": ["7805"], "state": "on"},
        {"capability": "Certain Time (and optional date)", "time": "A specific time", "atTime": "23:00"},
        {"capability": "Motion", "deviceIds": ["7978"], "state": "active"},
        {"capability": "Certain Time (and optional date)", "time": "A specific time", "atTime": "06:00"},
        {"capability": "Switch", "deviceIds": ["7805"], "state": "off"},
    ]


def valid():
    return {
        "tool": "hub_set_rule",
        "args": {"name": "Livingroom Light 1 - Night Idle OFF - TEST",
                 "addTriggers": triggers(),
                 "addActions": [
                     {"capability": "cancelDelay"},
                     {"capability": "ifThen", "expression": expr()},
                     {"capability": "delay", "minutes": 10, "cancelable": True},
                     {"capability": "ifThen", "expression": expr()},
                     {"capability": "switch", "action": "off", "deviceIds": ["7805"]},
                     {"capability": "endIf"}, {"capability": "endIf"},
                 ]}
    }


def test_exact_live_wrapper_syntax_is_canonicalized_not_reinterpreted():
    wrapped = valid()
    actions = wrapped["args"]["addActions"]
    for index in (1, 2, 3, 5, 6):
        row = actions[index]
        capability = row.pop("capability")
        if capability == "delay":
            row = {"delay": {"minutes": 10}, "cancelable": True}
        else:
            row = {capability: row}
        actions[index] = row
    actions[0] = {"cancelDelay": {}}
    before = copy.deepcopy(wrapped)
    result = normalize_rule_machine_proposal(GATEWAY, wrapped)
    assert result != before
    assert result["args"]["addActions"] == valid()["args"]["addActions"]
    assert rule_machine_proposal_error(GATEWAY, result) is None
    assert before["args"]["addActions"][0] == {"cancelDelay": {}}


def test_live_payload_wrong_condition_is_rejected_after_syntax_repair():
    malformed = valid()
    malformed["args"]["addActions"][0] = {"ifThen": {"expression": expr()}}
    malformed["args"]["addActions"][1] = {"delay": {"minutes": 10}, "cancelable": True}
    malformed["args"]["addActions"][2] = {"ifThen": {"expression": {
        "operator": "OR", "conditions": [
            {"capability": "Motion", "deviceIds": ["7978"], "state": "active"},
            {"capability": "Certain Time (and optional date)", "time": "A specific time", "atTime": "06:00"},
        ]}}}
    normalized = normalize_rule_machine_proposal(GATEWAY, malformed)
    assert normalized["args"]["addActions"][0]["capability"] == "ifThen"
    reason = rule_machine_proposal_error(GATEWAY, normalized)
    assert "condition 2 uses a time TRIGGER" in reason


def test_valid_bounded_night_timer_with_final_guard_passes_structural_validation():
    assert rule_machine_proposal_error(GATEWAY, valid()) is None
    assert rule_machine_proposal_error(
        GATEWAY, valid(),
        user_prompt="Create this night light rule, turn it OFF after 10 minutes",
    ) is None


def test_multiple_boundaries_require_guarded_cancel_sequence():
    values = valid()
    values["args"]["addActions"][0] = {"capability": "comment", "text": "bad"}
    assert "multiple daily times" in rule_machine_proposal_error(GATEWAY, values)
    values = valid()
    values["args"]["addActions"][3]["expression"]["conditions"][0]["state"] = "active"
    assert "multiple daily times" in rule_machine_proposal_error(GATEWAY, values)


def test_wrong_motion_target_and_missing_light_off_cannot_pass():
    values = valid()
    values["args"]["addTriggers"][0]["deviceIds"] = ["7764"]
    assert "multiple daily times" in rule_machine_proposal_error(GATEWAY, values)
    values = valid()
    values["args"]["addTriggers"] = values["args"]["addTriggers"][:-1]
    assert "multiple daily times" in rule_machine_proposal_error(GATEWAY, values)


def test_if_blocks_must_balance_and_conditions_cannot_embed_time_triggers():
    values = valid()
    values["args"]["addActions"] = values["args"]["addActions"][:-1]
    assert "missing endIf" in rule_machine_proposal_error(GATEWAY, values)
    values = valid()
    values["args"]["addActions"][1]["expression"]["conditions"][2] = {
        "capability": "Certain Time (and optional date)", "atTime": "23:00"
    }
    assert "time TRIGGER" in rule_machine_proposal_error(GATEWAY, values)


def test_unknown_wrapper_is_not_silently_transformed():
    value = {"tool": "hub_set_rule", "args": {
        "name": "Test", "addActions": [{"fantasyAction": {"x": 1}}]
    }}
    assert normalize_rule_machine_proposal(GATEWAY, value) == value
    assert "action 1 requires capability" in rule_machine_proposal_error(GATEWAY, value)


def test_model_payload_never_reflected_in_failed_rule_error():
    code = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "Rejected payload:" not in code
    assert "proposal validation failed twice" in code
    assert "not reflected back as" in code
