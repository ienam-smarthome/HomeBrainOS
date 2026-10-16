"""Opt-in, conservative Ollama paid-model selection and estimated spend guard.

The ledger reserves an estimated upper-bound *before* each paid model round.
It is not an Ollama billing limit: provider accounting and reasoning-token
usage may differ. Leave Ollama auto-reload disabled and monitor vendor usage.
Never log prompts, account keys or raw evidence.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re

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
    mode = str(mode or "hybrid").lower()
    if mode not in {"hybrid", "manual", "paid"}:
        return None
    question = next(
        (str(m.get("content") or "") for m in reversed(messages)
         if m.get("role") == "user" and isinstance(m.get("content"), str)), ""
    )
    if mode == "manual":
        if not re.search(r"\b(use paid model|premium model|paid investigation)\b", question, re.I):
            return None
        return "deepseek-v4-pro"
    # Avoid spending on routine writes even if a user asks "why" rhetorically.
    if re.search(r"^\s*(turn |switch |set |lock |unlock |block |allow )", question, re.I):
        return None
    if mode == "paid" or _COMPLEX.search(question):
        return "deepseek-v4-pro"
    if _MEDIUM.search(question):
        return "deepseek-v4.1-flash"
    return None


class PaidCreditGuard:
    """Single-process conservative reservation counter backed by /data JSON."""

    def __init__(self, *, enabled: bool, mode: str = "hybrid",
                 budget_usd: float = 6.50,
                 ledger_path: str = "/data/ollama_paid_usage.json"):
        self.enabled = bool(enabled)
        self.mode = mode
        self.budget_usd = max(0.0, float(budget_usd))
        self.path = Path(ledger_path)
        self._lock = asyncio.Lock()

    async def select(self, messages: list[dict], tools: list[dict]) -> str | None:
        if not self.enabled or self.budget_usd <= 0:
            return None
        model = choose_paid_model(messages, self.mode)
        if not model:
            return None
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
            except FileNotFoundError:
                spent = 0.0
            except (ValueError, TypeError):
                # Corrupted ledger must fail closed rather than resetting spend.
                return None
            if spent + reservation > self.budget_usd:
                return None
            updated = {"reserved_usd": round(spent + reservation, 8),
                       "reservation_count": 0}
            try:
                old = json.loads(self.path.read_text(encoding="utf-8"))
                updated["reservation_count"] = int(old.get("reservation_count", 0)) + 1
            except FileNotFoundError:
                updated["reservation_count"] = 1
            except (ValueError, TypeError):
                return None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(updated), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                return None
        return model
