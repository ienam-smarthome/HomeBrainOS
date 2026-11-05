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
    # Hubitat exposes two genuinely different shapes: a full result with an
    # app object, and a lightweight summary with fields at the top level.
    # Never borrow a missing appTypeId from the model's narrative or a separate
    # unconstrained catalog read.
    nested = data.get("app")
    if nested is not None and not isinstance(nested, dict):
        return None
    app = nested if nested is not None else data
    if _positive_id(app.get("id")) != target_id:
        return None
    if nested is not None and data.get("id") is not None:
        if _positive_id(data.get("id")) != target_id:
            return None
    if "appTypeId" in app:
        type_id = _positive_id(app["appTypeId"])
        if type_id is None:
            return None
    else:
        type_id = None

    # Self-reported metadata never proves the independent native class.
    # A summary lacking appTypeId still carries source-verifiable identity
    # fields, but cannot satisfy the stronger instance-to-type requirement.
    receipt: dict[str, Any] = {
        "appId": target_id,
        "identitySource": (
            "target-matched hub_get_app_config app metadata"
            if nested is not None else
            "target-matched hub_get_app_config summary metadata"
        ),
        "nativeClassBindingVerified": False,
    }
    if type_id is not None:
        receipt["appTypeId"] = type_id
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
    if type(app.get("user")) is bool:
        receipt["reportedUser"] = app["user"]
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



# A source's reported built-in-looking flags must not become a statement of
# independently verified native identity. The model remains responsible for
# selecting and synthesizing evidence; only an affirmative unsupported native
# certification is repaired from existing, source-matched read receipts.
_NATIVE_OVERCLAIM = re.compile(
    r"(?i)(?:\b(?:verified|confirmed|proven|established)\s+as\s+(?:an?\s+)?"
    r"(?:native|built[ -]?in|system)\b|"
    r"\b(?:confirming|proving|establishing)\s+(?:that\s+)?(?:it\s+is\s+)?"
    r"(?:an?\s+)?(?:native|built[ -]?in|system)\b|"
    r"\b(?:instance|application|app)[^.\n]{0,100}\b(?:confirmed|verified)"
    r"\s+to\s+be\s+(?:native|built[ -]?in|system)\b|"
    r"\b(?:native|built[ -]?in|system)\s+(?:Hubitat\s+)?"
    r"(?:class|parent|application|app)[^.\n]{0,75}\(Verified\))"
)
_EXPLICIT_APP_ID = re.compile(
    r"(?i)\b(?:app(?:lication)?(?:\s+instance)?|instance)"
    r"\s*(?:id\s*)?#?\s*([1-9][0-9]{0,8})\b"
)


def reconcile_app_class_identity_answer(
    message: str,
    receipts: list[dict[str, Any]],
    coverage: dict[str, Any],
    request: str,
) -> tuple[str, bool]:
    """Guard affirmative unsupported native class claims with typed facts.

    Keep the model's own calibrated natural language unless it certifies a
    native class despite the independently unverified source contract.
    Never make new source reads, invent omitted type IDs, or grant write access.
    """
    draft = str(message or "").strip()
    requirements = coverage.get("requirements") or []
    class_state = next((
        x.get("state") for x in requirements
        if isinstance(x, dict) and x.get("key") == "native_class_binding"
    ), None)
    # A negative sentence such as "not independently verified as native"
    # must not trigger an otherwise unnecessary model-text replacement.
    assertive = False
    for match in _NATIVE_OVERCLAIM.finditer(draft):
        before = draft[max(0, match.start() - 55):match.start()]
        negated = re.search(
            r"(?i)\b(?:not|never|without|unverified)\b"
            r"(?:\W+\w+){0,3}\s*$", before,
        )
        if not negated:
            assertive = True
            break
    if class_state == "observed" or not assertive:
        return draft, False

    ids = set(_EXPLICIT_APP_ID.findall(str(request or "")))
    # A multi-target request is not safe for a one-app fallback summary.
    target = next(iter(ids)) if len(ids) == 1 else None
    valid = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is not False or row.get("effect") != "read":
            continue
        if row.get("sub_tool") != "hub_get_app_config" or row.get("evidence_kind") not in (
            "typed_app_instance_metadata", "typed_app_class_identity",
        ):
            continue
        details = row.get("details")
        if not isinstance(details, dict) or details.get("nativeClassBindingVerified") is not False:
            continue
        identifier = _positive_id(details.get("appId"))
        if identifier is None or (target is not None and identifier != target):
            continue
        valid.append(details)

    if not target and len(set(d["appId"] for d in valid)) == 1:
        target = valid[0]["appId"]
    details_set = [d for d in valid if target and d["appId"] == target]

    def consistent(key: str) -> Any:
        values = [d[key] for d in details_set if key in d]
        if not values:
            return None
        return values[0] if all(v == values[0] for v in values) else None

    phrase = ("App " + target) if target else "The queried app"
    facts = []
    for field, title in (
        ("reportedName", "name"),
        ("reportedLabel", "label"),
        ("reportedType", "type"),
        ("reportedNamespace", "namespace"),
    ):
        value = consistent(field)
        if isinstance(value, str):
            facts.append(title + " " + repr(value))
    for field, title in (("reportedUser", "user"), ("reportedSystem", "system")):
        value = consistent(field)
        if isinstance(value, bool):
            facts.append(title + "=" + str(value).lower())
    if any("parentAppIdFieldPresent" in d for d in details_set):
        parents = [
            d.get("reportedParentAppId") for d in details_set
            if d.get("parentAppIdFieldPresent") is True
        ]
        if parents and all(x == parents[0] for x in parents):
            facts.append("parentAppId=" + ("null" if parents[0] is None else str(parents[0])))
    type_id = consistent("appTypeId")
    if type_id is not None:
        facts.append("appTypeId=" + str(type_id))

    if facts:
        first = (
            phrase + " has these **source-reported** fields: " +
            ", ".join(facts) + "."
        )
    else:
        first = (
            phrase + " was queried, but the public read receipts do not "
            "contain enough target-matched typed metadata to attest its "
            "reported name, type ID or class."
        )
    return (
        "**Native class identity: not independently verified.** " + first
        + " These reported fields do not by themselves establish that the "
        "instance is a built-in application parent or bind its type ID "
        "to an authoritative native class. "
        + "A complete, authoritative instance-to-type-to-native-class mapping "
        "is still required; a display name, namespace or user/system flag "
        "alone is not sufficient."
    ), True

__all__ = ["project_app_class_identity_receipt", "reconcile_app_class_identity_answer"]
