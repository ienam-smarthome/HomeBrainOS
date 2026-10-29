"""General operational evidence from independent MCP READ receipts.

Health/staleness, dependencies and current device state are different kinds
of evidence. The host attests only exactly returned rows. A stale timestamp
does NOT imply current offline connectivity; an app reference does NOT imply
failed execution or an active automation. No entity IDs or status invented.

The helper is agnostic to specific devices, rooms, apps, question words and
model routing. Only typed, bounded source projections enter the case ledger.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .native_source_adapters import safe_string


def _id(value: Any) -> str | None:
    if type(value) not in (str, int):
        return None
    text = str(value)
    return text if text.isdecimal() and len(text) <= 20 else None


def operational_evidence_facts(
    receipt: Mapping[str, Any],
    focus_ids: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Evidence candidate facts for any device-health or dependency response."""
    read = receipt.get("read")
    operation = receipt.get("operation")
    data = receipt.get("source_data")
    if type(read) is not int or not isinstance(data, Mapping):
        return []
    focus = {str(d) for d in focus_ids}
    facts: list[dict[str, Any]] = []

    def add(kind: str, key: tuple[Any, ...], statement: str,
            scope: str | None = None) -> None:
        facts.append({
            "kind": kind, "evidence_reads": [read], "source_id": scope,
            "statement": statement, "stable_key": key,
            "limits": "Bounded MCP source observation; no independent physical or execution verification.",
        })

    if operation == "hub_get_device_health":
        stale = data.get("staleDevices")
        unknown = data.get("unknownDevices")
        if isinstance(stale, list):
            valid = [
                row for row in stale[:80]
                if isinstance(row, Mapping) and _id(row.get("id"))
            ]
            add("health_sample_summary", ("health", "stale_count", read),
                f"Hubitat device-health read returned {len(valid)} named/ID "
                "device entries flagged stale. Last-activity staleness "
                "is not proof that each device is currently offline.")
            # The returned stale list may be a page or a capped preview;
            # never claim this is the complete device population.
            for row in valid[:5]:
                ident = _id(row.get("id"))
                if focus and ident not in focus:
                    continue
                name = safe_string(row.get("name") or "Device", 75)
                last = safe_string(row.get("lastActivity"), 72) or "not supplied"
                add("health_stale_entry", ("health", "stale", ident, read),
                    f"{name} (device {ident}) was listed as stale, with "
                    f"source-reported lastActivity={last}. This alone "
                    "does not prove current offline status.", ident)
        if isinstance(unknown, list):
            valid = [
                row for row in unknown[:80]
                if isinstance(row, Mapping) and _id(row.get("id"))
            ]
            add("health_sample_summary", ("health", "unknown_count", read),
                f"Hubitat device-health read returned {len(valid)} devices "
                "with unknown activity; absence of a recorded timestamp "
                "does not prove a physical device is offline.")
            for row in valid[:4]:
                ident = _id(row.get("id"))
                if focus and ident not in focus:
                    continue
                name = safe_string(row.get("name") or "Device", 75)
                last = safe_string(row.get("lastActivity"), 72) or "not supplied"
                add("health_unknown_entry", ("health", "unknown", ident, read),
                    f"{name} (device {ident}) had unknown activity "
                    f"(lastActivity={last}) in the returned health sample. "
                    "Its actual connectivity was not verified.", ident)
    elif operation == "hub_list_device_dependents":
        filters = receipt.get("read_filters")
        if not isinstance(filters, Mapping):
            return []
        requested = _id(filters.get("deviceId"))
        returned = _id(data.get("deviceId"))
        if not requested or returned != requested or (focus and requested not in focus):
            return []
        apps = data.get("apps_using")
        if not isinstance(apps, list):
            return []
        verified = [
            (str(x["appId"]), safe_string(x.get("name") or "App", 66))
            for x in apps[:80]
            if isinstance(x, Mapping) and _id(x.get("appId"))
        ]
        count = data.get("count")
        # The source count is not authoritative if it disagrees with its
        # typed, bounded rows; state only what is actually represented.
        found = len(verified)
        summary = ", ".join(
            f"{label} (app {ident})" for ident, label in verified[:4]
        )
        if found > 4:
            summary += f"; {found - 4} additional returned app references"
        add("app_dependency_reference", ("dependents", requested, read),
            f"Hubitat reported {found} app references to device {requested}"
            + (f": {summary}." if summary else ".")
            + " These are references, not proof that an automation "
              "is active, malfunctioning or issuing commands.", requested)
    return facts


__all__ = ["operational_evidence_facts"]
