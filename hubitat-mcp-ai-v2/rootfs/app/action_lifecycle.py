"""HomeBrainOS V2 native-action lifecycle for truthful client UX.

Evidence only: the requested action kind, offered UI gate, selected actual
native tools and submitted ORIGINAL receipts. Never parses assistant prose
into operations, never dispatches a write and never authorises approval.
"""
from __future__ import annotations

from typing import Any

from control_surface_recovery import is_explicit_device_imperative
from write_receipt_evidence import original_native_accepted


_NO_ACTION_NOTE = (
    "No native device action was selected or submitted and no approval "
    "card is pending. Prepare action starts a NEW request with fresh "
    "native evidence; a model-selected write would still require explicit "
    "same-request UI approval. If the requested condition already holds, "
    "do not repeat a state-changing command merely to create a card."
)


def inspect_action_lifecycle(
    question: str,
    receipts: list[dict[str, Any]],
    *,
    native_write_submitted: bool,
    native_write_selected: bool,
    ui_approval_available: bool,
) -> dict[str, Any]:
    """Mark actual call/acceptance separately from a valid model reply.

    The caller supplies `native_write_submitted` only when the native MCP
    transport was genuinely entered, not merely a proposed/approved call.
    An absent receipt is never evidence that a future operation did not run.
    """
    direct = is_explicit_device_imperative(question)
    if not direct:
        return {
            "status": "not_applicable", "native_write_submitted": bool(native_write_submitted),
            "native_write_accepted": None, "approval_pending": False,
        }
    if native_write_submitted:
        outcomes = [
            original_native_accepted(record)
            for record in receipts
            if isinstance(record, dict)
            and record.get("result_kind") == "tool_result"
            and record.get("possible_native_action") is True
        ]
        acceptance = (
            True if True in outcomes
            else False if outcomes and all(item is False for item in outcomes)
            else None
        )
        return {
            "status": (
                "native_accepted" if acceptance is True
                else "native_rejected" if acceptance is False
                else "native_result_unverified"
            ),
            "native_write_submitted": True,
            "native_write_accepted": acceptance,
            "approval_pending": False,
            "independent_future_outcome_verified": False,
            "note": (
                "The original native MCP result is not proof of a later "
                "physical or network effect. Review receipts and any "
                "separate readback before asserting one."
            ),
        }
    if native_write_selected:
        # Could have been explicitly declined, rejected by the contract, or
        # failed before submission. Never auto-prepare/retry uncertain writes.
        return {
            "status": "native_write_not_submitted",
            "native_write_submitted": False,
            "native_write_accepted": False,
            "approval_pending": False,
            "note": (
                "A native write was selected but was not submitted. "
                "It may have been declined or failed before dispatch; "
                "inspect the original receipt. Never replay it automatically."
            ),
        }
    return {
        "status": "not_prepared",
        "native_write_submitted": False,
        "native_write_accepted": False,
        "approval_pending": False,
        "model_answer_is_not_approval": True,
        "ui_prepare_available": bool(ui_approval_available),
        "note": _NO_ACTION_NOTE,
    }


def unprepared_action_choices(
    lifecycle: dict[str, Any],
    *,
    ui_approval_available: bool,
) -> dict[str, Any] | None:
    """UI choices require NO selected/attempted native write, no text tests."""
    if (not ui_approval_available
            or lifecycle.get("status") != "not_prepared"):
        return None
    return {
        "status": "unprepared_confirmation",
        "options": ["prepare_action", "edit_request", "dismiss"],
        "native_write_queued": False,
        "approval_pending": False,
        "reason": "no_native_write_selected",
        "note": lifecycle["note"],
    }


def unprepared_answer(lifecycle: dict[str, Any], original: str) -> str:
    """Prevent a free-text plan from masquerading as an actionable approval."""
    if lifecycle.get("status") != "not_prepared":
        return original
    return (
        "**No action queued.** No device command was sent. "
        "Choose **Prepare action**, **Edit request**, or **Dismiss** below. "
        "Any new write still requires its own explicit approval."
    )
