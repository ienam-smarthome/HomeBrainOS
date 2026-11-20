"""Bounded adapter from original read receipts to grounding anchors."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from investigation_source_ledger import _response, _SAFE_FIELD, _SAFE_ID
from native_device_event_receipt import original_device_event_history
from native_past_log_receipt import original_past_log_source


def _id(value: object) -> str | None:
    return str(value) if type(value) in (str, int) and _SAFE_ID.fullmatch(str(value)) else None


def _event_anchors(receipt: dict, zone: ZoneInfo) -> list[dict]:
    envelope, native = _response(receipt)
    if (not isinstance(envelope, dict) or not isinstance(native, dict)
            or envelope.get("isError") is True or native.get("isError") is True):
        return []
    history = original_device_event_history(receipt)
    if history is None:
        return []
    device_id, _, events = history
    attribute = receipt["arguments"].get("attribute")
    rows = []
    for event in events[:250]:
        if not isinstance(event, dict):
            continue
        field, date = event.get("name"), event.get("date")
        inline_id = event.get("deviceId")
        if (not isinstance(field, str) or not _SAFE_FIELD.fullmatch(field)
                or (attribute and field != attribute)
                or (inline_id is not None and _id(inline_id) != device_id)
                or not isinstance(date, str) or len(date) > 40):
            continue
        try:
            stamp = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            continue
        producer = event.get("producedBy")
        producer = producer if isinstance(producer, dict) else {}
        command = field.startswith("command-") or event.get("type") == "command"
        if command:
            roles = {"recorded_issuer_app_id": _id(producer.get("appId"))}
        else:
            notified = event.get("triggered")
            notified = notified[:8] if isinstance(notified, list) else []
            roles = {
                "reporter_device_id": _id(producer.get("deviceId")),
                "reporter_app_id": _id(producer.get("appId")),
                "notified_app_ids": list(dict.fromkeys(
                    ident for row in notified if isinstance(row, dict)
                    if (ident := _id(row.get("appId"))) is not None
                )),
            }
        rows.append((stamp, {
            "device_id": device_id, "field": field,
            "row_role": "command" if command else "state_report",
            "source_timestamp": date,
            "utc_timestamp": stamp.astimezone(timezone.utc).isoformat(),
            "hub_display_time": stamp.astimezone(zone).strftime("%A %Y-%m-%d %H:%M:%S %Z (%z)"),
            **roles,
        }))
    ordered = sorted(rows, key=lambda row: row[0], reverse=True)
    # Keep both row types discoverable when a noisy attribute dominates the page.
    commands = [row for _, row in ordered if row["row_role"] == "command"]
    states = [row for _, row in ordered if row["row_role"] == "state_report"]
    return states[:2] + commands[:2]


def receipt_grounding_anchors(receipts: list[dict], timezone_name: str | None) -> list[dict]:
    """Navigation only. A receipt without a supported source shape yields no anchors."""
    try:
        zone = ZoneInfo(timezone_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    result = []
    for position, receipt in enumerate(receipts[:16], 1):
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("operation_executed") is False):
            continue
        tool = receipt.get("name")
        if tool == "hub_list_device_events":
            events = _event_anchors(receipt, zone)
            if events:
                result.append({"receipt_number": position, "events": events})
        elif tool in ("hub_get_logs", "hub_list_devices"):
            if tool == "hub_get_logs":
                parsed = original_past_log_source(receipt)
                if parsed is None:
                    continue
                envelope, data, _ = parsed
            else:
                envelope, data = _response(receipt)
            if not isinstance(data, dict) or not isinstance(envelope, dict):
                continue
            if envelope.get("isError") is True or data.get("isError") is True:
                continue
            rows = data.get("entries" if tool == "hub_get_logs" else "devices")
            if not isinstance(rows, list):
                continue
            key = "reported_total_scope_unspecified" if tool == "hub_get_logs" else "reported_inventory_total"
            page = {"receipt_number": position, "returned_rows": len(rows)}
            if type(data.get("total")) is int:
                page[key] = data["total"]
            if tool == "hub_get_logs":
                if type(data.get("matched")) is int:
                    page["matched_rows"] = data["matched"]
                page["requested_interval_completeness_established"] = False
            elif type(data.get("hasMore")) is bool:
                page["native_has_more"] = data["hasMore"]
            result.append(page)
    return result
