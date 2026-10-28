"""Fast, schema-gated read of one explicitly named current Hubitat device.

Identity comes exclusively from a complete independently verified inventory.
The question contract is exact and intentionally narrow: no model-generated IDs,
no causal/history or mixed objective conversion, and no device write capability.
A failed/unsupported targeted source falls back to the existing full read path.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from mcp_client import MCPTool
from .device_context import _gateway, _args_schema, _accepts_field
from .planning import _schema_problem
from .receipt_projection import project_read_receipt


def current_status_attributes(
    question: str, verified_labels: Sequence[str],
) -> tuple[str, ...]:
    """Accept only a whole, explicitly named, factual read-only question."""
    if len(verified_labels) != 1 or not isinstance(question, str) or len(question) > 400:
        return ()
    label = " ".join(verified_labels[0].strip().casefold().split())
    if not label:
        return ()
    cleaned = " ".join(re.sub(r"[?.!]", "", question).casefold().split())
    hits = list(re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", cleaned))
    if len(hits) != 1:
        return ()
    match = hits[0]
    template = cleaned[:match.start()] + "{device}" + cleaned[match.end():]
    allowed = {
        "read the current switch state and brightness level of {device} directly from hubitat do not change anything",
        "read the current switch state and brightness of {device} directly from hubitat do not change anything",
        "what is the current switch state and brightness level of {device}",
        "what is the current switch state and brightness of {device}",
    }
    return ("switch", "level") if template in allowed else ()



# A filtered identity query is available only for these *entire* factual
# templates. Extracting a user-supplied name is not an AI identity guess.
_EXPLICIT_CURRENT = (
    re.compile(
        r"(?i)^\s*read the current switch state and brightness(?: level)? of "
        r"(?P<name>[^?!.]{3,160}?) directly from hubitat\.? "
        r"do not change anything\.?\s*$"
    ),
    re.compile(
        r"(?i)^\s*what is the current switch state and brightness(?: level)? of "
        r"(?P<name>[^?!.]{3,160}?)\??\s*$"
    ),
)


def explicit_current_device_name(question: str) -> str | None:
    if not isinstance(question, str) or len(question) > 400:
        return None
    for template in _EXPLICIT_CURRENT:
        match = template.fullmatch(question)
        if match:
            name = " ".join(match.group("name").strip().split())
            if (3 <= len(name) <= 160
                    and " and " not in name.casefold()
                    and not re.search(r"\b(?:device\s*[0-9]+|#\d+)\b", name, re.I)):
                return name
    return None


async def read_filtered_target_identity(
    mcp: Any, requested_label: str,
    *, diagnostics: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Read a COMPLETE exact-label-filtered source page, or decline.

    Requires the live read-only schema to advertise the labelFilter. The
    provider's total and hasMore/nextOffset attest *filter coverage*; they do
    NOT attest the user's entire Hubitat inventory. Only a unique exact
    friendly label can be selected. No device status or writes are read here.
    """
    if (not isinstance(requested_label, str)
            or not 3 <= len(requested_label) <= 160
            or " and " in requested_label.casefold()):
        return None
    gateway = _gateway(await mcp.list_tools(), "hub_list_devices")
    if gateway is None:
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_gateway_unavailable"
        return None
    nested = _args_schema(gateway)
    properties = nested.get("properties")
    required = nested.get("required")
    if (not isinstance(properties, dict)
            or not isinstance(required, list)
            or "labelFilter" not in properties):
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filter_not_advertised"
        return None
    args: dict[str, Any] = {"labelFilter": requested_label}
    # Explicitly bound pagination and summary identity projection only.
    for key, value in (
        ("fields", ["id", "name", "label", "room"]),
        ("limit", 50), ("offset", 0), ("detailed", False),
    ):
        if key in properties:
            args[key] = value
    if any(key not in args for key in required):
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_schema_required_fields"
        return None
    request = {"tool": "hub_list_devices", "args": args}
    if _schema_problem(request, gateway.input_schema) is not None:
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_schema_rejected"
        return None
    if diagnostics is not None:
        diagnostics["filtered_gateway_read_attempted"] = True
    result = await mcp.call_tool(gateway.name, request)
    from mcp_client import tool_succeeded
    if not tool_succeeded(result):
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_source_failed"
        return None
    from mcp_client import HubitatMCPClient
    source = HubitatMCPClient._find_device_page(result.data)
    rows = HubitatMCPClient._find_device_list(result.data)
    if (not isinstance(source, dict) or not isinstance(rows, list)
            or not isinstance(source.get("total"), int)
            or isinstance(source["total"], bool)
            or source["total"] != len(rows)
            or source.get("hasMore") is not False
            or len(rows) != 1
            or source.get("nextOffset") not in (None, 0)):
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_coverage_unverified"
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    ident = row.get("id")
    friendly = row.get("label")
    if (type(ident) not in (int, str)
            or not str(ident).isdecimal()
            or len(str(ident)) > 20
            or not isinstance(friendly, str)
            or friendly.strip().casefold() != requested_label.strip().casefold()):
        if diagnostics is not None:
            diagnostics["identity_lookup"] = "filtered_identity_mismatch"
        return None
    identity = {key: row[key] for key in ("id", "name", "label", "room", "roomName")
                if key in row}
    identity["id"] = str(ident)
    if diagnostics is not None:
        diagnostics["identity_lookup"] = "filtered_unique_exact_label"
    return [identity], {
        "source": "verified_hubitat_label_filter",
        "projection": "filtered_identity_only",
        "mode": "single_complete_filtered_page",
        "pages": 1,
        "scope": "exact_label",
        "complete": True,
        "home_inventory_complete": False,
        "page_timings_ms": [],
    }


def _attested_id(data: Mapping[str, Any]) -> str | None:
    """Only an explicit source-reported ID can attest the queried target."""
    source: Mapping[str, Any] = data
    for key in ("device", "data", "result"):
        nested = source.get(key)
        if isinstance(nested, dict):
            source = nested
    raw = source.get("id", source.get("deviceId"))
    return str(raw) if type(raw) in (str, int) and str(raw).isdecimal() else None


async def read_verified_target_status(
    mcp: Any, verified_id: str, *,
    wanted_attributes: Sequence[str] = ("switch", "level"),
    diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return (typed snapshot, honest scoped provenance), otherwise None.

    No caller-supplied tool names, arbitrary device IDs or write grants.
    The caller must already have uniquely bound verified_id via a complete
    identity audit; revalidate digits here as defence in depth.
    """
    def declined(reason: str) -> None:
        if diagnostics is not None:
            diagnostics["outcome"] = reason
        return None

    if not isinstance(verified_id, str) or not verified_id.isdecimal():
        return declined("invalid_verified_id")
    if tuple(wanted_attributes) != ("switch", "level"):
        return declined("unsupported_attribute_contract")
    tools = await mcp.list_tools()
    gateway = _gateway(tools, "hub_get_device")
    if gateway is None:
        return declined("live_read_operation_unavailable")
    nested = _args_schema(gateway)
    props = nested.get("properties", {})
    props = props if isinstance(props, dict) else {}
    required = nested.get("required", [])
    if not isinstance(required, list) or not _accepts_field(nested, "deviceId"):
        return declined("missing_live_device_id_schema")
    args: dict[str, Any] = {"deviceId": verified_id}
    if "mode" in required:
        allowed = props.get("mode", {}).get("enum", [])
        if not isinstance(allowed, list) or "status" not in allowed:
            return declined("status_mode_not_advertised")
        args["mode"] = "status"
    if any(key not in args for key in required):
        return declined("unsupported_required_args")
    request = {"tool": "hub_get_device", "args": args}
    if _schema_problem(request, gateway.input_schema) is not None:
        return declined("request_schema_rejected")
    # The exact, live-manifest-authorised operation is READ. No retries
    # on an error, and a malformed response cannot be promoted into state.
    if diagnostics is not None:
        diagnostics["gateway_read_attempted"] = True
    result = await mcp.call_tool(gateway.name, request)
    if not isinstance(result.data, dict):
        return declined("unstructured_source")
    if _attested_id(result.data) != verified_id:
        return declined("source_id_missing_or_mismatched")
    receipt = project_read_receipt(
        gateway.name, request, result,
        source_request_id="targeted-current-read",
    )
    if receipt.get("success") is not True:
        return declined("typed_source_receipt_failed")
    detail = receipt.get("details") or {}
    snapshot = detail.get("deviceSnapshot")
    if not isinstance(snapshot, dict) or snapshot.get("deviceId") != verified_id:
        return declined("typed_snapshot_id_mismatch")
    attrs = snapshot.get("attributes")
    if not isinstance(attrs, dict) or not any(
        key in attrs for key in wanted_attributes
    ):
        return declined("requested_attributes_not_projectable")
    # Provenance is *scoped* to this one fresh device read. It says nothing
    # about whether all devices or all possible states were returned.
    provenance = {
        "source": "schema_validated_hub_get_device",
        "projection": "targeted_current_attributes",
        "complete": True,
        "scope": "single_verified_id",
        "pages": 0,
        "source_operation": "hub_get_device",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if diagnostics is not None:
        diagnostics["outcome"] = "verified_targeted_source"
    return snapshot, provenance


__all__ = ["current_status_attributes", "read_verified_target_status",
           "explicit_current_device_name", "read_filtered_target_identity"]
