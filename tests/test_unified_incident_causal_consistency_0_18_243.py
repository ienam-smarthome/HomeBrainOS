"""v0.18.243: real 30 Oct 11:09 runtime receipt replay and causal checks.

The previous v0.18.242 safeguard passed when complete ON/OFF device history
was mocked, but live Bathroom 1/2 returned only OFF and level commands.
This replay tests precisely that partial source, including its false model
response, through the original agent's final answer boundary.
"""
from __future__ import annotations

from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from unified_investigation_bridge import (
    collect_unified_evidence, reconcile_unified_investigation_answer,
    unified_investigation_followup, unified_investigation_instruction,
)
from unified_incident_synthesis import (
    source_contradiction_flags, verified_incident_ledger,
)
from mcp_agent_orchestrator import UnifiedMCPAgent
from test_unified_homebrain_investigation_0_18_241 import (
    QUESTION, bathroom, reported, command, read_device,
)

WRONG_LIVE = (
    "The investigation indicates that activations were driven by location "
    "mode changes and physical motion detection.\n\n"
    "### Likely Causes\n"
    "* **Bathroom Lights 1 & 2:** These were activated by Light Mode "
    "Controller (App 4013) in response to Hubitat location mode changes.\n"
    "* **Shower Light:** This was activated by Shower Rule (App 4014).\n\n"
    "### 🕒 Reconstructed Event Timeline (30 Oct 2026)\n"
    "| Time | Light | Event |\n|---|---|---|\n"
    "| 07:12:34 | Bathroom Light 2 | setLevel(30) |\n\n"
    "### Analysis of Activations\n"
    "All recorded light events were setLevel commands.\n"
    "No OFF commands or state transitions to off were recorded for any "
    "of the three lights between 02:00 and 07:30.\n"
    "The commands functioned as activations rather than adjustments."
)


def actual_partial_receipts():
    receipts = bathroom()
    for r in receipts:
        args = r.get("arguments", {}).get("args", {})
        if r.get("sub_tool") != "hub_list_device_events":
            continue
        rows = r["details"]["observedEvents"]
        if args.get("deviceId") == "7818":
            # The actual 11:09 Hubitat page returned 6 rows, no switches.
            r["details"]["observedEvents"] = [
                reported("level", "07:15:03.071", "50"),
                command("setLevel", "07:15:02.678", "4013", "Bathroom"),
                reported("level", "07:12:34.528", "30"),
                command("setLevel", "07:12:33.560", "4013", "Bathroom"),
                command("off", "03:46:05.251", "1569", "button 4 pushed"),
                command("off", "03:04:16.978", "1568", "button 3 pushed"),
            ]
        elif args.get("deviceId") == "7821":
            # Actual 11:09 page returned 4 rows, again no switches.
            r["details"]["observedEvents"] = [
                reported("level", "07:12:35.546", "30"),
                command("setLevel", "07:12:34.622", "4013", "Bathroom"),
                command("off", "03:46:05.313", "1569", "button 4 pushed"),
                command("off", "03:04:16.993", "1568", "button 3 pushed"),
            ]
    return receipts


def test_partial_bathroom_target_histories_are_not_dropped_for_no_switch_rows():
    fact = collect_unified_evidence(actual_partial_receipts(), QUESTION)
    assert fact is not None
    assert fact["target_device_ids"] == ["7807", "7818", "7821"]
    assert set(fact["missing_switch_history_for_targets"]) == {
        "Bathroom Light 1", "Bathroom Light 2"}
    assert len(fact["transition_relationships"]) == 6 or len(fact["transition_relationships"]) == 5
    coverage = {r["device_id"]: r for r in fact["target_coverage"]}
    assert coverage["7818"]["reported_switch_on"] == 0
    assert coverage["7818"]["reported_switch_off"] == 0
    assert coverage["7818"]["issued_off"] == 2
    assert coverage["7818"]["issued_setlevel"] == 2
    assert coverage["7821"]["issued_off"] == 2
    assert coverage["7821"]["reported_level"] == 1
    assert coverage["7807"]["reported_switch_off"] >= 2
    assert fact["incident_ledger_total"] > 0
    assert all(r["event_class"] != "reported_switch_on"
               for r in fact["incident_ledger"]
               if r["device_id"] in ("7818", "7821"))


def test_false_no_off_and_mode_causes_are_rejected_entirely_not_appended():
    receipts = actual_partial_receipts()
    facts = collect_unified_evidence(receipts, QUESTION)
    flags = source_contradiction_flags(WRONG_LIVE, facts)
    assert "off_evidence_denied" in flags
    assert "issued_off_commands_omitted" in flags
    assert "initiator_claim_without_switch_history" in flags
    fixed, changed = reconcile_unified_investigation_answer(
        WRONG_LIVE, receipts, QUESTION)
    assert changed
    assert "activations were driven by location mode changes" not in fixed
    assert "No OFF commands or state transitions" not in fixed
    assert "Physical Confirmation" not in fixed
    assert "### Verified incident ledger" in fixed
    assert "03:04:16 | Bathroom Light 1 | Issued command | off()" in fixed
    assert "03:04:16 | Bathroom Light 2 | Issued command | off()" in fixed
    assert "03:46:05 | Bathroom Light 1 | Issued command | off()" in fixed
    assert "03:46:05 | Bathroom Light 2 | Issued command | off()" in fixed
    assert "07:12:33 | Bathroom Light 1 | Issued command | setLevel" in fixed
    assert "07:12:34 | Bathroom Light 2 | Issued command | setLevel" in fixed
    assert "07:15:02 | Bathroom Light 1 | Issued command | setLevel" in fixed
    assert "07:15:02 | Bathroom Light 1 | Reported switch | ON" not in fixed
    assert "02:18:15" not in fixed and "02:52:44" not in fixed
    assert "Causal limit" not in fixed  # unified new text says Cause is not fully verified
    assert "Cause is not fully verified" in fixed
    assert "Incomplete switch-state coverage" in fixed
    assert fixed.count("### ") == 1


def test_recovery_prompt_asks_for_independent_scoped_state_not_more_groovy_code():
    instruction = unified_investigation_followup(actual_partial_receipts(), QUESTION)
    assert instruction is not None
    assert "NO reported switch ON/OFF" in instruction
    assert "attribute=switch" in instruction
    assert "verified IDs" in instruction
    assert "write" in instruction
    context = unified_investigation_instruction(actual_partial_receipts(), QUESTION)
    assert '"target_coverage"' in context
    assert '"incident_ledger"' in context
    assert '"missing_switch_history_for_targets"' in context
    assert "no complete ON/OFF" in context


def test_read_only_source_gap_discloses_coverage_even_if_ai_answer_is_pleasant():
    msg, changed = reconcile_unified_investigation_answer(
        "The lights were affected by a variety of factors.",
        actual_partial_receipts(), QUESTION)
    assert changed
    assert "no switch ON/OFF" in msg
    assert "OFF commands were recorded" in msg
    assert "the initiating controller" in msg


@pytest.mark.asyncio
async def test_real_original_agent_publishes_single_consistent_answer(monkeypatch):
    class _NoMCP:
        async def list_tools(self): return []
        async def get_device_identities(self): return []
    class _NoProvider:
        async def post(self, *_args, **_kwargs):
            raise AssertionError("No new model call is needed after source receipts")
        async def aclose(self): return None

    agent = UnifiedMCPAgent(_NoMCP(), "key", "fake",
                            ai_client=_NoProvider(),
                            require_sensitive_confirmation=False)
    async def unreliable_ai(*_args, **_kwargs):
        for r in actual_partial_receipts():
            agent.evidence.record(
                r["tool"], r["arguments"], success=True,
                effect="read", mutates=False, elapsed_ms=1,
                summary="Verified source observation",
                supports_live_claim=True, details=r["details"],
            )
        return WRONG_LIVE
    monkeypatch.setattr(agent, "_process_user_request", unreliable_ai)
    outcome = await agent.process_user_request_result(QUESTION)
    assert outcome.request_class == "live-read"
    assert outcome.confirmation_required is False
    assert "No OFF commands" not in outcome.message
    assert "the lights were activated by" not in outcome.message
    assert outcome.message.count("### Verified incident ledger") == 1
    assert "Bathroom Light 1 | Issued command" in outcome.message
    assert "Bathroom Light 2 | Issued command" in outcome.message
    assert "Shower Light | Reported switch" in outcome.message
    assert all(e["mutates"] is False for e in outcome.evidence)


def test_rejected_unsupported_target_id_never_creates_asserted_history():
    receipts = [r for r in actual_partial_receipts() if r.get("sub_tool") != "hub_list_devices"]
    assert collect_unified_evidence(receipts, QUESTION) is None
    good = actual_partial_receipts()
    for r in good:
        if r.get("sub_tool") == "hub_list_device_events":
            r["supports_live_claim"] = False
    assert collect_unified_evidence(good, QUESTION) is None
