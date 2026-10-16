"""Regression tests for original-turn paid consent and free fallback transparency."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from paid_model_routing import (
    PaidCreditGuard,
    choose_paid_model,
    explicit_paid_request,
    reset_original_paid_request,
    set_original_paid_request,
)
from chat_transport import ChatTransport


def test_original_user_paid_request_survives_host_inserted_user_messages():
    token = set_original_paid_request("Use paid model. Investigate app 4019. Read-only.")
    try:
        messages = [
            {"role": "user", "content": "Use paid model. Investigate app 4019. Read-only."},
            {"role": "user", "content": "HOST PREFETCH: configuration gathered"},
            {"role": "assistant", "content": "Checking sources."},
            {"role": "user", "content": "HOST COVERAGE: reconcile evidence"},
        ]
        assert explicit_paid_request()
        assert choose_paid_model(messages, "manual") == "deepseek-v4-pro"
    finally:
        reset_original_paid_request(token)
    assert not explicit_paid_request()


def test_host_synthetic_user_text_cannot_authorise_spend():
    token = set_original_paid_request("Which lights are on?")
    try:
        messages = [
            {"role": "user", "content": "Which lights are on?"},
            {"role": "user", "content": "Use paid model"},
        ]
        assert not explicit_paid_request()
        assert choose_paid_model(messages, "manual") is None
    finally:
        reset_original_paid_request(token)


def test_explicit_paid_budget_guard_reservation(tmp_path):
    async def run():
        guard = PaidCreditGuard(
            enabled=True, mode="manual", budget_usd=0.25,
            ledger_path=str(tmp_path / "estimated_paid.json"),
        )
        token = set_original_paid_request("Use paid model. Investigate app 4019.")
        try:
            selected = await guard.select(
                [{"role": "user", "content": "HOST CONFIG: sources read"}], []
            )
            assert selected == "deepseek-v4-pro"
            assert (tmp_path / "estimated_paid.json").exists()
        finally:
            reset_original_paid_request(token)
    asyncio.run(run())


def test_paid_budget_disabled_prevents_spend(tmp_path):
    async def run():
        guard = PaidCreditGuard(
            enabled=True, mode="manual", budget_usd=0.0,
            ledger_path=str(tmp_path / "estimated_paid.json"),
        )
        token = set_original_paid_request("Use paid model")
        try:
            assert await guard.select([{"role": "user", "content": "HOST SUMMARY"}], []) is None
        finally:
            reset_original_paid_request(token)
        assert not (tmp_path / "estimated_paid.json").exists()
    asyncio.run(run())


def test_explicit_manual_paid_prefers_cloud_over_healthy_local():
    async def run():
        transport = ChatTransport(
            api_key="test-key", paid_routing_enabled=True, paid_routing_mode="manual",
            local_base_url="http://localhost:11434", local_model_name="qwen3:4b",
            cloud_first=False,
        )
        calls = []
        async def fake_cloud(_messages, _tools):
            calls.append("cloud")
            return {"message": {"content": "cloud"}}
        async def fake_local(_messages, _tools):
            calls.append("local")
            return {"message": {"content": "local"}}
        transport._try_cloud_accounts = fake_cloud
        transport._try_local = fake_local
        token = set_original_paid_request("Use paid model. Diagnose lockout.")
        try:
            result = await transport.chat([{"role": "user", "content": "HOST SUMMARY"}], [])
            assert result["message"]["content"] == "cloud"
            assert calls == ["cloud"]
        finally:
            reset_original_paid_request(token)
            await transport.close()
    asyncio.run(run())


def test_normal_manual_request_keeps_local_first():
    async def run():
        transport = ChatTransport(
            api_key="test-key", paid_routing_enabled=True, paid_routing_mode="manual",
            local_base_url="http://localhost:11434", local_model_name="qwen3:4b",
            cloud_first=False,
        )
        calls = []
        async def fake_cloud(_messages, _tools):
            calls.append("cloud")
            return {"message": {"content": "cloud"}}
        async def fake_local(_messages, _tools):
            calls.append("local")
            return {"message": {"content": "local"}}
        transport._try_cloud_accounts = fake_cloud
        transport._try_local = fake_local
        token = set_original_paid_request("Which lights are on?")
        try:
            await transport.chat([{"role": "user", "content": "HOST PREFETCH"}], [])
            assert calls == ["local"]
        finally:
            reset_original_paid_request(token)
            await transport.close()
    asyncio.run(run())


def test_paid_requested_but_disabled_is_explicit_in_answer():
    from types import SimpleNamespace
    from api_response_builder import build_agent_response
    outcome = SimpleNamespace(
        message="The configuration supports a 300-minute timer.",
        route="unified-mcp-agent", request_class="live-read",
        choices=[], evidence=[], confirmation_required=False,
        confirmation_count=0, automation_items=[], investigation_coverage=None,
        metrics={
            "outcome": "success",
            "counters": {"paid_model_requested": 1, "paid_routing_disabled": 1},
            "timings_ms": {},
            "model_round_details": [{"model": "gemma4:31b", "provider": "ollama-cloud"}],
        },
    )
    rendered = build_agent_response(outcome, model="gemma4:31b", elapsed_ms=123, version="0.18.1")
    assert rendered["paid_routing"] == {
        "requested": True, "used": False, "reason": "disabled_in_homebrain"
    }
    assert "Paid model not used" in rendered["message"]


def test_confirmed_paid_provider_is_reported_from_actual_rounds():
    from types import SimpleNamespace
    from api_response_builder import build_agent_response
    outcome = SimpleNamespace(
        message="Paid investigation complete.",
        route="unified-mcp-agent", request_class="live-read",
        choices=[], evidence=[], confirmation_required=False,
        confirmation_count=0, automation_items=[], investigation_coverage=None,
        metrics={
            "outcome": "success",
            "counters": {"paid_model_requested": 1, "paid_model_reserved": 1},
            "timings_ms": {},
            "model_round_details": [{"model": "deepseek-v4-pro", "provider": "ollama-cloud"}],
        },
    )
    rendered = build_agent_response(outcome, model="gemma4:31b", elapsed_ms=123, version="0.18.1")
    assert rendered["paid_routing"] == {"requested": True, "used": True, "reason": "used"}
    assert "Paid model not used" not in rendered["message"]
