"""Request-scoped command issuer evidence contract for recent device transitions.

This module produces NO causal answer and performs NO tool calls. State reports,
downstream listener subscriptions, log completion rows, and real command event
issuers have distinct identities. A post-event command completion is not the
same as a source-timed issued-command witness.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping

from skill_source_completion import pending_recent_focal_command_read


def _args(row: Mapping[str, Any]) -> dict[str, Any]:
    args = row.get("arguments")
    if not isinstance(args, dict):
        return {}
    return args.get("args") if isinstance(args.get("args"), dict) else args


def _at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def recent_command_issuer_sources(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Bind any source-timed command to one independently resolved target.

    A successful query of command-off checks the source CLASS; the source may
    be empty or truncated and never certifies an actual issuer without its
    typed event record. A generic hub log has no attested command identity.
    """
    verified: dict[str, str] = {}
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("evidence_kind") != "targeted_device_lookup":
            continue
        details = row.get("details")
        state = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if not isinstance(state, dict):
            continue
        ident, label = str(state.get("deviceId") or ""), str(state.get("label") or "")
        if ident.isdecimal() and label.strip() and label.casefold() in request.casefold():
            verified[ident] = label
    if len(verified) != 1:
        return None
    ident, label = next(iter(verified.items()))
    observed: list[tuple[datetime, str]] = []
    for row in receipts:
        if not isinstance(row, dict):
            continue
        if row.get("tool") != "homebrain_device_history" or row.get("success") is not True:
            continue
        details, args = row.get("details"), _args(row)
        if not isinstance(details, dict) or str(details.get("label") or "").casefold() != label.casefold():
            continue
        if str(args.get("name") or "").casefold() != label.casefold():
            continue
        for event in (details.get("observedEvents") or [])[:150]:
            if not isinstance(event, dict) or event.get("name") != "switch":
                continue
            action = str(event.get("value") or "").lower()
            at = _at(event.get("date"))
            if action in ("off", "on") and at is not None:
                observed.append((at, action))
    if not observed:
        return None
    requested = re.search(
        r"(?i)\b(?:turned|went|switched|turn|switch|turning)\s+(off|on)\b"
        r"|\b(off|on)\s+commands?\b|\bcommands?\s+(off|on)\b",
        request,
    )
    if requested is None:
        return None
    action = next((group.lower() for group in requested.groups() if group), "")
    events_for_action = [event for event in observed if event[1] == action]
    if not events_for_action:
        return None
    when, _ = max(events_for_action, key=lambda x: x[0])
    if not pending_recent_focal_command_read(request, receipts) and not any(
        # Read may already have run; only accept causal last-event requests.
        isinstance(row, dict)
        and str(_args(row).get("deviceId") or "") == ident
        and str(_args(row).get("attribute") or "").lower() == f"command-{action}"
        for row in receipts
    ):
        return None
    source_checked = False
    command_witnesses: set[tuple[str, str, str]] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("mutates") is True:
            continue
        if str(row.get("sub_tool") or "") != "hub_list_device_events":
            continue
        args = _args(row)
        if (str(args.get("deviceId") or "") != ident
                or str(args.get("attribute") or "").lower() != f"command-{action}"):
            continue
        if row.get("success") is True:
            source_checked = True
        details = row.get("details")
        if not isinstance(details, dict) or row.get("success") is not True:
            continue
        for name in ("observedEvents", "events", "commandEvents"):
            events = details.get(name)
            if not isinstance(events, list):
                continue
            for event in events[:100]:
                if not isinstance(event, dict) or event.get("name") != f"command-{action}":
                    continue
                actor = event.get("producedBy")
                actor = actor if isinstance(actor, dict) else {}
                app_id = str(actor.get("appId") or "")
                dt = _at(event.get("date"))
                if app_id.isdecimal() and dt is not None:
                    command_witnesses.add((dt.isoformat(), app_id, str(actor.get("name") or "")[:90]))
    witnesses = []
    for timestamp, app_id, app_label in sorted(command_witnesses)[-6:]:
        dt = _at(timestamp)
        delta = round((dt - when).total_seconds(), 3) if dt else None
        witnesses.append({
            "commandTimeUtc": timestamp,
            "recordedCommandAppId": app_id,
            "recordedCommandAppLabel": app_label,
            "secondsRelativeToStateReport": delta,
            "observedCommand": action,
            "causalEffectVerified": False,
        })
    return {
        "schema": "homebrain-recent-issuer-source.v1",
        "targetDeviceId": ident,
        "focalState": action,
        "focalStateReportedAtUtc": when.isoformat(),
        "commandHistorySourceChecked": source_checked,
        "recordedCommandWitnesses": witnesses,
        "commandIssuerVerifiedByTypedSource": bool(witnesses),
        "reportingBridgeIsNotIssuerProof": True,
        "notifiedAppsAreNotIssuerProof": True,
        "unscopedLogCompletionIsNotIssuerProof": True,
        "sourceHistoryIsNotComplete": True,
    }


def render_recent_command_issuer_sources(
    request: str, receipts: list[dict[str, Any]],
) -> str | None:
    facts = recent_command_issuer_sources(request, receipts)
    if facts is None:
        return None
    return (
        "HOST COMMAND-ISSUER SOURCE VERDICT — SOURCE FACTS, NOT MODEL ANSWER:\n"
        + json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        + "\nCausal publication rule: ONLY a target-scoped typed command event "
          "with an app producer identifies a recorded Hubitat command issuer. "
          "A separate generic app log mentioning command completion, particularly "
          "AFTER the state report, does NOT certify the issuing app or establish "
          "that this log caused the earlier reported OFF/ON transition. "
          "If no typed command witnesses are returned, explicitly say the "
          "issuer and reason remain unverified rather than naming a controller "
          "as the most likely cause. A timed command record verifies only "
          "the recorded invocation, not delivery, physical effect, upstream "
          "trigger or full historical coverage."
    )


__all__ = ["recent_command_issuer_sources", "render_recent_command_issuer_sources"]
