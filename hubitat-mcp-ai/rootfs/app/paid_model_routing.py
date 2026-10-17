"""Per-request Ollama model routing with an optional legacy spend guard.

Production HomeBrain now uses no local cumulative budget or reservation ledger:
Ollama account credit and auto-reload settings control billing. Older explicit
guard users/tests may still provide a finite budget. Never log account keys,
prompts, or raw evidence.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
import json
import math
import os
from pathlib import Path
import re

from request_metrics import increment_active_metric, record_active_paid_guard

# Only the real request sets this context. Do not infer consent from host-added
# role=user instructions, tool text, or historic conversation messages.
_ORIGINAL_PAID_REQUEST: ContextVar[str | None] = ContextVar(
    'homebrain_original_paid_request', default=None
)
# Explicit selection is scoped to one API request, never shared between
# concurrent sessions. "auto" leaves existing manual/hybrid mode untouched.
_REQUEST_MODEL_TIER: ContextVar[str] = ContextVar(
    'homebrain_request_model_tier', default='free'
)


def set_request_model_tier(tier: str) -> Token:
    if tier not in ('auto', 'free', 'paid', 'claude'):
        raise ValueError('Unsupported request model tier')
    return _REQUEST_MODEL_TIER.set(tier)


def reset_request_model_tier(token: Token) -> None:
    _REQUEST_MODEL_TIER.reset(token)


def request_model_tier() -> str:
    return _REQUEST_MODEL_TIER.get()

_EXPLICIT_PAID = re.compile(r'\b(use paid model|premium model|paid investigation)\b', re.I)


def set_original_paid_request(prompt: str) -> Token:
    return _ORIGINAL_PAID_REQUEST.set(str(prompt or ''))


def reset_original_paid_request(token: Token) -> None:
    _ORIGINAL_PAID_REQUEST.reset(token)


def explicit_paid_request() -> bool:
    tier = request_model_tier()
    if tier == 'free':
        return False
    if tier in ('paid', 'claude'):
        return True
    text = _ORIGINAL_PAID_REQUEST.get()
    return bool(text is not None and _EXPLICIT_PAID.search(text))


# Published per-million token rates supplied by the user, USD.
MODEL_RATES = {
    "deepseek-v4.1-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
    "glm-5.3": (1.40, 4.40),
}
_COMPLEX = re.compile(
    r"\b(why|root.cause|investigat\w*|diagnos\w*|correlat\w*|compar\w*|"
    r"conflict\w*|inconsisten\w*|audit|optimis\w*|optimiz\w*|reason\w*|"
    r"timeline|evidence)\b", re.I
)
_MEDIUM = re.compile(r"\b(rule|automation|schedule|history|log|event|sensor)\b", re.I)


def choose_paid_model(messages: list[dict], mode: str) -> str | None:
    """Prefer free unless a read-only investigation benefits from escalation.

    Paid routing is strictly advisory: tool permission and write-confirmation
    enforcement remain in the existing HomeBrain orchestrator.
    """
    tier = request_model_tier()
    # Per-request selection outranks admin automation modes but NEVER the
    # paid-credit guard, enabled flag, or read/write permission boundaries.
    if tier == "free":
        return None
    if tier == "paid":
        return "deepseek-v4-pro"
    if tier == "claude":
        # Claude is a separate API provider, never an Ollama-paid model.
        return None
    mode = str(mode or "hybrid").lower()
    if mode not in {"hybrid", "manual", "paid"}:
        return None
    original = _ORIGINAL_PAID_REQUEST.get()
    question = original if original is not None else next(
        (str(m.get("content") or "") for m in reversed(messages)
         if m.get("role") == "user" and isinstance(m.get("content"), str)), ""
    )
    if mode == "manual":
        if not _EXPLICIT_PAID.search(question):
            return None
        return "deepseek-v4-pro"
    # Explicit authorised paid use works in hybrid mode too.
    if _EXPLICIT_PAID.search(question):
        return "deepseek-v4-pro"
    # Avoid spending on routine writes even if a user asks "why" rhetorically.
    if re.search(r"^\s*(turn |switch |set |lock |unlock |block |allow )", question, re.I):
        return None
    if mode == "paid" or _COMPLEX.search(question):
        return "deepseek-v4-pro"
    # A lone mention of a device/rule or a simple "show" is not evidence
    # that paid reasoning will add value. Require an analytical action.
    if _MEDIUM.search(question) and re.search(
        r"\b(?:analyse|analyze|summaris\w*|summariz\w*|review|explain|trace|reconstruct|compare)\b",
        question, re.I,
    ):
        return "deepseek-v4.1-flash"
    return None


class PaidCreditGuard:
    """Paid-model gate: production is uncapped, finite legacy guards remain optional."""

    def __init__(self, *, enabled: bool, mode: str = "hybrid",
                 budget_usd: float | None = 6.50,
                 deep_model: str = "deepseek-v4-pro",
                 ledger_path: str = "/data/ollama_paid_usage.json"):
        self.enabled = bool(enabled)
        self.mode = mode
        self.deep_model = deep_model if deep_model in {"deepseek-v4-pro", "glm-5.3"} else "deepseek-v4-pro"
        # None means the HomeBrain add-on has no cumulative local cap.
        # Existing callers supplying a number retain the legacy limiter.
        # The production UI/configuration deliberately passes None.
        self.budget_usd = None if budget_usd is None else max(0.0, float(budget_usd))
        self.path = Path(ledger_path)
        self._lock = asyncio.Lock()

    async def select_fallback(self, messages: list[dict], tools: list[dict]) -> str | None:
        """Reserve credit for an explicitly rejected free-tier request."""
        if request_model_tier() == "free":
            return None
        return await self._reserve(messages, tools, self.deep_model)

    async def select(self, messages: list[dict], tools: list[dict]) -> str | None:
        model = choose_paid_model(messages, self.mode)
        if model is None:
            return None
        if model == "deepseek-v4-pro":
            model = self.deep_model
        if not self.enabled:
            increment_active_metric("paid_routing_disabled")
            record_active_paid_guard("disabled", budget_usd=self.budget_usd)
            return None
        if self.budget_usd is not None and self.budget_usd <= 0:
            increment_active_metric("paid_routing_budget_disabled")
            record_active_paid_guard("zero_budget", budget_usd=self.budget_usd)
            return None
        selected = await self._reserve(messages, tools, model)
        if self.budget_usd is not None:
            increment_active_metric("paid_model_reserved" if selected else "paid_routing_reservation_blocked")
        else:
            increment_active_metric("paid_model_selected" if selected else "paid_routing_disabled")
        return selected

    async def _reserve(self, messages: list[dict], tools: list[dict], model: str | None) -> str | None:
        if not self.enabled or (self.budget_usd is not None and self.budget_usd <= 0) or not model:
            if model:
                record_active_paid_guard("disabled" if not self.enabled else "zero_budget",
                                         budget_usd=self.budget_usd)
            return None
        if model not in MODEL_RATES:
            record_active_paid_guard("unknown_model", budget_usd=self.budget_usd)
            return None
        if self.budget_usd is None:
            # No local budget, ledger reads or persistent spend reservations.
            # Ollama alone handles remaining credits and provider-side charges.
            # Never delete the legacy ledger: it is simply no longer consulted.
            record_active_paid_guard("no_local_budget")
            return model
        # Pessimistic character/token ratio of 1:1 for the complete model
        # packet, including tools. Allow 8,192 output tokens per round.
        # This is a reservation, NOT a confirmed invoice amount.
        chars = len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False))
        input_tokens_reserved = max(1000, chars)
        in_rate, out_rate = MODEL_RATES[model]
        reservation = (input_tokens_reserved * in_rate + 8192 * out_rate) / 1_000_000
        # Reserve before dispatch. Never reimburse a failed or timed-out round:
        # it might already have consumed billable tokens.
        async with self._lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                spent = float(data.get("reserved_usd", 0))
                if not math.isfinite(spent) or spent < 0:
                    raise ValueError("Invalid cumulative reservation total")
            except FileNotFoundError:
                spent = 0.0
            except (ValueError, TypeError):
                # Corrupted ledger must fail closed rather than resetting spend.
                record_active_paid_guard("invalid_ledger", budget_usd=self.budget_usd,
                                         estimated_round_usd=reservation)
                return None
            except OSError:
                record_active_paid_guard("storage_unavailable", budget_usd=self.budget_usd,
                                         estimated_round_usd=reservation)
                return None
            if spent + reservation > self.budget_usd:
                record_active_paid_guard("round_exceeds_budget",
                                         budget_usd=self.budget_usd,
                                         already_reserved_usd=spent,
                                         estimated_round_usd=reservation)
                return None
            updated = {"reserved_usd": round(spent + reservation, 8),
                       "reservation_count": 0}
            try:
                old = json.loads(self.path.read_text(encoding="utf-8"))
                updated["reservation_count"] = int(old.get("reservation_count", 0)) + 1
            except FileNotFoundError:
                updated["reservation_count"] = 1
            except (ValueError, TypeError):
                record_active_paid_guard("invalid_ledger", budget_usd=self.budget_usd,
                                         already_reserved_usd=spent,
                                         estimated_round_usd=reservation)
                return None
            except OSError:
                record_active_paid_guard("storage_unavailable", budget_usd=self.budget_usd,
                                         already_reserved_usd=spent,
                                         estimated_round_usd=reservation)
                return None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(updated), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                record_active_paid_guard("storage_unavailable", budget_usd=self.budget_usd,
                                         already_reserved_usd=spent,
                                         estimated_round_usd=reservation)
                return None
        record_active_paid_guard("reserved", budget_usd=self.budget_usd,
                                 already_reserved_usd=spent + reservation,
                                 estimated_round_usd=reservation)
        return model
