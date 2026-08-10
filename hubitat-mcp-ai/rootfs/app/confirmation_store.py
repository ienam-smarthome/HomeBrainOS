from __future__ import annotations

import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from request_metrics import increment_active_metric


CONFIRM_WORDS = {
    "confirm",
    "confirmed",
    "proceed",
    "yes",
    "yes proceed",
    "do it",
}


@dataclass(slots=True)
class PendingConfirmation:
    expires_at: float
    # Every tool call from the originating round, in the model's original
    # order -- not just the sensitive ones. A round is only queued here at
    # all if it contained at least one sensitive call, but any routine calls
    # riding along in the same round must replay too once confirmed, or they
    # are silently dropped and their tool_call_id is left unanswered in the
    # replayed message history.
    actions: list[tuple[str, dict[str, Any]]]
    messages: list[dict[str, Any]]
    assistant_message: dict[str, Any]


class ConfirmationStore:
    """Keep a short-lived, full tool-calling round isolated by session."""

    def __init__(
        self,
        ttl_seconds: float = 120,
        *,
        max_pending_sessions: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = max(10.0, float(ttl_seconds))
        self.max_pending_sessions = max(1, int(max_pending_sessions))
        self._clock = clock
        self._pending: dict[str, PendingConfirmation] = {}

    @property
    def pending(self) -> dict[str, PendingConfirmation]:
        """Compatibility view for diagnostics and existing tests."""

        self._purge_expired()
        return self._pending

    def queue(
        self,
        session_id: str,
        actions: list[tuple[str, dict[str, Any]]],
        messages: list[dict[str, Any]],
        assistant_message: dict[str, Any],
    ) -> PendingConfirmation:
        self._purge_expired()
        session_key = self._normalize_session_id(session_id)
        if (
            session_key not in self._pending
            and len(self._pending) >= self.max_pending_sessions
        ):
            oldest = min(
                self._pending,
                key=lambda key: self._pending[key].expires_at,
            )
            self._pending.pop(oldest, None)
            # Observability only: an evicted session's confirmation is
            # silently lost under sustained pending-session pressure. This
            # does not affect the current request's own outcome
            # classification (the eviction targets a different session's
            # entry, not this request's), it's purely a passive counter so
            # sustained eviction pressure is visible in the technical
            # metrics panel instead of going unnoticed.
            increment_active_metric("confirmation_evicted")
        pending = PendingConfirmation(
            expires_at=self._clock() + self.ttl_seconds,
            actions=deepcopy(actions),
            messages=deepcopy(messages),
            assistant_message=deepcopy(assistant_message),
        )
        self._pending[session_key] = pending
        return pending

    def consume(
        self,
        session_id: str,
        prompt: str,
    ) -> PendingConfirmation | None:
        self._purge_expired()
        pending = self._pending.pop(self._normalize_session_id(session_id), None)
        if pending is None:
            return None
        normalized = " ".join(str(prompt).strip().casefold().split())
        return pending if normalized in CONFIRM_WORDS else None

    def cancel(self, session_id: str) -> None:
        self._pending.pop(self._normalize_session_id(session_id), None)

    @staticmethod
    def _normalize_session_id(session_id: str) -> str:
        # confirmation_policy.py normalizes session_id with str(...).strip()
        # before comparing; this store previously used a bare str(...),
        # so a caller passing incidental leading/trailing whitespace on the
        # session id would queue/consume/cancel under a key that never
        # matches the policy layer's own normalized comparison. Match the
        # same normalization here so both layers agree on the same key for
        # the same session id.
        return str(session_id).strip()

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [
            session_id
            for session_id, pending in self._pending.items()
            if pending.expires_at <= now
        ]
        for session_id in expired:
            self._pending.pop(session_id, None)
        if expired:
            increment_active_metric("confirmation_expired", len(expired))
