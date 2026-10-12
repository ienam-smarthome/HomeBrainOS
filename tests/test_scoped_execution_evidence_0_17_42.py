"""Generic historical execution evidence handoff, without verdict-by-keywords."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from scoped_execution_evidence import (
    bounded_app_log_evidence, event_handler_associations,
    model_only_log_packet,
)
from motion_lockout_investigation import prefetch_motion_lockout


def test_log_excerpt_separates_verified_app_identity_from_requested_filter():
    packet, receipt = bounded_app_log_evidence({
        "logs": [
            {"appId": "4019", "date": "2026-10-12T23:49:27.700+0100",
             "message": "motionLockoutOffHandler entered"},
            {"date": "2026-10-12T23:49:34.000+0100",
             "message": "Motion event evaluated"},
            {"appId": "3602", "date": "2026-10-12T23:49:34.000+0100",
             "message": "OTHER app ON command"},
        ],
    }, "4019")
    assert len(packet) == 2
    assert packet[0]["scopeBasis"] == "explicit-app-id"
    assert packet[1]["scopeBasis"] == "requested-backend-filter-only"
    assert receipt["returnedRows"] == 3
    assert receipt["reviewableRows"] == 2
    assert receipt["sourceIdVerifiedRows"] == 1
    assert receipt["scopeUnverifiedRows"] == 1
    assert receipt["mismatchedRowsExcluded"] == 1
    assert receipt["rowContentsIncludedInPublicEvidence"] is False
    assert "message" not in receipt


def test_empty_and_malformed_logs_never_claim_review_or_execution():
    rows, summary = bounded_app_log_evidence(None, "4019")
    assert rows == []
    assert summary["returnedRows"] is None
    rows, summary = bounded_app_log_evidence({
        "logs": [{"appId": "4019", "message": ""}]
    }, "4019")
    assert rows == []
    assert summary["returnedRows"] == 1
    assert summary["reviewableRows"] == 0


def test_source_timestamps_and_log_excerpts_are_bounded_and_redacted():
    rows, summary = bounded_app_log_evidence({
        "logs": [
            {"source": "app|4019|Livingroom Light 1",
             "date": "2026-10-12 23:49:33",
             "message": "token=abc123 help@example.com " + "x" * 500},
        ],
    }, "4019")
    assert rows[0]["timestampOffsetVerified"] is False
    assert rows[0]["scopeBasis"] == "explicit-app-id"
    assert "[redacted]" in rows[0]["message"]
    assert "[email]" in rows[0]["message"]
    assert len(rows[0]["message"]) <= 240
    packet = model_only_log_packet(rows, "4019")
    assert "app-log-1" in packet
    assert "complete log capture" in packet.lower()


def test_state_event_handler_reference_is_not_decision_execution():
    off = datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
    rows = {"events": [
        {"name": "switch", "value": "off",
         "date": "2026-10-12T23:49:27.529+0100",
         "triggered": [
             {"appId": 4019, "handler": "lightSwitchHandler"},
             {"appId": 4019, "handler": "motionLockoutOffHandler"},
             {"appId": 4129, "handler": "liveDeviceEventHandler"},
         ]},
        {"name": "switch", "value": "off",
         "date": "2026-10-12T17:43:37.715+0100",
         "triggered": [
             {"appId": 4019, "handler": "motionLockoutOffHandler"}
         ]},
    ]}
    refs = event_handler_associations(rows, focal_off=off, app_id="4019")
    assert {x["handler"] for x in refs} == {
        "lightSwitchHandler", "motionLockoutOffHandler",
    }
    assert all(x["handlerExecutionVerified"] == "false" for x in refs)
    assert all(x["lockoutDecisionVerified"] == "false" for x in refs)


def test_no_off_event_or_no_explicit_matching_app_returns_empty_handler_refs():
    off = datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
    data = {"events": [
        {"value": "off", "date": "2026-10-12T23:49:27.529+0100",
         "triggered": [{"appId": 3602, "handler": "unrelated"}]},
    ]}
    assert event_handler_associations(data, focal_off=off, app_id="4019") == []


def test_prefetch_passes_app_log_text_only_to_model_not_public_evidence():
    identity = {"id": "7805", "label": "Livingroom Light 1",
                "name": "Livingroom Light 1",
                "attributes": {"switch": "off"}}
    logged = "motionLockoutOffHandler: inspect decision; token=superSecret"
    state = {
        "temporalAnalysis": {"intervals": [
            {"start": "2026-10-12T23:49:19.140+0100",
             "end": "2026-10-12T23:49:27.529+0100"},
        ]},
        "events": [
            {"name": "switch", "value": "off",
             "date": "2026-10-12T23:49:27.529+0100",
             "triggered": [
                 {"appId": 4019, "handler": "motionLockoutOffHandler"}
             ]}
        ],
        "commandEvents": [],
    }
    recorded = []

    class MCP:
        async def get_device_identities(self):
            return [identity]

    class Executor:
        async def execute(self, name, arguments, **kwargs):
            if name == "homebrain_device_history":
                result = state
            elif arguments.get("tool") == "hub_get_app_config":
                result = {"page": {"sections": []}}
            elif arguments.get("tool") == "hub_get_logs":
                result = {"logs": [{
                    "appId": 4019, "date": "2026-10-12T23:49:27.700+0100",
                    "message": logged,
                }]}
            else:
                raise AssertionError(name)
            return SimpleNamespace(
                success=True, result=SimpleNamespace(data=result))

    class Evidence:
        def record(self, name, args, **kw):
            recorded.append({"tool": name, "details": kw.get("details")})

    class Catalog:
        def declared_tool(self, name):
            return object()

    host = SimpleNamespace(
        mcp=MCP(), executor=Executor(), evidence=Evidence(),
        historical_journal=None)
    messages = []
    question = ("Investigate the latest manual OFF of Livingroom Light 1 "
                "followed by motion. Did app 4019's three-minute lockout engage?")
    assert asyncio.run(prefetch_motion_lockout(
        host, question, catalog=Catalog(), messages=messages))
    technical = next(
        x["details"] for x in recorded
        if x["tool"] == "homebrain_motion_lockout_investigation")
    evidence_json = json.dumps(technical)
    assert "superSecret" not in evidence_json
    assert "motionLockoutOffHandler" in evidence_json  # associated handler
    assert technical["handlerReferenceIsNotExecutionProof"] is True
    assert technical["sources"][2]["decisionContentProvidedToModel"] is True
    assert technical["sources"][2]["decisionContentReviewed"] is False
    assert any("motionLockoutOffHandler: inspect decision" in m["content"]
               for m in messages)
    assert all("superSecret" not in m["content"] for m in messages)
