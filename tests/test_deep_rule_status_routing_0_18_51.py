"""v0.18.51: detailed Rule Machine reviews must bypass single-page status shortcuts.

Live regression: 'Inspect existing Rule Machine app 4239 ... actual triggers,
ordered IF/ELSE actions, counter variable, reset conditions, enabled status'
returned in 282ms with only hub_get_app_config(includeSettings=false).
This never inspected a single trigger/action and was routed scoped-app-status.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoped_app_status_read import scoped_status_app_id  # noqa: E402
from rule_machine_analysis import (  # noqa: E402
    requires_rule_logic_inspection, parse_rule_analysis_request,
)
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseAgent  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402


LIVE_4239_PROMPT = (
    'Inspect existing Rule Machine app 4239, "Internet: Google TV block after '
    '1hr total TV-on time". Read its actual triggers, ordered IF/ELSE actions, '
    'counter variable, reset conditions, current counter and enabled/paused '
    'status. Verify whether it correctly blocks Google TV Internet after 60 '
    'cumulative minutes and grants another 60 minutes once unblocked. '
    'Identify any defects or missing evidence. Do not create, modify, pause '
    'or disable any rules or devices.'
)


@pytest.mark.parametrize("prompt", [
    LIVE_4239_PROMPT,
    "Inspect Rule Machine app 4239 triggers, actions, variables and enabled status.",
    "Review app 4239 current status and IF/ELSE actions.",
    "Check app 4239 cumulative time counter and reset logic.",
    "Explain actual trigger events and ordered actions for rule 4239.",
])
def test_detailed_rule_logic_bypasses_both_status_shortcuts(prompt):
    assert requires_rule_logic_inspection(prompt)
    assert scoped_status_app_id(prompt) is None
    assert parse_rule_analysis_request(prompt) is None


@pytest.mark.parametrize("prompt,app_id", [
    ("What is the current status of Livingroom Light 1 automation (app 4019)?", 4019),
    ("Is app 4239 enabled?", 4239),
    ("Show the current status of app 4239", 4239),
])
def test_simple_status_still_uses_fast_path(prompt, app_id):
    assert scoped_status_app_id(prompt) == app_id
    assert not requires_rule_logic_inspection(prompt)


@pytest.mark.parametrize("prompt", [
    "Show recent logs for app 4239.",
    "Investigate whether app 4239 sent OFF at 10am yesterday.",
    "What is the status of the TV device 4221?",
    "Disable app 4239 now.",
    "Review app 4239 current settings.",
])
def test_unrelated_historical_control_and_simple_reads_not_deep(prompt):
    assert not requires_rule_logic_inspection(prompt)


@pytest.mark.asyncio
async def test_detailed_rule_routes_to_model_evidence_path_not_config_snapshot(monkeypatch):
    called = []

    async def bounded_model_path(self, prompt, history=None, *, session_id="default"):
        called.append((prompt, session_id))
        return AgentOutcome(
            message=(
                "Rule ID 4239 requires native trigger/action verification; "
                "configuration page identity alone is insufficient."
            ),
            request_class="live-read", evidence=[], choices=[],
        )

    monkeypatch.setattr(BaseAgent, "process_user_request_result", bounded_model_path)
    agent = UnifiedMCPAgent(object(), "test-key")
    outcome = await agent.process_user_request_result(
        LIVE_4239_PROMPT, session_id="deep-rule-4239"
    )
    assert called == [(LIVE_4239_PROMPT, "deep-rule-4239")]
    assert "requires native trigger/action verification" in outcome.message
    assert outcome.request_class == "live-read"
    assert not outcome.confirmation_required
