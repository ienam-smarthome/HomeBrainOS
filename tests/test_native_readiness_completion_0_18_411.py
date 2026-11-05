"""Regression: native read-only preflight must not be republished as app identity.

An installed 0.18.410 result had complete core preflight evidence (MCP 5.1.5,
backup and 2 guides), but the shared completion classifier noticed "native
parent app 169" and erased the preflight answer. No model or writer is needed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from native_rule_readiness_source import (
    is_native_rule_readiness_question,
    native_rule_readiness_coverage,
    read_native_rule_readiness,
)
from targeted_rule_scope_policy import is_app_class_identity_question
from mcp_client import MCPToolResult
from evidence_recorder import EvidenceRecorder
from mcp_agent_orchestrator import AgentOutcome
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "Perform a read-only preflight for native Rule Machine dated one-time "
    "rule creation. Verify the installed MCP Rule Server version using MCP "
    "initialize/serverInfo and hub_get_info, and report whether they agree. "
    "Inspect the current set_rule_reference tool guide and establish whether "
    "the native writer supports the Certain Time (and optional date) trigger, "
    "including atDate# with type date, its accepted format and any available "
    "readback evidence. Check the latest hub-local backup timestamp. "
    "Use the already established identity of native Rule Machine parent app 169, "
    "but identify any additional verification required by the writer's own "
    "preflight. Do not create, update, delete or execute any rule."
)

SIMPLE_REQUEST = (
    "Run a read-only native Rule Machine readiness preflight. Check the "
    "MCP server version, latest backup timestamp and both tool guides."
)


class FakeMCP:
    def __init__(
        self, *,
        initial_version="5.1.5", current_version="5.1.5",
        guide_at_date=False,
    ):
        self.server_info = {
            "name": "hubitat-mcp-rule-server", "version": initial_version,
        }
        self.current_version = current_version
        self.guide_at_date = guide_at_date
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            data = (
                {"mcpServerVersion": self.current_version}
                if self.current_version is not None else {}
            )
        elif name == "hub_read_apps_code":
            assert arguments == {
                "tool": "hub_list_backups", "args": {"scope": "hub_local"},
            }
            data = {
                "scope": "hub_local",
                "hubLocalBackups": [
                    {"createTimeOrig": "2026-11-05T03:02:31+00:00"},
                ],
            }
        elif name == "hub_get_tool_guide":
            section = arguments["section"]
            extra = (
                "atDate# type: date yyyy-MM-dd\n"
                if self.guide_at_date and section == "set_rule_reference"
                else "Native Rule Machine writer fields require independent checks.\n"
            )
            data = {
                "content": extra + "I-HAVE-READ-THE-GUIDE-"
                + section + "-abcdef123456\n",
            }
        else:
            raise AssertionError("Unexpected gateway " + name)
        return MCPToolResult(
            name=name, arguments=arguments, raw={}, text="",
            data=data, is_error=False,
        )


def _run(request=REQUEST, **opts):
    mcp = FakeMCP(**opts)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        answer, details = asyncio.run(read_native_rule_readiness(
            mcp, recorder,
            available_names=frozenset((
                "hub_read_apps_code", "hub_get_tool_guide", "hub_get_info",
            )),
            question=request,
        ))
        evidence = recorder.receipts()
    finally:
        recorder.reset(token)
    return mcp, answer, details, evidence


def test_actual_2026_11_05_request_keeps_readiness_domain_and_answer():
    assert is_native_rule_readiness_question(REQUEST)
    assert is_app_class_identity_question(REQUEST)  # overlapping trigger existed
    mcp, answer, details, evidence = _run()
    assert len(mcp.calls) == 4  # prior parent identity is referenced, not rechecked
    assert details["mcpServerVersion"] == "5.1.5"
    assert details["hubInfoMcpServerVersion"] == "5.1.5"
    assert details["mcpVersionAgreement"] is True
    assert details["latestHubLocalBackupUtc"] == "2026-11-05T03:02:31+00:00"
    assert details["preflightEvidenceComplete"] is True
    assert details["nativeDatedFieldGuideAttested"] is False
    assert details["nativeDatedDateReadbackVerified"] is False
    assert details["readinessForMutation"] is False
    assert "Initialize/hub_get_info version agreement: verified" in answer
    assert "atDate# as a date field: not verified" in answer
    assert "saved-state readback: not checked" in answer
    assert not any(row["mutates"] for row in evidence)
    assert not any("I-HAVE-READ-THE-GUIDE" in str(row) for row in evidence)
    assert not any("I-HAVE-READ-THE-GUIDE" in t for t in (answer, str(details)))

    original = AgentOutcome(
        message=answer, request_class="live-read",
        choices=[], evidence=evidence,
    )
    final = apply_shared_investigation_completion(original, REQUEST)
    assert final.message == answer  # no unrelated app-identity fallback
    assert final.investigation_coverage["domain"] == "native_rule_readiness"
    assert final.investigation_coverage["preflightEvidenceComplete"] is True
    assert final.investigation_coverage["evidenceComplete"] is False
    assert final.investigation_coverage["questionResolved"] is False
    assert final.investigation_coverage["readinessForMutation"] is False
    states = {r["key"]: r["state"]
              for r in final.investigation_coverage["requirements"]}
    assert states == {
        "mcp_server_version": "observed",
        "hub_local_backup": "observed",
        "native_rule_tool_guides": "observed",
        "mcp_version_agreement": "observed",
        "native_dated_field_guide": "checked-unverified",
        "native_dated_create_contract_guide": "checked-unverified",
        "native_dated_date_readback": "checked-unverified",
    }
    assert final.metrics["outcome"] == "unresolved"
    assert "appIdentityPublication" not in final.investigation_coverage


def test_simple_readiness_preflight_keeps_original_three_source_budget():
    mcp, answer, details, evidence = _run(SIMPLE_REQUEST)
    assert len(mcp.calls) == 3
    assert all(name != "hub_get_info" for name, _ in mcp.calls)
    assert details["preflightEvidenceComplete"] is True
    complete = native_rule_readiness_coverage(SIMPLE_REQUEST, evidence)
    assert complete["domain"] == "native_rule_readiness"
    assert complete["evidenceComplete"] is True
    assert complete["readinessForMutation"] is False


def test_installed_version_disagreement_is_not_treated_as_verified_support():
    _, answer, details, evidence = _run(current_version="5.1.6")
    assert details["mcpVersionAgreement"] is False
    assert "version agreement: conflict" in answer
    coverage = native_rule_readiness_coverage(REQUEST, evidence)
    assert coverage["evidenceComplete"] is False
    assert next(r["state"] for r in coverage["requirements"]
                if r["key"] == "mcp_version_agreement") == "checked-unverified"


def test_explicit_guide_declaration_does_not_verify_saved_date_readback():
    _, answer, details, evidence = _run(guide_at_date=True)
    assert details["nativeDatedFieldGuideAttested"] is True
    assert details["nativeDatedDateReadbackVerified"] is False
    assert "guide only; no persisted date proven" in answer
    coverage = native_rule_readiness_coverage(REQUEST, evidence)
    assert coverage["evidenceComplete"] is False
    assert next(r["state"] for r in coverage["requirements"]
                if r["key"] == "native_dated_date_readback") == "checked-unverified"


def test_unknown_hub_info_retains_completed_core_preflight_but_not_agreement():
    _, answer, details, evidence = _run(current_version=None)
    assert details["mcpVersionAgreement"] is None
    assert details["preflightEvidenceComplete"] is True
    assert "hub_get_info: not verified" in answer
    assert native_rule_readiness_coverage(REQUEST, evidence)[
        "questionResolved"
    ] is False


def test_unrelated_native_identity_request_is_not_stolen_by_preflight():
    question = (
        "Read-only investigate whether Rule Machine app 169 is the native "
        "built-in parent app type; do not change rules."
    )
    assert not is_native_rule_readiness_question(question)
    assert native_rule_readiness_coverage(question, []) is None
