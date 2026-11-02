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
from evidence_first_checkpoint_plan import select_evidence_checkpoint


def select_issuing_app_log_obligation(
    question: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Select at most one proven issuer's app-log request.

    The existing planners already reject ambiguous device/app identities,
    prior attempted app queries and unverified timestamps. Preserve their
    scopes and fail closed rather than silently broadening a query.
    """
    # Both source-specific planners retain their strict evidence admission.
    # The generic selector only orders already-admitted read obligations;
    # it does not invent an issuer, query or permission.
    candidates = []
    historical = pending_provenance_app_log_read(question, receipts)
    if historical is not None:
        candidates.append({
            "kind": "issuer-decision",
            "signature": "historical-issuer-decision",
            "verified": True, "available": True, "read_only": True,
            "tool": historical["tool"], "args": historical["args"],
        })
    method = pending_command_app_decision_log(question, receipts)
    if method is not None:
        candidates.append({
            "kind": "issuer-decision",
            "signature": "method-issuer-decision",
            "verified": True, "available": True, "read_only": True,
            "tool": method["tool"], "args": method["args"],
        })
    # Preserve incident-time command priority even though both represent
    # one source class. Avoid alphabetical signature ordering as a proxy
    # for the upstream evidence strength.
    selected = select_evidence_checkpoint(
        candidates[:1] if historical is not None else candidates
    )
    if selected is None:
        return None
    return {
        "kind": ("incident-command-provenance"
                 if selected["signature"] == "historical-issuer-decision"
                 else "typed-command-app-decision"),
        "tool": selected["tool"],
        "args": selected["args"],
    }


__all__ = ["select_issuing_app_log_obligation"]
