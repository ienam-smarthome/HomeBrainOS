"""Native Rule Machine parent identity attestation for writer preflights.

This is an exact-ID, non-rendering, read-only *validator* of externally
retrieved app summary fields. It does not query Hubitat, list rules or
make a decision to create, edit or delete an automation.
"""
from __future__ import annotations

import re
from typing import Any


def _id(value: Any) -> str | None:
    if type(value) not in (str, int):
        return None
    text = str(value)
    return text if re.fullmatch(r"[1-9]\d{0,8}", text) else None


def _native_parent_from_summary(
    summary: Any, *, candidate_id: str, candidate_type_id: str | None,
) -> tuple[dict[str, Any] | None, str]:
    """Only source-returned typed native app identity can prove parentage.

    The upstream summary=true read returns /installedapp/json/{id}; some
    firmware returns only id/name/type/user. That cannot prove namespace.
    """
    if not isinstance(summary, dict) or summary.get("success") is not True:
        return None, "native-app-summary-unavailable"
    root = summary.get("app") if isinstance(summary.get("app"), dict) else summary
    if _id(root.get("id")) != candidate_id:
        return None, "native-app-summary-id-mismatch"
    if root.get("user") is not False:
        return None, "native-app-summary-built-in-unverified"
    if root.get("parentId") not in (None, "") or root.get("parentAppId") not in (None, ""):
        return None, "native-app-summary-parent-conflict"
    if root.get("type") not in (None, "Rule Machine"):
        return None, "native-app-summary-type-conflict"
    reported_class_id = _id(root.get("appTypeId"))
    if (reported_class_id is not None and candidate_type_id is not None
            and reported_class_id != candidate_type_id):
        return None, "native-app-summary-class-id-conflict"
    # MCP 5.1.5 adds the source-observed namespace directly to the thin
    # summary=true response. It deliberately does not render an app page or
    # promise the full app.appType object. Older full/extended records may
    # carry that nested object instead. Never invent namespace from the label.
    flat_namespace = root.get("namespace")
    typed = root.get("appType")
    if typed is None:
        if flat_namespace is None:
            return None, "native-app-summary-class-namespace-unavailable"
        # Without a nested type, both identity fields must be attested by
        # the same thin app summary, not inferred from the instance listing.
        if flat_namespace != "hubitat" or root.get("type") != "Rule Machine":
            return None, "native-app-summary-class-namespace-unverified"
        type_id = None
    else:
        # A malformed or contradictory full type must not be silently
        # disregarded just because the flat namespace looks correct.
        if not isinstance(typed, dict):
            return None, "native-app-summary-class-namespace-unavailable"
        if typed.get("namespace") != "hubitat" or typed.get("name") != "Rule Machine":
            return None, "native-app-summary-class-namespace-unverified"
        if flat_namespace is not None and flat_namespace != typed.get("namespace"):
            return None, "native-app-summary-class-namespace-unverified"
        if typed.get("system") is False or typed.get("isBuiltIn") is False:
            return None, "native-app-summary-system-conflict"
        type_id = _id(typed.get("id"))
    if type_id is not None and candidate_type_id is not None and type_id != candidate_type_id:
        return None, "native-app-summary-class-id-conflict"
    return {
        "appId": candidate_id,
        "appTypeId": candidate_type_id or type_id,
        "namespace": "hubitat",
        "name": "Rule Machine",
        "proof": "source-typed-installed-app-summary",
    }, ""


