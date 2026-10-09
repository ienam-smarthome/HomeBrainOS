"""Request progress, safe timeouts, and sensitive URL logging guards."""
from __future__ import annotations

import contextvars
import logging
import re
import time
from dataclasses import dataclass, field
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


def safe_partial_outcome(outcome: Any, *, reason: str) -> Any:
    """Only expose successful source reads; drop unverified model prose."""
    from copy import copy
    safe = copy(outcome)
    receipts = [
        dict(row) for row in (getattr(outcome, "evidence", None) or [])
        if isinstance(row, dict)
    ]
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
