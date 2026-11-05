"""0.18.418: source-attested native parent and date-contract preflight.

Synthetic MCP fixtures only. The source guide contains a deliberately secret
acknowledgement token that must never enter public evidence or final text.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder
from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent
from native_rule_readiness_source import (
    is_native_rule_readiness_question, _extra_requested_checks,
    _guide_contract_projection, _native_parent_projection,
    native_rule_readiness_coverage, read_native_rule_readiness,
)

QUESTION = (
    "Perform a READ-ONLY native Rule Machine one-time scheduling preflight. "
    "Verify the installed MCP Rule Server version. "
    "Verify that app 169 is the correct native Rule Machine parent using its "
    "app identity and built-in app-type relationship. "
    "Read the native hub_set_rule tool guide. "
    "Determine whether the installed MCP Server supports creating a Rule Machine "
    "rule with a Certain Time (and optional date) trigger. "
    "Identify the documented date format, required typed trigger fields, "
    "parent ID requirements and supported creation operations. "
    "Do not create, modify, execute or delete rules, open editor forms or "
    "change devices. Keep native rule-writing authorisation disabled. "
    "Include Technical JSON."
)

SECRET = "PRIVATE-TOKEN-DO-NOT-PUBLISH"
GUIDE = (
    "I-HAVE-READ-THE-GUIDE-set_rule_reference-a12f109e\n"
    + SECRET + "\n"
    + "hub_set_rule operation=create accepts parent_id for Rule Machine.\n"
    + "Certain Time (and optional date) trigger:\n"
    + "time# type=enum\n"
    + "atTime# type=time\n"
    + "date# type=bool\n"
    + "atDate# type=date yyyy-MM-dd\n"
)

INST = {"apps": [
    {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
     "user": False, "appTypeId": 18, "parentId": None},
    {"id": 777, "name": SECRET, "type": "Rule-5.1", "parentId": 169},
], "count": 2, "totalOnHub": 2}
TYPES = {"apps": [
    {"id": 18, "name": "Rule Machine", "system": True,
     "isBuiltIn": True},
], "count": 1}
SUMMARY = {"success": True, "id": 169, "type": "Rule Machine",
           "name": "Rule Machine", "namespace": "hubitat",
           "appTypeId": 18, "user": False}
CONFIG = {"success": True, "app": {"id": 169, "parentAppId": None},
          "childApps": [{"id": 2020, "name": SECRET}]}


class SourceOnly:
    def __init__(self, *, guide=GUIDE, typ=TYPES, summary=SUMMARY,
                 config=CONFIG, instances=INST):
        self.calls = []
        self.server_info = {"name": "hubitat-mcp-rule-server",
                            "version": "5.1.6"}
        self.guide, self.types = guide, typ
        self.summary, self.config, self.instances = summary, config, instances

    async def list_tools(self):
        return [
            MCPTool("hub_read_apps_code", "read only", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "read only", {"type": "object"}),
        ]

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        assert gateway in {"hub_read_apps_code", "hub_get_tool_guide"}
        if gateway == "hub_get_tool_guide":
            sec = arguments["section"]
            assert sec in {"set_rule_reference", "builtin_app_tools_rules"}
            content = (self.guide if sec == "set_rule_reference" else
                       "I-HAVE-READ-THE-GUIDE-builtin_app_tools_rules-a12f109e")
            data = {"success": True, "content": content}
        else:
            tool = arguments["tool"]
            args = arguments["args"]
            if tool == "hub_list_backups":
                assert args == {"scope": "hub_local"}
                data = {"scope": "hub_local", "hubLocalBackups": [
                    {"createTimeOrig": "2026-11-05T03:02:31+00:00"}
                ]}
            elif tool == "hub_list_apps":
                assert args["scope"] in {"instances", "types"}
                data = (self.instances if args["scope"] == "instances"
                        else self.types)
            elif tool == "hub_get_app_config":
                assert str(args["appId"]) == "169"
                data = (self.summary if args.get("summary") is True
                        else self.config)
            else:
                raise AssertionError("Unexpected source tool: " + tool)
        return MCPToolResult(gateway, arguments, {}, "", data)


class NeverModel:
    async def chat(self, *args, **kwargs):
        raise AssertionError("Preflight must not call an AI model")


def _run(source, question=QUESTION):
    recorder = EvidenceRecorder()
    token = recorder.begin()
    import asyncio
    try:
        message, details = asyncio.run(read_native_rule_readiness(
            source, recorder,
            available_names={"hub_read_apps_code", "hub_get_tool_guide"},
            question=question,
        ))
        evidence = recorder.receipts()
        coverage = native_rule_readiness_coverage(question, evidence)
        return message, details, evidence, coverage
    finally:
        recorder.reset(token)


def test_live_preflight_intent_requires_distinct_parent_and_contract_checks():
    assert is_native_rule_readiness_question(QUESTION)
    assert _extra_requested_checks(QUESTION) == (False, True, False, True, True)


def test_preflight_exact_id_built_in_parent_and_guide_contract_are_source_attested():
    source = SourceOnly()
    message, details, evidence, coverage = _run(source)
    assert details["mcpServerVersion"] == "5.1.6"
    assert details["preflightEvidenceComplete"] is True
    assert details["nativeParentIdentity"] == {
        "appId": "169", "verified": True, "appTypeId": "18",
        "childRowsObserved": 1, "failureCode": None,
        "parentEvidenceMode": "inventory-and-non-rendering-summary",
    }
    assert details["nativeDatedFieldGuideAttested"] is True
    assert details["nativeCreateContractGuideAttested"] is True
    assert details["nativeGuideContract"]["typedTriggerFields"] == {
        "time#": "enum", "atTime#": "time",
        "date#": "bool", "atDate#": "date",
    }
    assert coverage["evidenceComplete"] is True
    assert coverage["readinessForMutation"] is False
    assert "exact built-in type and returned child relationship verified" in message
    assert "documented (guide only; runtime untested)" in message
    assert len(source.calls) == 6
    assert [a.get("tool", "guide") for _, a in source.calls] == [
        "hub_list_backups", "guide", "guide", "hub_list_apps",
        "hub_list_apps", "hub_get_app_config",
    ]
    assert all(row["effect"] == "read" and row["mutates"] is False
               for row in evidence)
    assert all(
        a.get("tool") != "hub_get_app_config"
        or a["args"] == {"appId": "169", "summary": True}
        for _, a in source.calls
    ), "A strict preflight must never render a full app page"
    assert all("hub_manage" not in gateway and a.get("tool") not in {
        "hub_set_rule", "hub_set_native_app",
    } for gateway, a in source.calls)
    for output in (message, str(details), str(evidence), str(coverage)):
        assert SECRET not in output
        assert "I-HAVE-READ-THE-GUIDE-" not in output


@pytest.mark.parametrize("broken,expected", [
    (dict(typ={"apps": [{"id": 18, "name": "Rule Machine",
                         "system": False, "isBuiltIn": False}]}),
     "native_type_conflict_or_unverified"),
    (dict(summary={**SUMMARY, "namespace": "community"}),
     "app_summary_identity_conflict"),
    (dict(instances={**INST, "apps": [
        {**INST["apps"][0], "parentId": 100}, INST["apps"][1]
    ]}), "installed_app_identity_unverified"),
])
def test_bad_parent_class_or_role_never_certified(broken, expected):
    source = SourceOnly(**broken)
    message, details, evidence, coverage = _run(source)
    assert details["nativeParentIdentity"]["verified"] is False
    assert details["nativeParentIdentity"]["failureCode"] == expected
    assert coverage["evidenceComplete"] is False
    assert coverage["readinessForMutation"] is False
    assert "unverified" in message
    assert all(r["mutates"] is False for r in evidence)


def test_partial_guide_names_cannot_attest_unseen_date_type_or_creator():
    partial = (GUIDE.replace("atDate# type=date yyyy-MM-dd",
                              "atDate# optional input: secret")
               .replace("operation=create", "read-only guide"))
    contract = _guide_contract_projection(partial)
    assert contract["atDateNamed"] is True
    assert contract["atDateTypeDateDeclared"] is False
    assert contract["dateFormatDeclared"] is False
    assert "atdate_input_type_not_declared" in contract["gapCodes"]
    assert contract["createContractDocumented"] is False
    message, details, evidence, coverage = _run(SourceOnly(guide=partial))
    assert "atDate# type=date declared=false" in message
    assert details["nativeDatedFieldGuideAttested"] is False
    assert coverage["evidenceComplete"] is False
    assert SECRET not in str(evidence)


def test_no_exact_parent_id_refuses_identity_instead_of_guessing_169():
    question = QUESTION.replace("app 169", "an installed app")
    source = SourceOnly()
    message, details, _, coverage = _run(source, question)
    assert details["nativeParentIdentity"]["appId"] is None
    assert details["nativeParentIdentity"]["failureCode"] == "explicit_parent_id_required"
    assert len(source.calls) == 3
    assert coverage["evidenceComplete"] is False
    assert "ID not unambiguously supplied" in message


@pytest.mark.asyncio
async def test_native_preflight_router_uses_source_without_model_or_rule_writes():
    mcp = SourceOnly()
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b",
                            ai_client=NeverModel())
    result = await agent.process_user_request_result(
        QUESTION, session_id="native-418-parent-date-contract",
    )
    assert result.request_class == "live-read"
    assert result.investigation_coverage["domain"] == "native_rule_readiness"
    assert result.investigation_coverage["readinessForMutation"] is False
    assert "app 169" in result.message
    assert "MCP Rule Server version" in result.message
    assert len(mcp.calls) == 6
    assert all(row["mutates"] is False for row in result.evidence)
    assert SECRET not in str(result.evidence)

def test_root_without_child_link_does_not_claim_parent_role():
    root_only = {**INST, "apps": [INST["apps"][0]], "count": 1}
    message, details, evidence, coverage = _run(SourceOnly(instances=root_only))
    assert details["nativeParentIdentity"]["verified"] is False
    assert details["nativeParentIdentity"]["failureCode"] == (
        "child_parent_relationship_unverified"
    )
    assert coverage["readinessForMutation"] is False
    assert coverage["evidenceComplete"] is False
    assert "unverified" in message
    assert all(row["mutates"] is False for row in evidence)


def test_no_rendered_config_read_even_when_sources_conflict():
    source = SourceOnly(summary={**SUMMARY, "namespace": "community"})
    _run(source)
    assert not any(
        a.get("tool") == "hub_get_app_config"
        and a["args"].get("summary") is not True
        for _, a in source.calls
    )



# Live 0.18.419 request: the question asks for the published contract and gap
# evidence without spelling out atDate# or "creation". Those proof obligations
# must not be silently dropped just because the core readiness checks succeed.
LIVE_419_QUESTION = (
    "Perform a READ-ONLY native Rule Machine scheduling preflight. "
    "Verify MCP Server version, latest hub-local backup and Rule Machine "
    "tool-guide availability. Verify native Rule Machine parent app 169 using "
    "only non-rendering hub_list_apps instance/type records and "
    "hub_get_app_config(summary=true). "
    "Do not render full app configuration pages or open editor forms. "
    "Report nativeParentIdentity, nativeGuideContract, observed child-parent "
    "relationships, guide evidence gaps and readinessForMutation. "
    "Distinguish missing guide declarations from unsupported server capabilities. "
    "Do not create, modify, execute or delete rules. Do not change devices or "
    "permissions. Include Technical JSON."
)

UNDOCUMENTED_GUIDE = (
    "I-HAVE-READ-THE-GUIDE-set_rule_reference-a12f109e\n"
    "hub_set_rule operation=create args:{parent_id,name,changes}.\n"
)


def test_419_live_guide_contract_request_cannot_return_false_success():
    assert is_native_rule_readiness_question(LIVE_419_QUESTION)
    assert _extra_requested_checks(LIVE_419_QUESTION) == (
        False, True, False, True, True,
    )
    source = SourceOnly(guide=UNDOCUMENTED_GUIDE)
    answer, details, evidence, coverage = _run(source, LIVE_419_QUESTION)
    assert details["preflightEvidenceComplete"] is True
    assert details["nativeParentIdentity"]["verified"] is True
    assert details["nativeGuideContract"]["inspectionStatus"] == "checked"
    assert details["nativeGuideContract"]["createOperationDocumented"] is True
    assert details["nativeGuideContract"]["parentIdParameterDocumented"] is True
    assert details["nativeDatedFieldGuideAttested"] is False
    assert details["nativeCreateContractGuideAttested"] is False
    assert "guide_unavailable" not in details["nativeGuideContract"]["gapCodes"]
    assert "atdate_field_not_named" in details["nativeGuideContract"]["gapCodes"]
    assert coverage["status"] == "partial-evidence"
    assert coverage["evidenceComplete"] is False
    assert coverage["questionResolved"] is False
    assert coverage["readinessForMutation"] is False
    req = {v["key"]: v["state"] for v in coverage["requirements"]}
    assert req["native_parent_identity"] == "observed"
    assert req["native_dated_field_guide"] == "checked-unverified"
    assert req["native_dated_create_contract_guide"] == "checked-unverified"
    assert "Date guide checks:" in answer
    assert "guide_unavailable_or_oversized" not in answer
    assert len(source.calls) == 6
    assert all(r["effect"] == "read" and r["mutates"] is False for r in evidence)
    assert all(
        a.get("tool") != "hub_get_app_config"
        or a["args"] == {"appId": "169", "summary": True}
        for _, a in source.calls
    )


@pytest.mark.parametrize("question", [
    "Read-only native Rule Machine preflight: check MCP Server version, latest hub-local backup and native tool guides. "
    "Report nativeGuideContract for the installed tool.",
    "Read-only native Rule Machine preflight: check MCP Server version, latest hub-local backup and native tool guides. "
    "Report guide evidence gaps, including any missing declarations.",
])
def test_positive_guide_reporting_requires_actual_guide_evidence(question):
    answer, details, evidence, coverage = _run(
        SourceOnly(guide=UNDOCUMENTED_GUIDE), question
    )
    assert details["nativeGuideContract"]["inspectionStatus"] == "checked"
    assert coverage["evidenceComplete"] is False
    assert "native_dated_field_guide" in {
        x["key"] for x in coverage["requirements"]
    }
    assert "atDate# named=false" in answer
    assert coverage["readinessForMutation"] is False


def test_simple_preflight_guide_was_checked_but_not_a_required_contract():
    question = (
        "Read-only native Rule Machine preflight: check MCP server version, "
        "latest hub-local backup, and tool-guide availability."
    )
    source = SourceOnly(guide=UNDOCUMENTED_GUIDE)
    answer, details, _, coverage = _run(source, question)
    assert len(source.calls) == 3
    assert details["nativeGuideContract"]["inspectionStatus"] == "checked"
    assert coverage["evidenceComplete"] is True
    assert "Date guide checks:" not in answer
    assert coverage["readinessForMutation"] is False


def test_prohibitions_are_not_positive_contract_requests():
    question = (
        "Read-only native Rule Machine preflight: verify MCP server version "
        "and latest backup. Do not report nativeGuideContract or guide gaps."
    )
    assert _extra_requested_checks(question) == (
        False, False, False, False, False
    )
