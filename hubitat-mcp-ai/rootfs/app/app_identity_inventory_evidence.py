"""Bounded read-only app/type inventory evidence; never a writer authorization."""
from __future__ import annotations

import re
from typing import Any

_ID = re.compile(r"[1-9][0-9]{0,8}\Z")
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.: ()/-]{0,95}\Z")
_BAD = re.compile(r"(?i)(secret|token|password|credential|api.?key|https?://)")
_MAX_ROWS = 20


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    value = str(value)
    return value if _ID.fullmatch(value) else None


def _label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _SAFE.fullmatch(value) and not _BAD.search(value) else None


def project_app_inventory_page(
    gateway: str, arguments: dict[str, Any], data: Any,
) -> dict[str, Any] | None:
    """Publish up to 20 source rows from a filtered list, not the full catalog."""
    if gateway != "hub_read_apps_code" or not isinstance(arguments, dict):
        return None
    if arguments.get("tool") != "hub_list_apps":
        return None
    args = arguments.get("args")
    if not isinstance(args, dict) or not isinstance(data, dict):
        return None
    scope = args.get("scope")
    name_filter = _label(args.get("nameFilter"))
    if scope not in ("instances", "types") or not name_filter:
        return None
    if data.get("success") is False or not isinstance(data.get("apps"), list):
        return None
    if scope == "types" and data.get("source") != "hub_api":
        return None
    rows = []
    for item in data["apps"]:
        if not isinstance(item, dict):
            continue
        rid, name = _id(item.get("id")), _label(item.get("name"))
        if not rid or not name or name_filter.casefold() not in name.casefold():
            continue
        if scope == "instances":
            record = {"appId": rid, "reportedName": name}
            if (type_id := _id(item.get("appTypeId"))) is not None:
                record["appTypeId"] = type_id
            if (type_name := _label(item.get("type"))) is not None:
                record["reportedType"] = type_name
            if type(item.get("user")) is bool:
                record["reportedUser"] = item["user"]
            if "parentId" in item:
                parent = item["parentId"]
                if parent is None or _id(parent) is not None:
                    record["parentIdPresent"] = True
                    record["reportedParentId"] = _id(parent)
        else:
            record = {"typeId": rid, "reportedTypeName": name}
            if (namespace := _label(item.get("namespace"))) is not None:
                record["reportedNamespace"] = namespace
            for field, dest in (("system", "reportedSystem"), ("isBuiltIn", "reportedIsBuiltIn")):
                if type(item.get(field)) is bool:
                    record[dest] = item[field]
        rows.append(record)
    if not rows:
        return None
    details = {
        "inventoryScope": scope,
        "nameFilter": name_filter,
        "rows": rows[:_MAX_ROWS],
        "returnedRowsInResponse": len(data["apps"]),
        "projectedRowsInResponse": len(rows),
        "projectionTruncated": len(rows) > _MAX_ROWS,
        "nextCursorAvailable": data.get("nextCursor") is not None,
        "nativeClassBindingVerified": False,
    }
    if scope == "types":
        details["catalogSource"] = "hub_api"
        details["catalogNotePresent"] = bool(data.get("note"))
    return details


def match_app_inventory_receipts(
    receipts: list[dict[str, Any]], target: str | None,
) -> dict[str, Any] | None:
    """Join source-reported instance and type records by IDs, not by names."""
    target = _id(target)
    if not target:
        return None
    instances, types = [], []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if (row.get("tool") != "hub_read_apps_code" or
                row.get("sub_tool") != "hub_list_apps" or
                row.get("effect") != "read" or row.get("mutates") is not False):
            continue
        args, details = row.get("arguments"), row.get("details")
        if not isinstance(args, dict) or not isinstance(details, dict):
            continue
        scope = details.get("inventoryScope")
        kind = ("typed_app_inventory_page" if scope == "instances" else
                "typed_app_type_catalog_page" if scope == "types" else None)
        params = args.get("args")
        if (args.get("tool") != "hub_list_apps" or not isinstance(params, dict) or
                params.get("scope") != scope or
                _label(params.get("nameFilter")) != details.get("nameFilter") or
                row.get("evidence_kind") != kind or
                details.get("nativeClassBindingVerified") is not False or
                not isinstance(details.get("rows"), list) or
                len(details["rows"]) > _MAX_ROWS):
            continue
        if scope == "types" and details.get("catalogSource") != "hub_api":
            continue
        for item in details["rows"]:
            if not isinstance(item, dict):
                continue
            if scope == "instances" and _id(item.get("appId")) == target:
                instances.append(item)
            elif scope == "types" and _id(item.get("typeId")) is not None:
                types.append(item)
    if not instances:
        return None
    ids = {_id(item.get("appTypeId")) for item in instances}
    candidate = next(iter(ids)) if len(ids) == 1 else None
    matches = [item for item in types
               if candidate is not None and _id(item.get("typeId")) == candidate]
    return {
        "appId": target,
        "inventoryInstanceRows": instances,
        "instanceTypeId": candidate,
        "instanceTypeIdConflict": len(ids) > 1,
        "matchedTypeRows": matches,
        "typeIdJoinObserved": bool(candidate and matches),
        "nativeClassBindingVerified": False,
    }


__all__ = ["project_app_inventory_page", "match_app_inventory_receipts"]
