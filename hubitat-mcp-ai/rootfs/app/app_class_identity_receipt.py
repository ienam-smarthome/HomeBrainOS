"""Allowlisted, target-matched app-instance metadata from a Hubitat read.

A model can inspect raw MCP app configuration, but a generic field-name
receipt does not let later completion or the user audit its scalar claims.
Retain only safe reported values; never infer an authoritative native class
binding from a display label, a 'system' flag, or a missing parent.
"""
from __future__ import annotations

import re
from typing import Any


_ID = re.compile(r"[1-9][0-9]{0,8}\Z")
_NAMESPACE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,39}\Z")
_UNSAFE_LABEL = re.compile(
    r"(?i)(?:password|secret|api.?key|credential|bearer|token|https?://)"
)


def _positive_id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    raw = str(value)
    return raw if _ID.fullmatch(raw) else None


def _safe_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not (1 <= len(stripped) <= 96):
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in stripped):
        return None
    if any(ch in stripped for ch in "<>{}") or _UNSAFE_LABEL.search(stripped):
        return None
    return stripped


def project_app_class_identity_receipt(
    gateway: str, arguments: dict[str, Any], data: Any,
) -> dict[str, Any] | None:
    """Project source-observed instance metadata, NOT native-class proof.

    Only an explicit read of a matching app ID may establish instance
    identity. A type catalog can supply independent class evidence in a
    future, separately validated contract, but this self-report never can.
    """
    if gateway != "hub_read_apps_code" or not isinstance(arguments, dict):
        return None
    if arguments.get("tool") != "hub_get_app_config":
        return None
    args = arguments.get("args")
    if not isinstance(args, dict):
        return None
    target_id = _positive_id(args.get("appId"))
    if target_id is None or not isinstance(data, dict) or data.get("success") is False:
        return None
    app = data.get("app")
    if not isinstance(app, dict):
        return None
    if _positive_id(app.get("id")) != target_id:
        return None
    type_id = _positive_id(app.get("appTypeId"))
    if type_id is None:
        return None

    # Native class attestation deliberately absent: an app can report its
    # name and type, and be a system/root app, without establishing the
    # built-in class mapping that is needed to authorize Rule Machine writes.
    receipt: dict[str, Any] = {
        "appId": target_id,
        "appTypeId": type_id,
        "identitySource": "target-matched hub_get_app_config app metadata",
        "nativeClassBindingVerified": False,
    }
    for raw_field, receipt_field in (
        ("label", "reportedLabel"),
        ("name", "reportedName"),
        ("type", "reportedType"),
        ("appTypeName", "reportedAppTypeName"),
    ):
        safe = _safe_label(app.get(raw_field))
        if safe is not None:
            receipt[receipt_field] = safe
    namespace = app.get("namespace")
    if isinstance(namespace, str) and _NAMESPACE.fullmatch(namespace):
        receipt["reportedNamespace"] = namespace
    if type(app.get("system")) is bool:
        receipt["reportedSystem"] = app["system"]
    if "parentAppId" in app:
        parent = app["parentAppId"]
        if parent is None:
            receipt["reportedParentAppId"] = None
            receipt["parentAppIdFieldPresent"] = True
        else:
            parent_id = _positive_id(parent)
            if parent_id is not None:
                receipt["reportedParentAppId"] = parent_id
                receipt["parentAppIdFieldPresent"] = True

    children = data.get("childApps")
    if isinstance(children, list) and len(children) <= 1000:
        # Number of rows in THIS returned page, not proof of total children.
        receipt["returnedChildAppRows"] = len(children)
        receipt["childCoverage"] = "returned-page-only"

    return receipt


__all__ = ["project_app_class_identity_receipt"]
