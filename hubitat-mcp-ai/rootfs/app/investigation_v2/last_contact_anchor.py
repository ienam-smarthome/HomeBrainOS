"""Evidence-driven search around a *reported* last-device-contact timestamp.

A lastSeen attribute is a search anchor, not independently established
physical contact. No device-specific naming, model inference or arbitrary
permission expansion. The ordinary read plan reviews each proposed read.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from mcp_client import MCPTool
from .device_context import _accepts_field, _args_schema, _gateway, _safe_identifier
from .evidence import CaseFile


def _reported_last_seen(case: CaseFile, ident: str) -> datetime | None:
    for snapshot in reversed(case.device_snapshots):
        if snapshot.get("deviceId") != ident:
            continue
        attrs = snapshot.get("attributes")
        value = attrs.get("lastSeen") if isinstance(attrs, dict) else None
        if not isinstance(value, str):
            continue
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                continue
        except ValueError:
            try:
                # Exactly the same reported UK source-clock form recognised
                # by device_context, including BST/GMT offset verification.
                parts = value.rsplit(" ", 2)
                if len(parts) != 3 or parts[1] not in ("BST", "GMT"):
                    continue
                local = datetime.strptime(
                    parts[0] + " " + parts[2], "%a %b %d %H:%M:%S %Y")
                dt = local.replace(tzinfo=ZoneInfo("Europe/London"))
                if dt.tzname() != parts[1]:
                    continue
            except (ValueError, OverflowError):
                continue
        return dt.astimezone(timezone.utc)
    return None


def last_contact_anchor_proposals(
    tools: Iterable[MCPTool], verified_ids: Iterable[str], case: CaseFile,
    *, learned_operations: Mapping[str, set[str]] | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """One bounded, independently gated attempt to recover an old event window.

    Only target-matched, source-reported lastSeen is used; the user need not
    know a date in advance. Return a categorical diagnostic instead of
    assuming an empty or ignored window was historically complete.
    """
    ident = _safe_identifier(verified_ids)
    if ident is None:
        return [], "target_not_unique"
    anchor = _reported_last_seen(case, ident)
    if anchor is None:
        return [], "reported_last_seen_unavailable"
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        return [], "invalid_reference_clock"
    age = (clock.astimezone(timezone.utc) - anchor).total_seconds()
    if not 24 * 3600 <= age <= 31 * 86400:
        return [], "no_old_last_seen_anchor"
    # A lastSeen value alone doesn't establish that an event source has a
    # gap worth backfilling. Only compare with actual timestamped history
    # returned for this exact target; avoid a fourth speculative read when
    # all historical pages were empty.
    historical_pages = [c for c in case.coverage
                        if c.operation == "hub_list_device_events"
                        and c.query_target_id == ident and c.succeeded
                        and c.oldest_utc is not None]
    if not historical_pages:
        return [], "no_timed_history_for_gap_comparison"
    if any(datetime.fromisoformat(c.oldest_utc) <= anchor + timedelta(hours=2)
           for c in historical_pages):
        return [], "reported_contact_window_already_observed"
    gateway = _gateway(tools, "hub_list_device_events",
                       learned_operations=learned_operations)
    if gateway is None:
        return [], "historical_read_not_advertised"
    schema = _args_schema(gateway)
    fields = schema.get("properties", {})
    fields = fields if isinstance(fields, dict) else {}
    required = schema.get("required", [])
    if not isinstance(required, list) or not _accepts_field(schema, "deviceId"):
        return [], "device_scope_schema_unavailable"
    args: dict[str, Any] = {"deviceId": ident}
    start = anchor - timedelta(hours=2)
    end = anchor + timedelta(hours=2)
    if _accepts_field(schema, "hoursBack"):
        hours = int((clock.astimezone(timezone.utc)-start).total_seconds() // 3600) + 2
        maximum = fields.get("hoursBack", {}).get("maximum")
        if type(maximum) in (int, float) and maximum > 0 and hours > maximum:
            return [], "historical_horizon_exceeds_live_schema"
        args["hoursBack"] = hours
    if _accepts_field(schema, "since") and _accepts_field(schema, "until"):
        args["since"] = start.isoformat()
        args["until"] = end.isoformat()
        strategy = "requested_bounded_last_seen_window"
    else:
        # When no temporal window fields are permitted, use a larger
        # existing history page only if its live schema allows enough rows.
        if "hoursBack" not in args or not _accepts_field(schema, "limit"):
            return [], "no_bounded_historical_window_or_larger_page"
        strategy = "requested_deeper_last_seen_history"
    if _accepts_field(schema, "limit"):
        maximum = fields.get("limit", {}).get("maximum")
        limit = min(200, int(maximum)) if type(maximum) is int and maximum > 0 else 200
        if limit <= 50 and strategy == "requested_deeper_last_seen_history":
            return [], "no_larger_historical_page"
        args["limit"] = limit
    if "attribute" in required:
        choices = fields.get("attribute", {}).get("enum", [])
        if not isinstance(choices, list) or "switch" not in choices:
            return [], "mandatory_attribute_cannot_be_safely_resolved"
        args["attribute"] = "switch"
    if any(field not in args for field in required):
        return [], "unmet_live_required_arguments"
    return [{
        "tool": gateway.name,
        "arguments": {"tool": "hub_list_device_events", "args": args},
        "discriminator": "Historical source check around device-reported lastSeen",
        "information_gain": "Test historical event coverage around the reported disappearance, not just recent watchdog activity",
        "hypothesis_ids": [],
    }], strategy


__all__ = ["last_contact_anchor_proposals"]
