"""Safeguards for explicit free-tier quota paid fallback."""
import asyncio
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from provider_rate_limit_policy import confirmed_free_allowance_exhaustion
from paid_model_routing import PaidCreditGuard


def error(status, payload):
    request = httpx.Request("POST", "https://ollama.com/api/chat")
    response = httpx.Response(status, json=payload, request=request)
    return httpx.HTTPStatusError("Provider rejected request", request=request, response=response)


def test_exact_quota_signal_only():
    assert confirmed_free_allowance_exhaustion(error(429, {"error":{"code":"free_tier_quota_exhausted"}}))
    assert confirmed_free_allowance_exhaustion(error(402, {"code":"free_quota_exhausted"}))
    for status, body in [(429, {"error":"Free allowance exceeded"}),
                         (429, {"error":{"code":"rate_limit_exceeded"}}),
                         (401, {"code":"free_tier_quota_exhausted"}),
                         (403, {"code":"free_quota_exhausted"}),
                         (500, {"code":"free_quota_exhausted"}),
                         (429, {"error":{"message":"quota exceeded"}})]:
        assert not confirmed_free_allowance_exhaustion(error(status, body))
    assert not confirmed_free_allowance_exhaustion(TimeoutError("timeout"))


def test_fallback_requires_optin_and_available_budget(tmp_path):
    async def run():
        messages = [{"role":"user","content":"Are lights on?"}]
        path = str(tmp_path / "usage.json")
        disabled = PaidCreditGuard(enabled=False, ledger_path=path)
        assert await disabled.select_fallback(messages, []) is None
        assert not Path(path).exists()
        tiny = PaidCreditGuard(enabled=True, budget_usd=0.001, ledger_path=path)
        assert await tiny.select_fallback(messages, []) is None
        allowed = PaidCreditGuard(enabled=True, budget_usd=0.25, ledger_path=path)
        assert await allowed.select_fallback(messages, []) == "deepseek-v4-pro"
    asyncio.run(run())
