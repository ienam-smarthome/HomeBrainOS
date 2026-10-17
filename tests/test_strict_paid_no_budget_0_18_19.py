"""v0.18.19: strict per-request model choice without a HomeBrain spending cap."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from paid_model_routing import (
    PaidCreditGuard, set_request_model_tier, reset_request_model_tier,
    set_original_paid_request, reset_original_paid_request,
)
from chat_transport import ChatTransport, PaidModelUnavailable
from api_response_builder import build_agent_response
from webui import render_page


def test_unlimited_production_guard_ignores_legacy_reservation_ledger(tmp_path):
    async def scenario():
        ledger = tmp_path / "ollama_paid_usage.json"
        ledger.write_text('{"reserved_usd": 2.9278, "reservation_count": 100}')
        guard = PaidCreditGuard(
            enabled=True, mode="manual", budget_usd=None, ledger_path=str(ledger),
        )
        t = set_request_model_tier("paid")
        try:
            for _ in range(20):
                assert await guard.select(
                    [{"role":"user","content":"Investigate the device"}], []
                ) == "deepseek-v4-pro"
            assert await guard.select_fallback([], []) == "deepseek-v4-pro"
        finally:
            reset_request_model_tier(t)
        assert ledger.read_text() == '{"reserved_usd": 2.9278, "reservation_count": 100}'
        assert guard.budget_usd is None
    asyncio.run(scenario())


def test_paid_requires_enabled_setting_even_without_local_cap(tmp_path):
    async def scenario():
        t = set_request_model_tier("paid")
        try:
            guard = PaidCreditGuard(enabled=False, budget_usd=None,
                ledger_path=str(tmp_path / "unused.json"))
            assert await guard.select([{"role":"user","content":"Investigate"}], []) is None
        finally:
            reset_request_model_tier(t)
    asyncio.run(scenario())


def test_paid_never_issues_gemma_after_paid_route_unavailable():
    async def scenario():
        transport = ChatTransport(
            api_key="test-key", paid_routing_enabled=False,
            paid_routing_mode="hybrid", paid_budget_usd=None,
            model_name="gemma4:31b",
        )
        attempted = []
        async def fake_round(messages, tools, **opts):
            attempted.append(opts["model_name"])
            return {"message": {"content": "This should never be returned."}}
        transport._chat_round = fake_round
        token = set_request_model_tier("paid")
        try:
            with pytest.raises(PaidModelUnavailable, match="no free-model fallback"):
                await transport.chat([{"role":"user","content":"Investigate"}], [])
            assert attempted == []
        finally:
            reset_request_model_tier(token)
            await transport.close()
    asyncio.run(scenario())


def test_paid_cloud_error_never_falls_back_to_configured_local():
    async def scenario():
        transport = ChatTransport(
            api_key="test-key", paid_routing_enabled=True,
            paid_routing_mode="hybrid", paid_budget_usd=None,
            model_name="gemma4:31b", cloud_first=False,
            local_model_name="qwen3:4b", local_base_url="http://localhost:11434",
        )
        models = []
        async def fail_cloud(messages, tools, **opts):
            models.append(opts["model_name"])
            raise RuntimeError("Provider unavailable")
        async def fake_local(messages, tools):
            models.append("local")
            return {"message":{"content":"unexpected local"}}
        transport._chat_round = fail_cloud
        transport._try_local = fake_local
        t = set_request_model_tier("paid")
        try:
            with pytest.raises(RuntimeError, match="Provider unavailable"):
                await transport.chat([{"role":"user","content":"Investigate"}], [])
            assert models == ["deepseek-v4-pro"]
        finally:
            reset_request_model_tier(t)
            await transport.close()
    asyncio.run(scenario())


def test_paid_remains_paid_across_several_model_rounds():
    async def scenario():
        transport = ChatTransport(
            api_key="test-key", paid_routing_enabled=True,
            paid_routing_mode="hybrid", paid_budget_usd=None,
            model_name="gemma4:31b",
        )
        models = []
        async def fake_round(messages, tools, **opts):
            models.append(opts["model_name"])
            return {"message":{"content":"OK"}}
        transport._chat_round = fake_round
        t = set_request_model_tier("paid")
        try:
            for _ in range(7):
                await transport.chat([{"role":"user","content":"Investigate"}], [])
            assert models == ["deepseek-v4-pro"] * 7
        finally:
            reset_request_model_tier(t)
            await transport.close()
    asyncio.run(scenario())


def _result_with_rounds(rounds, counters=None):
    return SimpleNamespace(
        message="Evidence checked; cause unverified.",
        route="unified-mcp-agent", request_class="live-read",
        choices=[], evidence=[], confirmation_required=False,
        confirmation_count=0, automation_items=[], investigation_coverage=None,
        metrics={"outcome":"unresolved", "counters":counters or {}, "timings_ms":{},
                 "model_round_details":[{"model":m,"provider":"ollama-cloud"} for m in rounds]},
    )


def test_auto_paid_usage_is_visible_without_explicit_paid_request():
    result = build_agent_response(
        _result_with_rounds(["deepseek-v4-pro"]+["gemma4:31b"]*4),
        model="gemma4:31b", elapsed_ms=24000, version="0.18.19",
    )
    assert result["model_usage"] == {
        "models":{"deepseek-v4-pro":1,"gemma4:31b":4},
        "paid_rounds":1,"free_rounds":4,"paid_used":True,
        "charges_controlled_by":"ollama-account",
    }
    assert result["model_continuity"]["mixed_models"] is True
    assert result["model_continuity"]["estimated_budget_exhausted"] is False
    assert "paid_routing" not in result


def test_strict_paid_observation_is_seven_deepseek_zero_gemma():
    result=build_agent_response(
        _result_with_rounds(["deepseek-v4-pro"]*7, {"paid_model_requested":1}),
        model="gemma4:31b", elapsed_ms=24000, version="0.18.19",
    )
    assert result["model_usage"]["paid_rounds"] == 7
    assert result["model_usage"]["free_rounds"] == 0
    assert result["paid_routing"]["used"] is True


def test_release_ui_and_addon_drop_budget_field_and_explain_billing():
    root = Path(__file__).resolve().parents[1]
    yaml = (root/"hubitat-mcp-ai"/"config.yaml").read_text()
    app = (APP_DIR/"app.py").read_text()
    page = render_page("HomeBrain", "0.18.19")
    assert "ollama_paid_budget_usd" not in yaml
    assert 'OPTIONS.get("ollama_paid_budget_usd")' not in app
    assert "no additional HomeBrain budget" in page
    assert "No Gemma fallback or HomeBrain budget" in page
    assert 'data.model_usage' in page
