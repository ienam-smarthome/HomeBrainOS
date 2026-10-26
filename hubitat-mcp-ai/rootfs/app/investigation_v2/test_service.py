"""Explicitly gated read-only Investigation V2 browser test service.

The admission gate uses an operator-set secret and live Hubitat device IDs.
It does not call production V1, disclose the key, change a device, or install
any model-proposed permission. No implicit background/shadow execution.
"""
from __future__ import annotations

import hmac
from typing import Any, Iterable


def require_test_access(*, enabled: bool, configured_token: str,
                        supplied_token: str, explicit_opt_in: bool) -> None:
    if enabled is not True or len(configured_token) < 16:
        raise PermissionError("v2_test_disabled")
    if explicit_opt_in is not True:
        raise PermissionError("explicit_opt_in_required")
    if not supplied_token or not hmac.compare_digest(configured_token, supplied_token):
        raise PermissionError("invalid_test_token")


def match_verified_device_ids(requested: Iterable[str],
                              live_devices: Any) -> tuple[str, ...]:
    """Allow only exact, independently observed IDs from refreshed inventory."""
    requested = list(requested)
    if not 1 <= len(requested) <= 4:
        raise ValueError("Select one to four device IDs")
    ids = []
    for item in requested:
        if not isinstance(item, str) or not item.isdecimal() or len(item) > 20:
            raise ValueError("Device IDs must be decimal strings")
        ids.append(item)
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate device ID")
    if not isinstance(live_devices, list):
        raise ValueError("Live Hubitat device inventory unavailable")
    verified = {
        str(d["id"]) for d in live_devices if isinstance(d, dict)
        and type(d.get("id")) in (int, str)
        and str(d["id"]).isdecimal()
    }
    if not verified or any(i not in verified for i in ids):
        raise ValueError("Device ID not verified in refreshed Hubitat inventory")
    return tuple(ids)


__all__ = ["require_test_access", "match_verified_device_ids"]
