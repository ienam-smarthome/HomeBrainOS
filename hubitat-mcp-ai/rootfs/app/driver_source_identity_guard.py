"""Verify source-code identity before executing read-only driver-source requests.

A Hubitat device instance ID is not a driver *source-code* ID. For a
single-device telemetry investigation, an LLM must not substitute the known
device ID into hub_get_source(type=driver, id=...). Only an explicitly
target-linked successful metadata receipt can authorize that read. Unknown
metadata fails closed for the *source code operation*, never for the wider
investigation or ordinary device/log reads.

No target names, raw source text, tokens or arbitrary message content are
persisted; the caller sends a static source-identity limitation to the model.
"""
from __future__ import annotations

from typing import Any

from typed_device_history_evidence import normalize_target_device_history


_CODE_KEYS = ("sourceCodeId", "driverSourceCodeId", "driverCodeId")
_CONTAINERS = ("driverSource", "driver", "deviceInfo", "driverInfo")


def _numeric_code_id(value: Any) -> str | None:
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        candidate = str(value).strip()
        if candidate.isdigit() and int(candidate) > 0:
            return candidate
    return None


def _linked_driver_source_ids(
    receipts: list[dict[str, Any]],
    target_device_id: str,
) -> frozenset[str]:
    """Use explicit code-ID fields from a positively device-scoped read.

    Do not infer a source ID from a device ID, a driver name, a cache entry,
    an unrelated app, a successful source call or an arbitrary model string.
    """
    ids: set[str] = set()
    for row in receipts:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("mutates") is True or row.get("effect") == "write"):
            continue
        if row.get("sub_tool") not in {"hub_get_device", "hub_list_devices"}:
            continue
        args = row.get("arguments") or {}
        if not isinstance(args, dict):
            continue
        inner = args.get("args")
        inner = inner if isinstance(inner, dict) else args
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        # Do not trust a source object attached to an unrelated device. A
        # hub_get_device request is strongly scoped by its argument. A
        # hub_list_devices result must positively report this device ID.
        if row.get("sub_tool") == "hub_get_device":
            if str(inner.get("deviceId") or "") != target_device_id:
                continue
            # All explicit identity fields must agree; selecting a single
            # matching field must not conceal a second contradictory one.
            if any(
                details.get(field) not in (None, "")
                and str(details[field]) != target_device_id
                for field in ("deviceId", "id")
            ):
                continue
        else:
            reported = details.get("reportedDeviceState")
            if (not isinstance(reported, dict)
                    or str(reported.get("deviceId") or "") != target_device_id):
                continue
        candidates = [details]
        reported = details.get("reportedDeviceState")
        if isinstance(reported, dict):
            candidates.append(reported)
        for item in list(candidates):
            for key in _CONTAINERS:
                child = item.get(key)
                if isinstance(child, dict):
                    candidates.append(child)
        for item in candidates:
            # Only driver-context source metadata, not app source IDs or
            # arbitrary top-level typeId/device ID, can justify a source read.
            for key in _CODE_KEYS:
                if key == "sourceCodeId" and item is details:
                    continue
                value = _numeric_code_id(item.get(key))
                if value:
                    ids.add(value)
    return frozenset(ids)



def verified_driver_configuration_metadata(
    data: Any, target_device_id: str,
) -> dict[str, Any] | None:
    """Retain only an explicitly target-linked driver code ID, not raw config.

    The Hubitat configuration response must itself name the requested device.
    Device instance IDs, app code, generic type IDs and arbitrary nested
    numbers are NOT driver source identifiers.
    """
    if not isinstance(data, dict):
        return None
    target = str(target_device_id or "")
    observed = str(data.get("deviceId") or data.get("id") or "")
    if (
        not target.isdecimal() or observed != target
        or any(
            data.get(field) not in (None, "")
            and str(data[field]) != target
            for field in ("deviceId", "id")
        )
    ):
        return None
    candidates = []
    for container in _CONTAINERS:
        item = data.get(container)
        if not isinstance(item, dict):
            continue
        for field in _CODE_KEYS:
            candidate = _numeric_code_id(item.get(field))
            if candidate:
                candidates.append(candidate)
    ids = set(candidates)
    if len(ids) != 1:
        return {"deviceId": target, "driverSourceCodeIdentity": "unverified"}
    return {
        "deviceId": target,
        "driverSource": {"sourceCodeId": next(iter(ids))},
    }


def unverified_driver_source_read(
    tool_name: str,
    arguments: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    domain: str | None,
) -> bool:
    """True if model proposed a driver source code ID without target linkage."""
    if domain != "device_telemetry" or tool_name != "hub_read_apps_code":
        return False
    if arguments.get("tool") != "hub_get_source":
        return False
    args = arguments.get("args")
    if not isinstance(args, dict) or str(args.get("type") or "").casefold() != "driver":
        return False
    proposed = _numeric_code_id(args.get("id"))
    if proposed is None:
        return False  # Existing schema/required-field checks own malformed IDs.
    normalized = normalize_target_device_history(receipts)
    if not isinstance(normalized, dict):
        return False
    target_id = str(normalized.get("deviceId") or "")
    state = normalized.get("reportedDeviceState")
    if (not target_id.isdigit() or not isinstance(state, dict)
            or str(state.get("deviceId") or "") != target_id):
        return False  # No proven target, so do not intervene.
    return proposed not in _linked_driver_source_ids(receipts, target_id)


__all__ = ["unverified_driver_source_read", "verified_driver_configuration_metadata"]
