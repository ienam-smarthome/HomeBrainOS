"""One read-only app-log source obligation per investigation finalization.

Reuses existing strict source-backed historical and typed-method planners. An
app-log request requires positive provenance to an observed issuing app; no
target ID, issuer, date, or mutation authority is invented here. Historical
incident-time obligations have precedence over generic latest method commands.
"""
from __future__ import annotations

from typing import Any

from provenance_app_log_planner import pending_provenance_app_log_read
from method_command_source_contract import pending_command_app_decision_log


def select_issuing_app_log_obligation(
    question: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Select at most one proven issuer's app-log request.

    The existing planners already reject ambiguous device/app identities,
    prior attempted app queries and unverified timestamps. Preserve their
    scopes and fail closed rather than silently broadening a query.
    """
    historical = pending_provenance_app_log_read(question, receipts)
    if historical is not None:
        return {
            "kind": "incident-command-provenance",
            "tool": historical["tool"],
            "args": dict(historical["args"]),
        }
    method = pending_command_app_decision_log(question, receipts)
    if method is not None:
        return {
            "kind": "typed-command-app-decision",
            "tool": method["tool"],
            "args": dict(method["args"]),
        }
    return None


__all__ = ["select_issuing_app_log_obligation"]
