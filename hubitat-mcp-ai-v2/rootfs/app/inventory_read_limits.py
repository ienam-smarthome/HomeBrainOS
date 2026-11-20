"""Bounded safety/performance contract for repeated native DETAILED inventories.

No device selection, native retry, source synthesis or writer path. The user
may still request a complete summary/attribute projection and the connected
model chooses any subsequent offered read. The cap applies ONLY to detailed
all-device inventory, not ordinary focused queries or read-only commands.
"""
from __future__ import annotations


def detailed_inventory_block_reason(args: object, receipts: list[dict]) -> str | None:
    if not isinstance(args, dict) or args.get("format") != "detailed":
        return None
    # A single detailed request with an excessive page limit can consume
    # the whole first-answer deadline and frequently exceeds MCP output caps.
    limit = args.get("limit")
    if type(limit) is int and limit > 100:
        return (
            "Detailed inventory page limit exceeds this client's bounded "
            "maximum of 100. Nothing was executed. For a count, prefer a "
            "schema-supported summary/attribute projection; for detail, "
            "request a smaller page with the live catalog contract."
        )
    detailed_failures = sum(
        row.get("name") == "hub_list_devices"
        and row.get("success") is False
        and isinstance(row.get("arguments"), dict)
        and row["arguments"].get("format") == "detailed"
        and row.get("operation_executed") is not False
        for row in receipts
        if isinstance(row, dict)
    )
    if detailed_failures >= 2:
        return (
            "Two detailed inventory attempts failed in this Ask. "
            "No further detailed inventory reads may execute in this request. "
            "Choose a schema-supported summary/attribute query if useful; "
            "previous failed reads contain no evidence of missing devices."
        )
    return None


def inventory_failure_recovery_note(args: object) -> dict | None:
    if not isinstance(args, dict) or args.get("format") != "detailed":
        return None
    return {
        "status": "failed_detailed_inventory_not_data",
        "failed_read_cannot_prove_device_absence": True,
        "no_client_automatic_retry": True,
        "suggested_next_source_category": "native summary or attribute-projected inventory",
        "next_tool_and_arguments_remain_model_selected": True,
        "note": (
            "Detailed pages may exceed source output limits even when "
            "the schema accepts the request. Do not blindly retry oversized "
            "pages. For numeric counts, use the currently advertised "
            "summary/attribute projection when supported; verify total, "
            "pagination, distinct IDs and numeric values."
        ),
    }
