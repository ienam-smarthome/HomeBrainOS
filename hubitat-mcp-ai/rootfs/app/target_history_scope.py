"""Target/source scope integrity for the original model-directed investigator.

A successful location-wide device-event lookup cannot establish absence of
events for particular verified device IDs. This is a source-contract problem,
not a keyword/device-specific answer correction. No tools or writes here.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


def _args(row: Mapping[str, Any]) -> Mapping[str, Any]:
    args = row.get("arguments")
    if not isinstance(args, Mapping):
        return {}
    for _ in range(2):
        inner = args.get("args")
        if not isinstance(inner, Mapping):
            break
        args = inner
    return args


def _read(row: Any) -> bool:
    return (isinstance(row, Mapping) and row.get("success") is True
            and row.get("mutates") is not True
            and row.get("effect") in (None, "read"))


def inspect_target_history_scope(
    question: str, receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Determine *coverage of read identities*, never historical completeness.

    Device IDs must originate from successful exact targeted lookups matching
    the user's named subjects. An unscoped query can supply positive evidence
    but NOT certify a zero-event answer for one of these devices.
    """
    from investigation_policy import is_history_investigation, is_causal_investigation

    if not (is_history_investigation(question) or is_causal_investigation(question)):
        return None
    targets: dict[str, str] = {}
    requested = str(question or "").casefold()
    for row in receipts:
        if not _read(row) or row.get("evidence_kind") != "targeted_device_lookup":
            continue
        details = row.get("details")
        state = details.get("reportedDeviceState") if isinstance(details, Mapping) else None
        if not isinstance(state, Mapping):
            continue
        ident = str(state.get("deviceId") or "")
        label = str(state.get("label") or "").strip()
        args = _args(row)
        filter_label = str(args.get("labelFilter") or "").strip()
        if (ident.isdecimal() and int(ident) > 0 and label
                and label.casefold() in requested
                and filter_label and label.casefold() == filter_label.casefold()):
            targets[ident] = label[:90]
    if not targets:
        return None

    checked: set[str] = set()
    unscoped = 0
    for row in receipts:
        if not _read(row):
            continue
        leaf = str(row.get("sub_tool") or row.get("tool") or "")
        if leaf == "hub_list_device_events":
            ident = str(_args(row).get("deviceId") or "")
            if ident in targets:
                checked.add(ident)
            elif not ident:
                unscoped += 1
        elif row.get("tool") == "homebrain_device_history":
            args = _args(row)
            ident = str(args.get("deviceId") or "")
            details = row.get("details")
            label = str(details.get("label") or "").strip() if isinstance(details, Mapping) else ""
            if ident in targets:
                checked.add(ident)
            elif label:
                matches = [k for k, name in targets.items()
                           if name.casefold() == label.casefold()]
                if len(matches) == 1:
                    checked.add(matches[0])
    missing = sorted(set(targets).difference(checked), key=int)
    return {
        "status": "target-scoped-read-ids-checked" if not missing
                  else "target-scoped-read-ids-missing",
        "verified_targets": [{"deviceId": ident, "label": targets[ident]}
                             for ident in sorted(targets, key=int)],
        "target_scoped_read_ids": sorted(checked, key=int),
        "missing_target_read_ids": missing,
        "unscoped_event_queries": unscoped,
        "history_completeness_proven": False,
        "unscoped_zero_does_not_prove_target_inactivity": True,
    }


def render_target_scope_followup(
    question: str, receipts: Sequence[Mapping[str, Any]],
) -> str | None:
    """Model chooses its own allowed tool, with source-verified target IDs."""
    state = inspect_target_history_scope(question, receipts)
    if not state or not state["missing_target_read_ids"]:
        return None
    unresolved = [r for r in state["verified_targets"]
                  if r["deviceId"] in state["missing_target_read_ids"]]
    scope = ", ".join(r["label"] + " (deviceId=" + r["deviceId"] + ")"
                      for r in unresolved[:8])
    return (
        "HOST HISTORICAL SUBJECT-SCOPE GAP (read-only). The original question "
        "concerns these independently verified devices: " + scope
        + ". No successful device-scoped event-history read exists for "
          "those IDs in the current evidence. "
        + ("A location-wide hub_list_device_events query was performed, "
           "but its empty/summary response cannot establish no activity "
           "for any particular target. " if state["unscoped_event_queries"] else "")
        + "Choose a permitted, bounded READ that explicitly names each "
          "verified deviceId and the requested historical window. Prefer "
          "the installed hub_list_device_events leaf through the approved "
          "gateway or homebrain_device_history if available. If the "
          "source reports no events, distinguish empty returned data from "
          "verified historical completeness. Continue to inputs, command "
          "provenance and app decisions only after the target history is "
          "properly scoped. Do not invent schemas or modify Hubitat. "
          "If source retrieval fails or no safe read is available, return "
          "an explicit coverage limitation, never a zero-event verdict."
    )


_UNIVERSAL_EMPTY = re.compile(
    r"(?i)\b(?:no\s+recorded\s+activity|no\s+(?:state\s+changes|"
    r"switch\s+transitions|commands|events)\s+(?:or\s+commands\s+)?"
    r"(?:were\s+)?recorded|zero\s+events|"
    r"none\s+of\s+(?:these|the)\s+(?:devices|lights)\s+"
    r"(?:had|showed|recorded))\b",
)


def guard_unscoped_target_history_denial(
    message: str, question: str, receipts: Sequence[Mapping[str, Any]],
) -> tuple[str, bool]:
    """Replace unsupported zero-history verdicts at every final API path."""
    original = str(message or "")
    state = inspect_target_history_scope(question, receipts)
    if (not state or not state["missing_target_read_ids"]
            or not _UNIVERSAL_EMPTY.search(original)):
        return original, False
    targets = state["verified_targets"]
    subjects = ", ".join(r["label"] for r in targets[:8])
    missing = ", ".join(state["missing_target_read_ids"])
    return (
        "I couldn't verify the historical ON/OFF activity for " + subjects
        + ". The available event-history query was not scoped to all "
          "requested device IDs; target-specific history is still missing "
          "for deviceId " + missing + ". "
        + ("The location-wide event query is not evidence that these "
           "devices had no activity. " if state["unscoped_event_queries"] else "")
        + "Current device states and automation memberships cannot "
          "establish what happened during the requested historical window. "
          "A bounded, device-specific event and command-history read is "
          "needed before investigating sensor/controller causation. "
          "No devices or rules were changed."
    ), True


__all__ = [
    "inspect_target_history_scope",
    "render_target_scope_followup",
    "guard_unscoped_target_history_denial",
]
