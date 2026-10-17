"""Request progress, safe timeouts, and sensitive URL logging guards."""
from __future__ import annotations

import contextvars
import logging
import re
import time
from dataclasses import dataclass, field
from copy import copy, deepcopy
from typing import Any

_ACTIVE: contextvars.ContextVar["RequestProgress | None"] = contextvars.ContextVar(
    "homebrain_active_progress", default=None
)
_SECRET = re.compile(r"(?i)(access_token|api_key|token)=([^&\s\"']+)")
_AUTH = re.compile(r"(?i)(Authorization:\s*Bearer\s+)\S+")


class SensitiveUrlFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        cleaned = _AUTH.sub(r"\1[REDACTED]", _SECRET.sub(r"\1[REDACTED]", rendered))
        if rendered != cleaned:
            record.msg = cleaned
            record.args = ()
        return True


def install_sensitive_log_redaction() -> None:
    for name in ("httpx", "httpx._client", "HomeBrainOS"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, SensitiveUrlFilter) for item in logger.filters):
            logger.addFilter(SensitiveUrlFilter())


@dataclass
class RequestProgress:
    request_id: str
    stage: str = "Starting request"
    started: float = field(default_factory=time.monotonic)
    checkpoint: Any = None
    verified_reads: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "stage": self.stage,
            "elapsed_seconds": round(time.monotonic() - self.started, 1),
            "completed": self.completed,
        }


def begin_progress(progress: RequestProgress) -> contextvars.Token:
    return _ACTIVE.set(progress)


def end_progress(token: contextvars.Token) -> None:
    _ACTIVE.reset(token)


def set_request_stage(stage: str) -> None:
    state = _ACTIVE.get()
    if state:
        state.stage = stage


def remember_verified_outcome(outcome: Any) -> None:
    state = _ACTIVE.get()
    if state:
        state.checkpoint = outcome


def remember_verified_read_receipt(receipt: dict[str, Any]) -> None:
    """Keep a bounded, redacted read trail before the agent's final answer.

    Recording does not assert that the requested historical/causal question
    was resolved. Mutations, failures, and untrusted model output are excluded.
    """
    state = _ACTIVE.get()
    if (
        state is not None
        and len(state.verified_reads) < 64
        and isinstance(receipt, dict)
        and receipt.get("success") is True
        and receipt.get("mutates") is False
        and receipt.get("effect") == "read"
    ):
        state.verified_reads.append(deepcopy(receipt))


def safe_partial_outcome(
    outcome: Any, *, reason: str,
    additional_reads: list[dict[str, Any]] | None = None,
) -> Any:
    """Only expose successful read receipts; drop unverified model prose."""
    safe = copy(outcome)
    receipts = [
        deepcopy(row) for row in (getattr(outcome, "evidence", None) or [])
        if isinstance(row, dict) and row.get("success") is True
        and row.get("mutates") is False
        and row.get("effect") in ("read", None)
    ]
    for row in additional_reads or []:
        if (
            isinstance(row, dict) and row.get("success") is True
            and row.get("mutates") is False and row.get("effect") == "read"
            and row not in receipts and len(receipts) < 64
        ):
            receipts.append(deepcopy(row))
    proven = sorted({
        str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or
            row.get("tool") or "")
        for row in receipts if row.get("success") is True
    } - {""})
    safe.message = (
        f"**Investigation stopped after {reason}.** The AI analysis did not finish; "
        "no optimisation or repair recommendations have been verified.\n\n"
        + ("Completed read-only checks: " + ", ".join(proven) + "."
           if proven else "No successful source reads could be verified.")
        + "\nThe source evidence is retained in Technical details. "
          "Retry a smaller investigation to receive recommendations."
    )
    safe.route = "investigation-timeout"
    safe.evidence = receipts
    safe.choices = []
    safe.confirmation_required = False
    return safe


def safe_receipt_partial_outcome(
    verified_reads: list[dict[str, Any]], *, reason: str,
) -> Any:
    """Make an evidence-only partial answer when cancellation beats synthesis.

    Import lazily: the orchestrator can import request_runtime itself.
    """
    from mcp_agent_orchestrator import AgentOutcome
    evidence_only = AgentOutcome(
        message="", request_class="live-read",
        evidence=list(verified_reads), choices=[],
    )
    return safe_partial_outcome(evidence_only, reason=reason)
