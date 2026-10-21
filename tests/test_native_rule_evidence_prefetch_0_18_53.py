"""v0.18.53 regression: rule 4239 health and variable proof without writes."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from native_rule_evidence_prefetch import (  # noqa: E402
    prefetch_native_rule_evidence, _variables, _verified_health,
)
from evidence_recorder import EvidenceRecorder  # noqa: E402


class FakeMCP:
    def __init__(self, *, fail_health=False, variables=None):
        self.calls = []
        self.fail_health = fail_health
        self.variables = variables if variables is not None else [
            {"name": "TV_Minutes_Used", "type": "Number", "value": "42"},
            {"name": "credential", "type": "String", "value": "privatepassword"},
            {"name": "access_pin", "type": "Number", "value": "987654"},
        ]

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        assert gateway == "hub_read_rules"
        assert args["args"] == {"appId": "4239"}
        if args["tool"] == "hub_get_rule_health":
            if self.fail_health:
                return SimpleNamespace(is_error=True, data={"error": "not readable"})
            return SimpleNamespace(
                is_error=False, data={
                    "ok": True, "paused": False,
                    "stopped": None, "broken": False,
                    "name": "Internet: Google TV block after 1hr total TV-on time",
                },
            )
        assert args["tool"] == "hub_list_rule_local_variables"
        return SimpleNamespace(
            is_error=False, data={"appId": "4239", "localVariables": self.variables,
                                  "total": len(self.variables)},
        )


@pytest.mark.asyncio
async def test_native_rule_prefetch_reads_only_health_and_owned_variables():
    mcp = FakeMCP()
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = [{"role": "user", "content": "Inspect app 4239"}]
        attempted = await prefetch_native_rule_evidence(
            mcp, evidence, app_id="4239", available_names={"hub_read_rules"},
            messages=messages,
        )
        assert attempted
        assert [(gateway, args["tool"]) for gateway, args in mcp.calls] == [
            ("hub_read_rules", "hub_get_rule_health"),
            ("hub_read_rules", "hub_list_rule_local_variables"),
        ]
        receipts = evidence.receipts()
        assert len(receipts) == 2
        assert all(r["success"] and not r["mutates"] and r["effect"] == "read" for r in receipts)
        assert receipts[0]["details"]["verifiedHealth"] == {
            "paused": False, "broken": False,
        }
        assert receipts[1]["details"]["numericVariables"] == [{
            "name": "TV_Minutes_Used", "type": "Number", "value": 42,
        }]
        assert "TV_Minutes_Used" in messages[-1]["content"]
        assert "privatepassword" not in messages[-1]["content"]
        assert "987654" not in messages[-1]["content"]
        assert "Local variables belong to their owning app" in messages[-1]["content"]
        assert "does NOT prove" in messages[-1]["content"]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_blocked_health_read_is_reported_unknown_not_paused_or_broken():
    mcp = FakeMCP(fail_health=True)
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = []
        assert await prefetch_native_rule_evidence(
            mcp, evidence, app_id="4239", available_names={"hub_read_rules"},
            messages=messages,
        )
        receipts = evidence.receipts()
        assert receipts[0]["success"] is False
        assert receipts[1]["success"] is True
        assert "healthReadFailed" in messages[-1]["content"]
        assert '"paused": false' not in messages[-1]["content"]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_unavailable_native_read_gateway_causes_zero_mcp_calls():
    mcp = FakeMCP()
    evidence = EvidenceRecorder()
    messages = []
    assert not await prefetch_native_rule_evidence(
        mcp, evidence, app_id="4239",
        available_names={"hub_read_apps_code"}, messages=messages,
    )
    assert mcp.calls == [] and messages == []


def test_missing_health_booleans_and_nonnumeric_variable_values_not_inferred():
    assert _verified_health({"ok": True, "paused": None, "broken": "false"}) == {}
    variables, parsed = _variables({
        "localVariables": [
            {"name": "SafeNumber", "value": "7", "type": "Number"},
            {"name": "SensitiveString", "value": "secret123"},
            {"name": "Missing"},
        ]
    })
    assert parsed
    assert variables == [
        {"name": "SafeNumber", "type": "Number", "value": 7},
        {"name": "SensitiveString"},
        {"name": "Missing"},
    ]
    assert _variables({"localVariables": {}}) == ([], False)


def test_partial_rule_review_headline_calibrated_without_erasing_findings():
    from evidence_claim_calibrator import calibrate_api_outcome
    original = SimpleNamespace(
        message=(
            'The read-only investigation of Rule Machine app **4239** '
            'and its companion reset rule **4241** is complete.\n\n'
            'Counter TV_Minutes_Used reported 42; logs show initialized only.'
        ),
        evidence=[],
        investigation_coverage={
            "domain": "causal_provenance", "evidenceComplete": False,
            "status": "partial-evidence",
        },
        metrics={"outcome": "unresolved", "counters": {}},
    )
    result = calibrate_api_outcome(
        original,
        "Inspect Rule Machine app 4239 ordered actions and counter reset conditions.",
    )
    assert "remains partial" in result.message
    assert "is complete" not in result.message
    assert "TV_Minutes_Used reported 42" in result.message
    assert result.metrics["counters"]["evidence_claim_calibrations"] >= 1
    # Preserve the actual original evidence/response object.
    assert "is complete" in original.message


def test_complete_coverage_or_other_domains_keep_existing_conclusions():
    from evidence_claim_calibrator import calibrate_api_outcome
    text = "The investigation of Rule Machine app 4239 is complete."
    completed = SimpleNamespace(
        message=text, evidence=[], investigation_coverage={
            "evidenceComplete": True, "domain": "rule_machine"
        }, metrics={},
    )
    assert calibrate_api_outcome(completed, "Inspect app 4239 ordered actions").message == text
    unrelated = SimpleNamespace(
        message=text, evidence=[], investigation_coverage={
            "evidenceComplete": False, "domain": "other"
        }, metrics={},
    )
    assert calibrate_api_outcome(unrelated, "Explain my network").message == text


@pytest.mark.asyncio
async def test_wrong_app_id_response_is_never_promoted_to_4239_health():
    class WrongHub(FakeMCP):
        async def call_tool(self, gateway, args):
            if args["tool"] == "hub_get_rule_health":
                self.calls.append((gateway, args))
                return SimpleNamespace(is_error=False, data={
                    "ok": True, "appId": 9999, "paused": True, "broken": True,
                })
            return await super().call_tool(gateway, args)

    hub = WrongHub()
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        messages = []
        await prefetch_native_rule_evidence(
            hub, recorder, app_id="4239",
            available_names={"hub_read_rules"}, messages=messages,
        )
        health_receipt = recorder.receipts()[0]
        assert not health_receipt["success"]
        assert not health_receipt["supports_live_claim"]
        assert "healthReadFailed" in messages[-1]["content"]
        assert '"paused": true' not in messages[-1]["content"]
    finally:
        recorder.reset(token)


def test_secret_named_numeric_variable_is_not_exposed():
    variables, parsed = _variables({"localVariables": [
        {"name": "TV_Minutes_Used", "value": "42"},
        {"name": "adminPin", "value": "1234"},
        {"name": "api_key", "value": 7654321},
    ]})
    assert parsed
    assert variables == [
        {"name": "TV_Minutes_Used", "value": 42},
        {"name": "adminPin"},
        {"name": "api_key"},
    ]
