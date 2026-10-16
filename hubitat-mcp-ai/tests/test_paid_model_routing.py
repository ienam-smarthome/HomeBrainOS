"""Regression tests for opt-in paid Ollama model routing."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from paid_model_routing import PaidCreditGuard, choose_paid_model


def msg(prompt):
    return [{"role": "user", "content": prompt}]


def test_complex_and_medium_routing():
    assert choose_paid_model(msg("Investigate why the bedroom light came on"), "hybrid") == "deepseek-v4-pro"
    assert choose_paid_model(msg("Analyse conflicting evidence"), "hybrid") == "deepseek-v4-pro"
    assert choose_paid_model(msg("Show rule history"), "hybrid") == "deepseek-v4.1-flash"
    assert choose_paid_model(msg("Is the hallway light on?"), "hybrid") is None


def test_manual_and_mutation_safeguards():
    assert choose_paid_model(msg("Investigate the lights"), "manual") is None
    assert choose_paid_model(msg("Use paid model to check lights"), "manual") == "deepseek-v4-pro"
    assert choose_paid_model(msg("Turn the lights off and tell me why"), "hybrid") is None


def test_opt_in_and_budget(tmp_path):
    async def run():
        ledger = tmp_path / "credits.json"
        guard = PaidCreditGuard(enabled=False, ledger_path=str(ledger))
        assert await guard.select(msg("Investigate the light"), []) is None
        assert not ledger.exists()
        guard = PaidCreditGuard(enabled=True, budget_usd=0.01, ledger_path=str(ledger))
        assert await guard.select(msg("Investigate the light"), []) is None
        assert not ledger.exists()
        guard = PaidCreditGuard(enabled=True, budget_usd=1.0, ledger_path=str(ledger))
        assert await guard.select(msg("Investigate the light"), []) == "deepseek-v4-pro"
        previous = json.loads(ledger.read_text())
        assert previous["reserved_usd"] > 0
        assert previous["reservation_count"] == 1
    asyncio.run(run())


def test_corrupt_ledger_fails_closed(tmp_path):
    async def run():
        ledger = tmp_path / "credits.json"
        ledger.write_text("invalid JSON")
        guard = PaidCreditGuard(enabled=True, ledger_path=str(ledger))
        assert await guard.select(msg("Investigate light"), []) is None
    asyncio.run(run())


def test_concurrent_rounds_reserve_atomically(tmp_path):
    async def run():
        ledger = tmp_path / "credits.json"
        guard = PaidCreditGuard(enabled=True, budget_usd=0.10, ledger_path=str(ledger))
        answers = await asyncio.gather(*[
            guard.select(msg("Investigate conflicting light events"), []) for _ in range(5)
        ])
        reserved = json.loads(ledger.read_text())
        assert sum(answer is not None for answer in answers) == reserved["reservation_count"]
        assert reserved["reserved_usd"] <= 0.10
    asyncio.run(run())
