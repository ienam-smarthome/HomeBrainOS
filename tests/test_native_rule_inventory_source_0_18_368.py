"""Rule Machine parent + dated one-off inventory is NOT an action-tree audit.

Synthetic Hubitat inventory responses, no network, no model/tool writes.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from native_rule_inventory_source import (  # noqa: E402
    is_native_rule_inventory_question, project_rule_inventory, render_inventory,
    read_native_rule_inventory,
)

QUESTION = (
    "Read-only native Rule Machine investigation: use hub_list_apps and "
    "hub_list_rules to identify installed native Rule Machine parent and "
    "find existing rules whose names end with (One-time YYYY-MM-DD HH:MM). "
    "Report exact names/IDs. Do not create, update or execute rules."
)

INST = {
    "apps": [
        {"id": 21, "name": "Rule Machine", "type": "Rule Machine",
         "appTypeId": 90, "parentId": None},
        {"id": 72, "name": "Sample Internet OFF (One-time 2026-11-01 18:30)",
         "type": "Rule-5.1", "appTypeId": 91, "parentId": 21},
        {"id": 73, "name": "Other recurring rule", "type": "Rule-5.1",
         "appTypeId": 91, "parentId": 21},
    ],
    "count": 3, "totalOnHub": 3, "filter": "all",
}
TYPES = {
    "apps": [
        {"id": 90, "name": "Rule Machine", "namespace": "hubitat"},
        {"id": 91, "name": "Rule-5.1", "namespace": "hubitat"},
    ],
    "count": 2,
}
RULES = {
    "rules": [
        {"id": 72, "name": "Sample Internet OFF (One-time 2026-11-01 18:30)"},
        {"id": 73, "name": "Other recurring rule"},
    ],
    "count": 2,
}


@pytest.mark.parametrize("q,expect", [
    (QUESTION, True),
    ("List my one-off Rule Machine rules and their IDs", True),
    ("Identify Rule Machine parent app ID from installed app listing", True),
    ("Identify the installed native Rule Machine parent app and find existing "
     "one-time Rule Machine rules using read-only app/rule inventory. "
     "Report the parent ID, source-verified type and namespace, or explain "
     "why identity remains unverified. Report any incomplete source coverage. "
     "Do not create, execute, modify, pause or delete anything.", True),
    ("Find existing Rule Machine rules and explain why parent namespace is unverified", True),
    ("List one-time Rule Machine rules and report why source identity is missing", True),
    ("Find Rule Machine rules and explain why the rule turned OFF", False),
    ("Find Rule Machine rules and explain why it failed to execute", False),
    ("List Rule Machine rules and what triggered them", False),
    ("What triggered Rule Machine rule 4136 to turn off yesterday?", False),
    ("Read-only: explain nested IF and delay cancellation of rule 4136", False),
    ("Please turn off internet for this device", False),
    ("What are my current temperatures?", False),
])
def test_inventory_objective_has_distinct_scope(q, expect):
    assert is_native_rule_inventory_question(q) is expect


def test_parent_join_and_dated_rule_matches_are_source_typed():
    src = copy.deepcopy((INST, TYPES, RULES))
    data = project_rule_inventory(*src)
    assert src == (INST, TYPES, RULES)
    assert data["parents"] == [{
        "appId": "21", "appTypeId": "90",
        "namespace": "hubitat", "name": "Rule Machine",
    }]
    assert data["oneTimeRules"] == [{
        "appId": "72", "name": RULES["rules"][0]["name"],
        "sourceKinds": ["hub_list_rules", "hub_list_apps"], "parentId": "21",
    }]
    assert data["oneTimeMatchCount"] == 1
    assert data["ruleListComplete"] is True
    assert "ID **21**" in render_inventory(data)
    assert "ID 72" in render_inventory(data)
    assert "rule ran" not in render_inventory(data).lower()


def test_names_or_matching_child_counts_do_not_prove_native_parent():
    user_types = copy.deepcopy(TYPES)
    user_types["apps"][0]["namespace"] = "user"
    p = project_rule_inventory(INST, user_types, RULES)
    assert p["parents"] == []
    assert p["candidateParents"] == [{
        "appId": "21", "appTypeId": "90", "typeProof": "unverified",
        "typeProofGap": "no-matching-native-app-type-id",
    }]
    assert "native parent ID remains unresolved" in render_inventory(p)

    wrong_class = copy.deepcopy(INST)
    wrong_class["apps"][0]["appTypeId"] = 999
    p2 = project_rule_inventory(wrong_class, TYPES, RULES)
    assert p2["parents"] == []


def test_missing_or_truncated_inventory_cannot_prove_no_matches():
    p = project_rule_inventory(INST, TYPES, {"rules": [], "count": 0,
                                             "nextCursor": "more"})
    # Existing app-list match still counts as observed, but page isn't complete.
    assert p["oneTimeMatchCount"] == 1
    assert p["ruleListComplete"] is False
    assert "Not all rules" in render_inventory(p)

    without = copy.deepcopy(INST)
    without["apps"] = without["apps"][:1]
    without["count"] = 1
    without["totalOnHub"] = 3
    p2 = project_rule_inventory(without, TYPES,
                                {"rules": [], "count": 0, "nextCursor": "more"})
    assert p2["oneTimeMatchCount"] == 0
    assert "do not establish absence" in render_inventory(p2)


def test_exact_suffix_required_not_loose_one_time_name():
    r = {"rules": [
        {"id": 40, "name": "One-time 2026-11-01 18:30"},
        {"id": 41, "name": "Example (One-time 2026-11-01 18:30)"},
    ], "count": 2}
    p = project_rule_inventory({"apps": [], "count": 0, "totalOnHub": 0},
                               TYPES, r)
    assert [x["appId"] for x in p["oneTimeRules"]] == ["41"]


class FakeMCP:
    def __init__(self, *, missing_type=False, flat_summary=False):
        self.calls = []
        self.missing_type = missing_type
        self.flat_summary = flat_summary

    async def list_tools(self):
        return [
            MCPTool("hub_read_apps_code", "Apps", {"type": "object"}),
            MCPTool("hub_read_rules", "Rules", {"type": "object"}),
            MCPTool("hub_manage_native_rules_and_apps", "Write", {"type": "object"}),
        ]

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        assert gateway in {
            "hub_read_apps_code", "hub_read_rules",
            "hub_manage_native_rules_and_apps",
        }
        subtool = args.get("tool")
        if gateway == "hub_manage_native_rules_and_apps":
            assert subtool == "hub_set_rule"
            assert args["args"] == {"operation": "read", "rule_id": 72}
            data = {
                "rule_id": 72,
                "validation": {"structuralIssues": [], "uiChecked": False},
                "nativeHealth": {"broken": False, "stopped": False},
                "triggers": {"1": "When time is 6:30 PM on November 1"},
                "actions": [{
                    "id": "1", "value": {"method": "getOnOffSwitch"},
                }],
                "conditions": {}, "expressions": {},
                "settings": [
                    {"name": "tCapab1", "type": "enum",
                     "value": "Certain Time (and optional date)"},
                    {"name": "atTime1", "type": "time",
                     "value": "2026-11-01T18:30:00"},
                    {"name": "actType.1", "type": "enum",
                     "value": "switchActs"},
                    {"name": "onOff.1", "type": "bool", "value": "false"},
                    {"name": "onOffSwitch.1", "type": "capability.switch",
                     "device_ids": ["99"]},
                ],
            }
        elif subtool == "hub_list_rules":
            data = RULES
        elif subtool == "hub_get_app_config":
            assert args["args"] == {"appId": "21", "summary": True}
            data = {
                "success": True, "id": 21, "type": "Rule Machine",
                "user": False, "appTypeId": 90, "parentId": None,
                **({"namespace": "hubitat"} if self.flat_summary else {}),
            }
        elif args["args"]["scope"] == "instances":
            data = INST
        else:
            data = {} if self.missing_type else TYPES
        return MCPToolResult(gateway, args, {}, "", data)


class NeverAskModel:
    async def chat(self, *args, **kwargs):
        raise AssertionError("Inventory source queries must not cost model rounds")


@pytest.mark.asyncio
async def test_three_bounded_read_calls_produce_typed_evidence():
    mcp = FakeMCP()
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        report, projection = await read_native_rule_inventory(
            mcp, recorder, available_names={
                "hub_read_apps_code", "hub_read_rules",
                "hub_manage_native_rules_and_apps",
            })
        assert len(mcp.calls) == 3
        assert [x[1]["tool"] for x in mcp.calls] == [
            "hub_list_apps", "hub_list_apps", "hub_list_rules",
        ]
        assert projection["parents"][0]["appId"] == "21"
        assert "ID 72" in report
        receipts = recorder.receipts()
        assert receipts[-1]["evidence_kind"] == "typed_native_rule_inventory"
        assert receipts[-1]["details"]["parents"][0]["appId"] == "21"
        assert all(not row["mutates"] and row["effect"] == "read"
                   for row in receipts)
    finally:
        recorder.reset(token)


@pytest.mark.asyncio
async def test_orchestrator_returns_inventory_not_generic_deep_rule_refusal():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b",
                            ai_client=NeverAskModel())
    result = await agent.process_user_request_result(
        QUESTION, session_id="inventory-parent-source"
    )
    assert result.request_class == "live-read"
    assert not result.confirmation_required
    assert result.confirmation_count == 0
    assert "ID **21**" in result.message
    assert "ID 72" in result.message
    assert "comparison controller" not in result.message
    assert "complete executable action tree" not in result.message
    assert result.investigation_coverage is None
    assert len(mcp.calls) == 4
    assert mcp.calls[-1][1] == {
        "tool": "hub_set_rule",
        "args": {"operation": "read", "rule_id": 72},
    }
    assert "6:30 PM" in result.message
    assert all(not row.get("mutates") for row in result.evidence)
    assert all(row.get("effect") == "read" for row in result.evidence)
    assert all(not (x[1].get("tool") == "hub_set_rule"
                    and x[1]["args"]["operation"] != "read")
               for x in mcp.calls)


@pytest.mark.asyncio
async def test_source_scope_explanation_routes_to_typed_inventory_not_groovy_or_model():
    """A bounded identity-coverage explanation is not a rule-execution audit."""
    question = (
        "Identify the installed native Rule Machine parent app and find existing "
        "one-time Rule Machine rules using read-only app/rule inventory. "
        "Report the parent ID, source-verified type and namespace, or explain "
        "why identity remains unverified. Report any incomplete source coverage. "
        "Do not create, execute, modify, pause or delete anything."
    )
    mcp = FakeMCP(missing_type=True, flat_summary=True)
    agent = UnifiedMCPAgent(
        mcp, "test-key", "gemma4:31b", ai_client=NeverAskModel(),
    )
    result = await agent.process_user_request_result(
        question, session_id="native-inventory-source-coverage",
    )
    assert result.request_class == "live-read"
    assert not result.confirmation_required
    assert "ID **21**" in result.message
    assert "namespace **hubitat**" in result.message
    assert "ID 72" in result.message
    assert "Other recurring rule" not in result.message
    assert "one-time" in result.message.lower()
    assert not any("source code" in x["summary"].lower() for x in result.evidence)
    assert [x[1]["tool"] for x in mcp.calls] == [
        "hub_list_apps", "hub_list_apps", "hub_list_rules",
        "hub_get_app_config", "hub_set_rule",
    ]
    assert mcp.calls[3][1]["args"] == {"appId": "21", "summary": True}
    assert mcp.calls[4][1]["args"]["operation"] == "read"
    assert all(row["effect"] == "read" and row["mutates"] is False
               for row in result.evidence)


@pytest.mark.asyncio
async def test_orchestrator_can_report_unverified_parent_without_fabricating_id():
    mcp = FakeMCP(missing_type=True)
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b",
                            ai_client=NeverAskModel())
    result = await agent.process_user_request_result(
        QUESTION, session_id="inventory-unverified-type"
    )
    assert "native parent ID remains unresolved" in result.message
    assert "ID **21**" not in result.message
    assert result.confirmation_count == 0


def test_live_20261103_parent_class_gap_remains_unresolved_even_with_complete_lists():
    """Real receipt shape, synthetic minimal rows; no source payload guessed.

    App candidate 169 refers to appTypeId 18, but the returned type list had
    no matching native class and the thin summary omitted appType namespace.
    Inventory completeness does not certify the missing type join.
    """
    instances = {
        "apps": [{"id": 169, "name": "Rule Machine",
                  "type": "Rule Machine", "appTypeId": 18,
                  "parentId": None, "user": False, "hasChildren": True}],
        "count": 1, "totalOnHub": 1, "filter": "all",
    }
    types = {"apps": [{"id": 19, "name": "Rule Machine Legacy",
                         "namespace": "hubitat", "system": True,
                         "isBuiltIn": True}], "count": 1}
    rules = {"rules": [], "count": 0}
    summary = {
        "success": True,
        "app": {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
                "user": False, "appTypeId": 18, "parentId": None},
    }
    projected = project_rule_inventory(
        instances, types, rules, summaries={"169": summary},
    )
    assert projected["parents"] == []
    assert projected["candidateParents"] == [{
        "appId": "169", "appTypeId": "18", "typeProof": "unverified",
        "typeProofGap": "no-matching-native-app-type-id",
    }]
    assert projected["summarySourceChecks"] == [{
        "appId": "169",
        "typeProofGap": "native-app-summary-class-namespace-unavailable",
    }]
    assert projected["ruleListComplete"] is True
    assert projected["appListComplete"] is True
    assert projected["typesListComplete"] is True
    assert projected["parentIdentityComplete"] is False
    assert projected["nativeRuleMachineTypeIds"] == []
    assert "parent ID remains unresolved" in render_inventory(projected)
    # A dated-rule suffix scan does not check for the offline delay writer's
    # unique label, and this inventory route did not read owned devices.
    assert projected["oneTimeMatchCount"] == 0
    assert "ownedDevices" not in projected


def test_same_class_id_from_community_type_is_not_native_parent_proof():
    instances = {
        "apps": [{"id": 169, "name": "Rule Machine",
                  "type": "Rule Machine", "appTypeId": 18,
                  "parentId": None, "user": False}],
        "count": 1, "totalOnHub": 1, "filter": "all",
    }
    types = {
        "apps": [{"id": 18, "name": "Rule Machine",
                  "namespace": "community", "system": False,
                  "isBuiltIn": False}], "count": 1,
    }
    proj = project_rule_inventory(instances, types,
                                  {"rules": [], "count": 0})
    assert proj["parents"] == []
    assert proj["parentIdentityComplete"] is False
