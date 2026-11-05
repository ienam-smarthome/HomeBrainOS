"""v0.18.415: safety clauses must not invoke whole-hub automation-status.

Live 0.18.414 repro: a source-scoped read-only retry for existing
native Rule Machine IDs 2967/3985 instead returned 166 status rows in 1s.
The status matcher previously saw "rule" and "disabled" anywhere in the
question, including "Keep native rule-writing authorisation disabled".
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation_status_service import (
    AutomationStatusService, AutomationStatusOutcome,
)
from native_dated_trigger_discovery import (
    is_existing_dated_trigger_question, _requested_rule_ids,
)


LIVE_RETRY = (
    "Retry read-only inspection of existing native Rule Machine dated triggers "
    "for rule IDs 2967 and 3985. Check saved time#, atTime#, date# and atDate# "
    "fields and their types and values. Verify each ID against the native "
    "child-app inventory first. Use only hub_set_rule(operation=read) for "
    "confirmed IDs. Report successful and incomplete reads separately. "
    "Do not create, modify, execute or delete rules, or open editor forms. "
    "Keep native rule-writing authorisation disabled. Include Technical JSON."
)


@pytest.mark.parametrize("prompt", [
    LIVE_RETRY,
    (
        "Inspect existing native Rule Machine dated triggers read-only for "
        "rule IDs 2967 and 3985. List source typed date fields; keep writer disabled."
    ),
    (
        "Read-only investigate existing Rule Machine dated triggers. "
        "Check saved atDate# for rule IDs 2967 and 3985 and leave authorisation disabled."
    ),
    "Review the stored fields for rule 2967; do not modify its disabled status.",
    "Show recent logs for the existing Rule Machine app, not the global status.",
])
def test_incidental_disabled_list_and_status_do_not_trigger_global_inventory(prompt):
    assert AutomationStatusService.matches_request(prompt) is False


def test_exact_live_retry_stays_an_exclusive_native_date_read_intent():
    assert is_existing_dated_trigger_question(LIVE_RETRY)
    assert _requested_rule_ids(LIVE_RETRY) == ["2967", "3985"]
    assert AutomationStatusService.matches_request(LIVE_RETRY) is False


@pytest.mark.parametrize("prompt", [
    "List every automation app and Rule Machine rule with its current active, disabled, paused, broken, or unknown status",
    "List all my automations",
    "Show my Rule Machine rules",
    "Which rules are paused?",
    "Which automations are broken?",
    "What automations are disabled?",
    "Automation status",
    "Status of my automations",
    "How many rules are active?",
    "Recommend useful automations for my home",
    "recommend which of my automations need fixing",
    "Review which of my rules have problems",
])
def test_genuine_broad_status_and_ideas_queries_still_route_fast(prompt):
    assert AutomationStatusService.matches_request(prompt) is True


def test_actual_api_ask_routes_retry_to_agent_not_status_dashboard(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    calls = []

    async def model_or_specialist(prompt, history, *, session_id):
        calls.append(prompt)
        return SimpleNamespace(
            message="Native existing-date exact-ID reader selected.",
            request_class="live-read", evidence=[],
            choices=[], route="unified-mcp-agent",
        )

    async def reject_status(*args, **kwargs):
        raise AssertionError("whole-hub automation status must not be called")

    monkeypatch.setattr(module.agent, "process_user_request_result", model_or_specialist)
    monkeypatch.setattr(module.automation_status, "snapshot", reject_status)
    with TestClient(module.app) as client:
        resp = client.post("/api/ask", json={
            "query": LIVE_RETRY, "model_tier": "free",
        })
    assert resp.status_code == 200
    assert resp.json()["route"] == "unified-mcp-agent"
    assert "Native existing-date" in resp.json()["message"]
    assert calls == [LIVE_RETRY]


def test_actual_api_ask_preserves_explicit_automation_status_dashboard(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")

    async def fake_snapshot(*args, **kwargs):
        return AutomationStatusOutcome(
            message="An explicit full app/rule status request.",
            automation_items=[
                {"id": "3985", "name": "Example", "type": "rule",
                 "status": "paused"}
            ],
        )

    async def reject_agent(*args, **kwargs):
        raise AssertionError("explicit global status must not require an LLM")

    monkeypatch.setattr(module.automation_status, "snapshot", fake_snapshot)
    monkeypatch.setattr(module.agent, "process_user_request_result", reject_agent)
    with TestClient(module.app) as client:
        resp = client.post("/api/ask", json={
            "query": "List every automation app and Rule Machine rule with its current active, disabled, paused or broken status",
            "model_tier": "free",
        })
    assert resp.status_code == 200
    assert resp.json()["route"] == "automation-status"
    assert resp.json()["automation_items"][0]["status"] == "paused"
