"""Read-only diagnostics of HomeBrain's estimated paid-model budget guard."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from paid_model_routing import PaidCreditGuard, set_original_paid_request, reset_original_paid_request
from request_metrics import RequestMetrics
from api_response_builder import build_agent_response


def _attempt(tmp_path, *, budget, ledger=None):
    async def run():
        ledger_path = tmp_path / "paid-ledger.json"
        if ledger is not None:
            ledger_path.write_text(ledger, encoding="utf-8")
        metrics = RequestMetrics()
        metrics_token = metrics.begin()
        intent_token = set_original_paid_request("Use paid model. Explain app 4019 lockout. Read-only.")
        try:
            guard = PaidCreditGuard(
                enabled=True, mode="manual", budget_usd=budget,
                ledger_path=str(ledger_path),
            )
            model = await guard.select(
                [{"role": "user", "content": "HOST evidence summary"}], []
            )
            return model, metrics.snapshot(), ledger_path
        finally:
            reset_original_paid_request(intent_token)
            metrics.reset(metrics_token)
    return asyncio.run(run())


def test_round_over_budget_reports_exact_safe_estimate(tmp_path):
    model, snapshot, path = _attempt(tmp_path, budget=0.01)
    assert model is None
    guard = snapshot["paid_guard"]
    assert guard["status"] == "round_exceeds_budget"
    assert guard["configured_budget_usd"] == 0.01
    assert guard["estimated_round_usd"] > guard["remaining_estimated_budget_usd"]
    assert guard["already_reserved_usd"] == 0
    assert not path.exists()


def test_existing_reservations_not_erased_or_recredited(tmp_path):
    starting = json.dumps({"reserved_usd": 0.49, "reservation_count": 3})
    model, snapshot, path = _attempt(tmp_path, budget=0.5, ledger=starting)
    assert model is None
    assert snapshot["paid_guard"]["status"] == "round_exceeds_budget"
    assert snapshot["paid_guard"]["already_reserved_usd"] == 0.49
    assert json.loads(path.read_text(encoding="utf-8"))["reservation_count"] == 3
    assert json.loads(path.read_text(encoding="utf-8"))["reserved_usd"] == 0.49


def test_corrupt_ledger_fails_closed_without_replacement(tmp_path):
    model, snapshot, path = _attempt(tmp_path, budget=1.0, ledger="{invalid")
    assert model is None
    assert snapshot["paid_guard"]["status"] == "invalid_ledger"
    assert path.read_text(encoding="utf-8") == "{invalid"


def test_nonfinite_ledger_fails_closed(tmp_path):
    model, snapshot, path = _attempt(
        tmp_path, budget=1.0, ledger='{"reserved_usd": NaN, "reservation_count": 10}'
    )
    assert model is None
    assert snapshot["paid_guard"]["status"] == "invalid_ledger"
    assert path.exists()


def test_successful_reservation_returns_estimate_without_tokens_or_keys(tmp_path):
    model, snapshot, path = _attempt(tmp_path, budget=1.0)
    assert model == "deepseek-v4-pro"
    assert snapshot["paid_guard"]["status"] == "reserved"
    assert snapshot["paid_guard"]["already_reserved_usd"] > 0
    assert "HOST" not in str(snapshot)
    assert "/data" not in str(snapshot)
    assert json.loads(path.read_text(encoding="utf-8"))["reservation_count"] == 1


def test_response_exposes_specific_block_reason():
    outcome = SimpleNamespace(
        message="Evidence shows a 300-minute saved value.",
        route="unified-mcp-agent",
        request_class="live-read",
        choices=[], evidence=[], confirmation_required=False, confirmation_count=0,
        automation_items=[], investigation_coverage=None,
        metrics={
            "outcome": "success",
            "counters": {"paid_model_requested": 1, "paid_routing_reservation_blocked": 2},
            "timings_ms": {},
            "model_round_details": [{"model": "gemma4:31b", "provider": "ollama-cloud"}],
            "paid_guard": {
                "status": "round_exceeds_budget",
                "configured_budget_usd": 0.5,
                "already_reserved_usd": 0.49,
                "remaining_estimated_budget_usd": 0.01,
                "estimated_round_usd": 0.1,
            },
        },
    )
    response = build_agent_response(outcome, model="gemma4:31b", elapsed_ms=100, version="0.18.2")
    assert response["paid_routing"]["reason"] == "estimated_round_exceeds_local_budget"
    assert response["paid_routing"]["local_guard"]["remaining_estimated_budget_usd"] == 0.01
    assert response["paid_routing"]["used"] is False
    assert response["model"] == "gemma4:31b"
