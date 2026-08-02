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
    actions: list[tuple[str, dict[str, Any]]]
    messages: list[dict[str, Any]]
    assistant_message: dict[str, Any]


class ConfirmationStore:
    """Keep short-lived sensitive actions isolated by session."""

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
        session_key = str(session_id)
        if (
            session_key not in self._pending
            and len(self._pending) >= self.max_pending_sessions
        ):
            oldest = min(
                self._pending,
                key=lambda key: self._pending[key].expires_at,
            )
            self._pending.pop(oldest, None)
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
        pending = self._pending.pop(str(session_id), None)
        if pending is None:
            return None
        normalized = " ".join(str(prompt).strip().casefold().split())
        return pending if normalized in CONFIRM_WORDS else None

    def cancel(self, session_id: str) -> None:
        self._pending.pop(str(session_id), None)

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
