"""Typed method-command provenance and bounded issuing-app decision reads.

A source-scoped Hubitat event history can record command-*other methods*
(e.g. thermostat commands), not only command-on/off. A recorded invocation
does NOT prove the rule's reason, boiler operation or complete command history.
All methods are observation-only; this file never executes a tool.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Mapping


def _args(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("arguments")
    if not isinstance(raw, dict):
        return {}
    return raw.get("args") if isinstance(raw.get("args"), dict) else raw


def _at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _source_label(row: dict[str, Any]) -> str | None:
    """Accept only explicitly device/label-scoped successful history receipts."""
    if row.get("success") is not True or row.get("mutates") is True:
        return None
    if row.get("effect") not in (None, "read"):
        return None
    args = _args(row)
    details = row.get("details")
    if not isinstance(details, dict):
        return None
    op = str(row.get("sub_tool") or "")
    if row.get("tool") == "homebrain_device_history":
        asked = str(args.get("name") or "").strip()
        returned = str(details.get("label") or "").strip()
        if asked and returned and asked.casefold() == returned.casefold():
            return returned
    if op == "hub_list_device_events":
        ident = str(args.get("deviceId") or "")
        if ident.isdecimal() and int(ident) > 0:
            return "device:" + ident
    return None


def typed_method_command_records(
    receipts: list[dict[str, Any]], *, target: str | None = None,
) -> list[dict[str, Any]]:
    """Return attested command invocation records, without invented issuers."""
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for receipt in receipts[:160]:
        if not isinstance(receipt, dict):
            continue
        label = _source_label(receipt)
        if not label:
            continue
        if target is not None and label.casefold() != target.casefold():
            continue
        details = receipt.get("details") or {}
        events = details.get("observedEvents")
        if not isinstance(events, list):
            continue
        for event in events[:200]:
            if not isinstance(event, dict):
                continue
            name = str(event.get("name") or "")
            if (not name.startswith("command-") or len(name) > 100
                    or not re.fullmatch(r"command-[A-Za-z][\w-]*", name)
                    or str(event.get("type") or "").lower() != "command"):
                continue
            at = _at(event.get("date"))
            if at is None:
                continue
            producer = event.get("producedBy")
            producer = producer if isinstance(producer, dict) else {}
            # A numeric producer ID is only a known application when the
            # source explicitly marks it as an app.
            app_id = ""
            if str(producer.get("type") or "").lower() == "app":
                candidate = str(producer.get("appId") or producer.get("id") or "")
                if candidate.isdecimal() and int(candidate) > 0:
                    app_id = candidate
            dedupe = (label.casefold(), at.isoformat(), name)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rows.append({
                "scope": label,
                "name": name,
                "at": at.isoformat(),
                "recordedIssuerAppId": app_id or None,
                "recordedIssuerLabel": str(
                    producer.get("label") or producer.get("name") or ""
                )[:100] if app_id else None,
                "sourceKind": "typed-target-device-event-history",
                "commandRecorded": True,
                "deviceAcknowledgementVerified": False,
                "physicalActuationVerified": False,
                "upstreamAutomationDecisionVerified": False,
            })
    return sorted(rows, key=lambda x: x["at"], reverse=True)[:20]


def _requested_exact_label(request: str, label: str) -> bool:
    """Do not bind a short label inside a different compound device name.

    A preceding title-case token may belong to the real device label, which
    this receipt did not verify. Prefer no inferred app log to a wrong device.
    This is deliberately conservative for partial label matches.
    """
    pattern = r"(?<![\\w-])" + re.escape(label) + r"(?![\\w-])"
    for match in re.finditer(pattern, request, re.I):
        before = request[:match.start()]
        prefix = re.search(r"([A-Za-z][A-Za-z0-9-]*)\\s+$", before)
        if prefix and prefix.group(1)[0].isupper():
            continue
        return True
    return False


def command_source_packet(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Make an evidence-only packet for uniquely named current-turn target."""
    labels = {r["scope"] for r in typed_method_command_records(receipts)}
    targets = [
        label for label in labels
        if not label.startswith("device:")
        and _requested_exact_label(request, label)
    ]
    if len(targets) != 1:
        return None
    target = targets[0]
    records = typed_method_command_records(receipts, target=target)
    return {
        "schema": "homebrain-method-command-evidence.v1",
        "target": target,
        "recordedCommands": records[:8],
        "upstreamAutomationDecisionVerified": False,
        "physicalPlantOperationVerified": False,
        "commandHistoryComplete": False,
        "notes": (
            "A device state and recorded method command do not establish "
            "the app's upstream decision, complete historical coverage, "
            "physical plant operation or all other device requests."
        ),
    }


def pending_command_app_decision_log(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """One read-only app log at the latest recorded command for the user target."""
    if not re.search(
        r"(?i)\b(?:why|reason|schedul\w*|protect\w*|early heat\w*|"
        r"decisions?|investigat\w*|automat\w*)\b", request,
    ):
        return None
    packet = command_source_packet(request, receipts)
    if packet is None or not packet["recordedCommands"]:
        return None
    last = packet["recordedCommands"][0]
    app_id = last["recordedIssuerAppId"]
    if not app_id:
        return None
    at = _at(last["at"])
    if at is None:
        return None
    before, after = at - timedelta(minutes=10), at + timedelta(minutes=10)
    for row in receipts:
        if not isinstance(row, dict):
            continue
        op = str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or "")
        if op != "hub_get_logs":
            continue
        args = _args(row)
        if str(args.get("appId") or "") != app_id:
            continue
        # Prior attempt for the same verified app — no more source retries,
        # even if its incident window was wrong or it returned empty.
        return None
    return {
        "tool": "hub_get_logs",
        "args": {
            "appId": app_id,
            "since": before.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "until": after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 60,
        },
        "deviceLabel": packet["target"],
        "observedCommandTimeUtc": last["at"],
        "causeVerified": False,
    }


def render_command_source_packet(request: str, receipts: list[dict[str, Any]]) -> str | None:
    packet = command_source_packet(request, receipts)
    if packet is None:
        return None
    return (
        "HOST OBSERVED METHOD COMMANDS — CURRENT-TURN SOURCE ROLES:\n"
        + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        + "\nExplain the actual recorded command, its source time and "
          "reported device state in natural language. Do not invent the "
          "upstream automation decision, protection/override state, "
          "physical plant operation or hardware acknowledgement from these records. "
          "A successful app config read does not prove historical app "
          "decisions, and empty logs do not prove no rule ran. "
          "Distinguish reported device state from independent plant "
          "operation and absent-command claims."
    )


__all__ = [
    "typed_method_command_records", "command_source_packet",
    "pending_command_app_decision_log", "render_command_source_packet",
]
