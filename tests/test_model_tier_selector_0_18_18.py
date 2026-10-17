"""Per-request Auto / Free / Paid model selector and budget safety (v0.18.18)."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] /
           "hubitat-mcp-ai" / "rootfs" / "app")
)

from paid_model_routing import (
    PaidCreditGuard,
    choose_paid_model,
    explicit_paid_request,
    request_model_tier,
    reset_original_paid_request,
    reset_request_model_tier,
    set_original_paid_request,
    set_request_model_tier,
)
from webui import render_page


def message(value="Investigate an offline device."):
    return [{"role": "user", "content": value}]


def test_free_overrides_hybrid_manual_and_paid_routing_modes():
    original = set_original_paid_request("Use paid model. Investigate this device.")
    tier = set_request_model_tier("free")
    try:
        assert not explicit_paid_request()
        for mode in ("paid", "manual", "hybrid"):
            assert choose_paid_model(message("Use paid model."), mode) is None
    finally:
        reset_request_model_tier(tier)
        reset_original_paid_request(original)
    assert request_model_tier() == "free"


def test_paid_explicit_selector_works_even_in_manual_mode_without_prompt_magic():
    original = set_original_paid_request("Check the status of bedroom 3 mesh")
    tier = set_request_model_tier("paid")
    try:
        assert explicit_paid_request()
        for mode in ("manual", "hybrid"):
            assert choose_paid_model(message("Check the status of a device."), mode) == "deepseek-v4-pro"
    finally:
        reset_request_model_tier(tier)
        reset_original_paid_request(original)
    assert not explicit_paid_request()


def test_auto_keeps_existing_paid_selection_contract():
    token = set_request_model_tier("auto")
    try:
        assert choose_paid_model(message("Investigate why a light turned on"), "hybrid") == "deepseek-v4-pro"
        assert choose_paid_model(message("Investigate why a light turned on"), "manual") is None
        assert choose_paid_model(message("Are the lights on?"), "hybrid") is None
    finally:
        reset_request_model_tier(token)


def test_invalid_tiers_rejected_without_corrupting_current_selection():
    for invalid in ("premium", "", "PAID", True, None):
        with pytest.raises(ValueError):
            set_request_model_tier(invalid)
    assert request_model_tier() == "free"


def test_request_scope_prevents_cross_request_paid_consent():
    async def worker(tier):
        token = set_request_model_tier(tier)
        original = set_original_paid_request("Diagnose a device.")
        try:
            await asyncio.sleep(0)
            return (request_model_tier(), choose_paid_model(message(), "manual"),
                    explicit_paid_request())
        finally:
            reset_original_paid_request(original)
            reset_request_model_tier(token)

    free, paid = asyncio.run(_gather_workers(worker))
    assert free == ("free", None, False)
    assert paid == ("paid", "deepseek-v4-pro", True)
    assert request_model_tier() == "free"


async def _gather_workers(worker):
    return await asyncio.gather(worker("free"), worker("paid"))


def test_guard_never_reserves_on_explicit_free_but_paid_still_needs_budget(tmp_path):
    async def run():
        ledger = str(tmp_path / "credits.json")
        guard = PaidCreditGuard(
            enabled=True, mode="hybrid", budget_usd=0.25, ledger_path=ledger,
        )
        original = set_original_paid_request("Use paid model. Investigate the device.")
        try:
            tier = set_request_model_tier("free")
            try:
                assert await guard.select(message(), []) is None
                assert await guard.select_fallback(message(), []) is None
                assert not Path(ledger).exists()
            finally:
                reset_request_model_tier(tier)
            tier = set_request_model_tier("paid")
            try:
                assert await guard.select(message(), []) == "deepseek-v4-pro"
                assert Path(ledger).exists()
            finally:
                reset_request_model_tier(tier)
        finally:
            reset_original_paid_request(original)
    asyncio.run(run())


def test_paid_selector_cannot_override_disabled_or_exhausted_local_guard(tmp_path):
    async def run():
        token = set_request_model_tier("paid")
        try:
            disabled = PaidCreditGuard(
                enabled=False, mode="manual", budget_usd=1,
                ledger_path=str(tmp_path / "disabled.json"),
            )
            assert await disabled.select(message(), []) is None
            assert not (tmp_path / "disabled.json").exists()
            zero = PaidCreditGuard(
                enabled=True, mode="manual", budget_usd=0,
                ledger_path=str(tmp_path / "zero.json"),
            )
            assert await zero.select(message(), []) is None
            assert not (tmp_path / "zero.json").exists()
        finally:
            reset_request_model_tier(token)
    asyncio.run(run())


def test_ui_has_explicit_nonpersistent_model_control_and_request_body_field():
    page = render_page("HomeBrain", "0.18.18")
    assert '<select id="modelTier"' in page
    assert '<option value="auto">' in page
    assert '<option value="free">' in page
    assert '<option value="paid">' in page
    assert "model_tier:selectedTier" in page
    assert "const selectedTier=modelTier.value;" in page
    assert "modelTier.onchange=describeModelTier" in page
    assert "localStorage.setItem('hmcp_model_tier'" not in page
    assert "sessionStorage.setItem('hmcp_model_tier'" not in page
    assert "request_model_tier" not in page


def test_free_tier_does_not_fallback_to_paid_on_actual_provider_quota_response(tmp_path):
    from chat_transport import ChatTransport
    import httpx

    async def run():
        ledger = str(tmp_path / "credits.json")
        transport = ChatTransport(
            api_key="test-credential", base_url="https://ollama.com",
            paid_routing_enabled=True, paid_routing_mode="paid",
            paid_budget_usd=3, free_quota_paid_fallback_enabled=True,
        )
        transport.paid_credit_guard.path = Path(ledger)
        attempts = []
        async def reject_free(_messages, _tools, **params):
            attempts.append(params["model_name"])
            request = httpx.Request("POST", "https://ollama.com/api/chat")
            response = httpx.Response(
                402, json={"code": "free_quota_exhausted"}, request=request,
            )
            raise httpx.HTTPStatusError(
                "Free quota exhausted", request=request, response=response,
            )
        transport._chat_round = reject_free
        selected = set_request_model_tier("free")
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await transport._try_cloud_accounts(message(), [])
            assert attempts == ["gemma4:31b"]
            assert not Path(ledger).exists()
        finally:
            reset_request_model_tier(selected)
            await transport.close()

    asyncio.run(run())
