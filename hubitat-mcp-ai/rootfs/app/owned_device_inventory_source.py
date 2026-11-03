"""Bounded, exact read-only inventory of MCP-owned virtual devices.

This is a source-scoped request, not Rule Machine inventory. Negative safety
instructions mentioning rules must never steal the requested device read.
"""
from __future__ import annotations

import re
import time
from typing import Any

from mcp_client import tool_succeeded
from skill_secret_guard import redact_secrets

_SOURCE = "hub_list_devices owned detailed"
_SCOPE = re.compile(r"\bscope\s*[:=]\s*[\"']?owned\b", re.I)
_FORMAT = re.compile(r"\bformat\s*[:=]\s*[\"']?detailed\b", re.I)
_DENY_CALL = re.compile(r"\b(?:do\s+not|don't|never)\s+(?:call|use|invoke|run)\s+hub_list_devices\b", re.I)
_DEVICE_TOPIC = re.compile(r"\b(?:mcp[- ](?:created|managed|owned)|virtual\s+devices?)\b", re.I)
_SWITCH = re.compile(r"^virtual\s+switch(?:\s+.*)?$", re.I)
_ID = re.compile(r"[1-9]\d{0,8}")
_MAX_PAGES = 12
_PAGE_SIZE = 20


def is_explicit_owned_device_inventory_request(question: str) -> bool:
    """A single, exact MCP-owned device-only read. Never act on exclusions."""
    q = str(question or "")
    lead = q[:200]
    if (not re.search(r"\bhub_list_devices\b", q, re.I)
            or _DENY_CALL.search(q)
            or not _SCOPE.search(q) or not _FORMAT.search(q)
            or not _DEVICE_TOPIC.search(q)
            or not re.search(r"\bonly\b", lead, re.I)):
        return False
    # Respect the explicitly named device-only scope; unrelated tool names
    # mentioned in a prohibited-operation sentence do not expand the task.
    return True


def owned_device_coverage(request: str, evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not is_explicit_owned_device_inventory_request(request):
        return None
    for row in reversed(evidence):
        if (not isinstance(row, dict)
                or row.get("evidence_kind") != "typed_owned_device_inventory"
                or row.get("effect") != "read" or row.get("mutates") is not False):
            continue
        d = row.get("details")
        if not isinstance(d, dict) or d.get("source") != _SOURCE:
            continue
        verified = (row.get("success") is True
                    and row.get("supports_live_claim") is True
                    and d.get("inventoryComplete") is True
                    and d.get("metadataComplete") is True
                    and d.get("requestedScope") == "owned"
                    and d.get("requestedFormat") == "detailed")
        return {
            "domain": "owned_virtual_device_inventory",
            "status": "owned-inventory-verified" if verified else "partial-evidence",
            "evidenceComplete": verified,
            "questionResolved": verified,
            "requestedScope": "owned",
            "requestedFormat": "detailed",
            "returnedCount": d.get("returnedCount"),
            "sourceTotal": d.get("sourceTotal"),
            "inventoryComplete": d.get("inventoryComplete") is True,
            "metadataComplete": d.get("metadataComplete") is True,
            "requirements": [{
                "key": "owned_device_list",
                "state": "observed" if verified else "checked-unverified",
                "necessary": True,
                "source": _SOURCE,
            }],
            "limitations": (
                ["MCP-owned device membership only; unrelated devices, native Rule Machine parent identity and physical effects were not checked."]
                if verified else
                ["The requested MCP-owned device list or necessary metadata was not fully verified; do not infer an empty inventory."]
            ),
        }
    return None


def _err(result: Any, *, fallback: str) -> str:
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        e = data.get("error")
        if isinstance(e, dict):
            val = f"{e.get('code', 'source-error')}: {e.get('message', fallback)}"
        else:
            val = str(e or data.get("message") or fallback)
    else:
        val = fallback
    return redact_secrets(val[:300]).replace("\n", " ")


async def read_owned_virtual_device_inventory(
    mcp: Any, recorder: Any, *,
    available_names: set[str] | frozenset[str],
) -> tuple[str, dict[str, Any]]:
    gateway = ("hub_read_devices" if "hub_read_devices" in available_names
               else "hub_list_devices" if "hub_list_devices" in available_names else None)
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    visited: set[str] = set()
    offset = "0"
    total: int | None = None
    error = ""
    inventory_complete = False
    metadata_complete = True
    page_count = 0

    if gateway is None:
        error = "Read-only hub_list_devices is unavailable in the current MCP tool catalog."
    else:
        for _ in range(_MAX_PAGES):
            args: dict[str, Any] = {
                "scope": "owned", "format": "detailed",
                "cursor": offset, "limit": _PAGE_SIZE,
            }
            request = {"tool": "hub_list_devices", "args": args} if gateway == "hub_read_devices" else args
            t = time.monotonic()
            result = None
            data = None
            try:
                result = await mcp.call_tool(gateway, request)
                if tool_succeeded(result) and isinstance(result.data, dict):
                    data = result.data
            except Exception:
                pass
            recorder.record(
                gateway, request, success=data is not None,
                elapsed_ms=round((time.monotonic() - t) * 1000),
                summary=("Owned virtual device page read" if data is not None
                         else "Owned virtual device page unavailable"),
                supports_live_claim=False,
                evidence_kind="owned_device_list_source",
                effect="read", mutates=False,
            )
            page_count += 1
            if data is None:
                error = _err(result, fallback="MCP source read failed or returned an unsupported response.")
                break
            items = data.get("devices")
            count, source_total = data.get("count"), data.get("total")
            if (not isinstance(items, list)
                    or any(not isinstance(item, dict) for item in items)
                    or type(count) is not int or count != len(items)
                    or type(source_total) is not int or source_total < 0
                    or (total is not None and source_total != total)
                    or data.get("offset") != int(offset)):
                error = "Source page shape/count/offset conflicted; inventory incomplete."
                break
            total = source_total
            if (data.get("partial") is True or data.get("budgetLimited") is True
                    or data.get("metadataUnavailableIds")):
                metadata_complete = False
            for item in items:
                device_id = str(item.get("id") or "")
                if (not _ID.fullmatch(device_id) or device_id in ids
                        or item.get("mcpManaged") is not True):
                    error = "Owned device identity/ownership was missing or duplicated."
                    break
                ids.add(device_id)
                if item.get("metadataUnavailable") is True:
                    metadata_complete = False
                rows.append(item)
            if error:
                break
            if data.get("hasMore") is False:
                if not data.get("nextCursor") and len(rows) == total:
                    inventory_complete = True
                else:
                    error = "Terminal source page has inconsistent total/cursor."
                break
            nxt = data.get("nextCursor")
            if (data.get("hasMore") is not True or not isinstance(nxt, str)
                    or not nxt.isdecimal() or int(nxt) <= int(offset)
                    or nxt in visited or len(rows) >= 500):
                error = "Source pagination is missing, repeated, or exceeds safety limits."
                break
            visited.add(offset)
            offset = nxt
        else:
            error = "Source pagination exceeded bounded page budget."

    verified = inventory_complete and metadata_complete and not error
    switches: list[str] = []
    for item in rows:
        driver = str(item.get("driverType") or item.get("driver") or "").strip()
        if _SWITCH.fullmatch(driver):
            label = str(item.get("label") or item.get("name") or "(label unavailable)")[:120]
            ns = str(item.get("driverNamespace") or "not supplied")[:80]
            typ = str(item.get("driverType") or "not supplied (native driver field used)")[:80]
            switches.append(
                f"- {label} (ID {item['id']}): driver={driver}; "
                f"driverType={typ}; driverNamespace={ns}; mcpManaged=true"
            )
    lines = ["**MCP-owned virtual devices — read-only**", ""]
    if verified:
        lines.append(f"Complete owned-device inventory: {len(rows)} of {total} devices returned across {page_count} page(s).")
    else:
        lines.append("Owned-device inventory not fully verified; no empty-inventory claim is justified.")
        if error:
            lines.append("Read/validation error: " + error)
        lines.append(f"Returned {len(rows)} device row(s) from {page_count} attempted page(s); source total: {total if total is not None else 'unknown'}.")
        if not metadata_complete:
            lines.append("Some device metadata was unavailable.")
    if switches:
        lines.extend(["", "Virtual Switch entries identified from source-provided driver names:", *switches])
    elif verified:
        lines.append("No Virtual Switch driver was identified among the complete MCP-owned inventory.")
    else:
        lines.append("No Virtual Switch absence can be concluded.")
    lines.append("")
    lines.append("Rule Machine parent identity was not checked. No modifying Hubitat operations were called.")
    projection = {
        "source": _SOURCE, "requestedScope": "owned",
        "requestedFormat": "detailed", "returnedCount": len(rows),
        "sourceTotal": total, "pageCount": page_count,
        "inventoryComplete": inventory_complete and not error,
        "metadataComplete": metadata_complete, "virtualSwitchCount": len(switches),
        "error": error or None,
    }
    recorder.record(
        "homebrain_owned_device_inventory", {},
        success=verified, elapsed_ms=0,
        summary="Typed source-scoped MCP-owned device inventory",
        evidence_kind="typed_owned_device_inventory",
        supports_live_claim=verified, effect="read", mutates=False,
        details=projection,
    )
    return "\n".join(lines), projection
