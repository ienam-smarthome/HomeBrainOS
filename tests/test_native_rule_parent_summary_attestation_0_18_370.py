"""Native Rule Machine parent identity via a read-only per-app summary.

The current live hub reported app ID 169, appTypeId 18, but the
hub_list_apps(scope=types) native Rule Machine type list was empty.
Upstream MCP may omit systemAppTypes from that list while supporting the
independent non-rendering /installedapp/json/169 summary endpoint.
Never promote a mere name or user:false into native appType proof.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from native_rule_inventory_source import (  # noqa: E402
    _native_parent_from_summary, project_rule_inventory,
    read_native_rule_inventory, render_inventory,
)

INSTANCES = {"apps": [
    {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
     "appTypeId": 18, "parentId": None, "user": False},
], "count": 1, "totalOnHub": 1, "filter": "all"}
TYPES_MISSING_SYSTEM = {
    "apps": [{"id": 731, "namespace": "user", "name": "Community Rule"}],
    "count": 1, "source": "hub_api",
    "note": "/hub2/appsList did not return a usable list this call; built-in (system) app types are omitted this call.",
}
RULES = {"rules": [], "count": 0}

SUMMARY = {
    "success": True, "id": 169, "name": "Rule Machine",
    "type": "Rule Machine", "user": False, "appTypeId": 18,
    "parentId": None,
    "appType": {"id": 18, "namespace": "hubitat",
                "name": "Rule Machine", "system": True},
    "endpoint": "/installedapp/json/169",
}


def test_direct_summary_source_attests_native_parent_even_if_types_omitted():
    parent, gap = _native_parent_from_summary(
        SUMMARY, candidate_id="169", candidate_type_id="18"
    )
    assert gap == ""
    assert parent == {
        "appId": "169", "appTypeId": "18",
        "namespace": "hubitat", "name": "Rule Machine",
        "proof": "source-typed-installed-app-summary",
    }
    result = project_rule_inventory(
        INSTANCES, TYPES_MISSING_SYSTEM, RULES, {"169": SUMMARY},
    )
    assert result["parents"] == [parent]
    assert result["candidateParents"] == []
    assert result["parentIdentityComplete"]
    assert result["typesListComplete"] is False
    assert result["oneTimeMatchCount"] == 0
    assert "Verified native Rule Machine parent app: ID **169**" in render_inventory(result)


@pytest.mark.parametrize("patch,expected_gap", [
    ({}, "native-app-summary-class-namespace-unavailable"),
    ({"user": True}, "native-app-summary-built-in-unverified"),
    ({"id": 170}, "native-app-summary-id-mismatch"),
    ({"parentId": 99}, "native-app-summary-parent-conflict"),
    ({"type": "Rule-5.1"}, "native-app-summary-type-conflict"),
    ({"appTypeId": 19}, "native-app-summary-class-id-conflict"),
    ({"appType": {"namespace": "user", "name": "Rule Machine",
                   "system": True}}, "native-app-summary-class-namespace-unverified"),
    ({"appType": {"namespace": "hubitat", "name": "Rule Machine",
                   "system": False}}, "native-app-summary-system-conflict"),
    ({"appType": {"id": 19, "namespace": "hubitat",
                  "name": "Rule Machine", "system": True}},
     "native-app-summary-class-id-conflict"),
])
def test_summary_must_provide_exact_native_type_link(patch, expected_gap):
    candidate = deepcopy(SUMMARY)
    if patch:
        candidate.update(patch)
    else:
        candidate.pop("appType")
    parent, gap = _native_parent_from_summary(
        candidate, candidate_id="169", candidate_type_id="18",
    )
    assert parent is None
    assert gap == expected_gap
    result = project_rule_inventory(
        INSTANCES, TYPES_MISSING_SYSTEM, RULES, {"169": candidate}
    )
    assert result["parents"] == []
    assert result["oneTimeRules"] == []
    assert result["summarySourceChecks"][0]["typeProofGap"] == expected_gap
    assert result["parentIdentityComplete"] is False


def test_bare_summary_type_or_false_builtin_class_cannot_gain_native_authority():
    bare = {"success": True, "id": 169, "name": "Rule Machine",
            "type": "Rule Machine", "user": False}
    p = project_rule_inventory(
        INSTANCES, TYPES_MISSING_SYSTEM, RULES, {"169": bare}
    )
    assert p["parents"] == []
    assert p["candidateParents"][0]["appTypeId"] == "18"
    assert p["typesListComplete"] is False
    assert p["parentIdentityComplete"] is False
    assert "omitted its native appType namespace/name" in render_inventory(p)


class StubMCP:
    def __init__(self, *, typed_summary=True, type_catalog=TYPES_MISSING_SYSTEM):
        self.calls = []
        self.type_catalog = type_catalog
        self.typed_summary = typed_summary

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        assert gateway in {"hub_read_apps_code", "hub_read_rules"}
        assert args["tool"] in {"hub_list_apps", "hub_list_rules", "hub_get_app_config"}
        if args["tool"] == "hub_get_app_config":
            assert args == {
                "tool": "hub_get_app_config",
                "args": {"appId": "169", "summary": True}
            }
            data = SUMMARY if self.typed_summary else {
                "success": True, "id": 169, "type": "Rule Machine",
                "user": False,
            }
        elif args["tool"] == "hub_list_apps":
            data = (INSTANCES if args["args"]["scope"] == "instances"
                    else self.type_catalog)
        else:
            data = RULES
        return MCPToolResult(gateway, args, {}, "", data)


@pytest.mark.asyncio
async def test_readonly_summary_is_one_extra_call_only_when_native_catalog_gap():
    client = StubMCP()
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        report, result = await read_native_rule_inventory(
            client, evidence,
            available_names={"hub_read_apps_code", "hub_read_rules"},
        )
        assert result["parents"][0]["appId"] == "169"
        assert result["parents"][0]["proof"] == "source-typed-installed-app-summary"
        assert len(client.calls) == 4
        assert client.calls[3] == (
            "hub_read_apps_code",
            {"tool": "hub_get_app_config",
             "args": {"appId": "169", "summary": True}},
        )
        assert "ID **169**" in report
        assert len(evidence.receipts()) == 5
        assert all(x["effect"] == "read" and not x["mutates"]
                   for x in evidence.receipts())
        assert all(x["arguments"].get("tool") != "hub_set_rule"
                   for x in evidence.receipts())
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_bare_summary_stays_unresolved_and_reports_specific_missing_proof():
    client = StubMCP(typed_summary=False)
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        report, result = await read_native_rule_inventory(
            client, evidence,
            available_names={"hub_read_apps_code", "hub_read_rules"},
        )
        assert result["parents"] == []
        assert result["candidateParents"][0]["appId"] == "169"
        assert result["summarySourceChecks"][0]["typeProofGap"] == (
            "native-app-summary-class-namespace-unavailable"
        )
        assert result["parentIdentityComplete"] is False
        assert "omitted its native appType namespace/name" in report
        assert "No exact one-time suffix matched" in report
    finally:
        evidence.reset(token)


def test_native_summary_does_not_override_conflicting_explicit_class_record():
    types = {
        "apps": [{"id": 18, "namespace": "user",
                  "name": "Community App", "system": False}],
        "count": 1,
    }
    p = project_rule_inventory(INSTANCES, types, RULES, {"169": SUMMARY})
    assert p["parents"] == []
    assert p["candidateParents"][0]["appTypeId"] == "18"
    assert p["summarySourceChecks"][0]["typeProofGap"] == (
        "native-app-summary-catalog-conflict"
    )

def test_complete_type_page_is_not_complete_parent_identity_with_unjoined_candidate():
    """Real failure shape: all returned rows were counted, but no class-ID join."""
    known_user_types = {
        "apps": [{"id": 740, "namespace": "community",
                  "name": "Unrelated App", "system": False}],
        "count": 1,
    }
    thin = {"success": True, "id": 169,
            "type": "Rule Machine", "user": False}
    projected = project_rule_inventory(
        INSTANCES, known_user_types, RULES, {"169": thin},
    )
    assert projected["typesListComplete"] is True
    assert projected["appListComplete"] is True
    assert projected["ruleListComplete"] is True
    assert projected["oneTimeMatchCount"] == 0
    assert projected["parents"] == []
    assert projected["candidateParents"][0]["appId"] == "169"
    assert projected["parentIdentityComplete"] is False
    assert projected["summarySourceChecks"][0]["typeProofGap"] == (
        "native-app-summary-class-namespace-unavailable"
    )


def test_no_installed_parent_candidates_complete_catalog_can_establish_absence():
    no_instances = {
        "apps": [{"id": 560, "name": "Another App",
                  "type": "Another App", "parentId": None}],
        "count": 1, "totalOnHub": 1, "filter": "all",
    }
    types = {"apps": [{"id": 50, "name": "Another App",
                       "namespace": "user"}], "count": 1}
    projection = project_rule_inventory(no_instances, types, RULES)
    assert projection["parents"] == []
    assert projection["candidateParents"] == []
    assert projection["parentIdentityComplete"] is True
