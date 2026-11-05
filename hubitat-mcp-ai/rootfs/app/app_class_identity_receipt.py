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



# Identity answer publication uses the same narrow, source-typed receipt
# contract as the technical coverage. Positive raw model assertions about
# app types, child rules, flags or built-in status are not attested merely
# because the model saw an unrestricted tool payload. Use a readable
# source-derived synthesis for this one evidence-certification domain when
# native class binding is incomplete. No extra model or MCP call is made.
_EXPLICIT_APP_ID = re.compile(
    r"(?i)\b(?:app(?:lication)?(?:\s+instance)?|instance)"
    r"\s*(?:id\s*)?#?\s*([1-9][0-9]{0,8})\b"
)
_IDENTITY_KINDS = frozenset((
    "typed_app_instance_metadata", "typed_app_class_identity",
))


def _matched_identity_receipts(
    receipts: list[dict[str, Any]],
    target: str | None,
) -> list[dict[str, Any]]:
    matched = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if (row.get("tool") != "hub_read_apps_code"
                or row.get("sub_tool") != "hub_get_app_config"
                or row.get("evidence_kind") not in _IDENTITY_KINDS
                or row.get("effect") != "read"
                or row.get("mutates") is not False):
            continue
        args = row.get("arguments")
        if not isinstance(args, dict) or args.get("tool") != "hub_get_app_config":
            continue
        scoped = args.get("args")
        details = row.get("details")
        if not isinstance(scoped, dict) or not isinstance(details, dict):
            continue
        app_id = _positive_id(details.get("appId"))
        if (app_id is None or _positive_id(scoped.get("appId")) != app_id
                or (target is not None and target != app_id)
                or details.get("nativeClassBindingVerified") is not False):
            continue
        if row["evidence_kind"] == "typed_app_class_identity":
            if _positive_id(details.get("appTypeId")) is None:
                continue
        elif "appTypeId" in details:
            # Do not silently upgrade summary-only evidence with an
            # unvalidated number attached to a weaker receipt kind.
            continue
        matched.append(details)
    return matched


def _source_value(
    rows: list[dict[str, Any]], key: str,
) -> tuple[bool, Any, bool]:
    """Return (present, value, conflicted), never resolve conflicting reads."""
    values = [row[key] for row in rows if key in row]
    if not values:
        return False, None, False
    if any(type(v) is not type(values[0]) or v != values[0] for v in values[1:]):
        return False, None, True
    return True, values[0], False


def reconcile_app_class_identity_answer(
    message: str,
    receipts: list[dict[str, Any]],
    coverage: dict[str, Any],
    request: str,
) -> tuple[str, bool]:
    """Publish only exact target-matched, source-observed app identity facts.

    The model selects relevant tools and reasons about which evidence to
    pursue. For a *still-unverified native-class identity* its final factual
    assertions cannot be audited from raw tool text, so publish the safe
    verified observations rather than guessing which sentence might contain
    an unsupported flag, type mapping or total child-rule claim.

    An independently observed native-class binding is reserved for a future
    separately validated source contract; this projector cannot create it.
    """
    draft = str(message or "").strip()
    requirements = coverage.get("requirements") or []
    native_state = next((
        entry.get("state") for entry in requirements
        if isinstance(entry, dict) and entry.get("key") == "native_class_binding"
    ), None)
    if native_state == "observed" and coverage.get("evidenceComplete") is True:
        return draft, False

    target_ids = set(_EXPLICIT_APP_ID.findall(str(request or "")))
    if len(target_ids) > 1:
        output = (
            "**Native class identity remains unverified.** The question "
            "names multiple app instances; each needs a separately "
            "target-matched typed record and authoritative class mapping. "
            "No type, system flag or child count is certified by an "
            "unscoped app inventory."
        )
        return output, output != draft

    target = next(iter(target_ids)) if target_ids else None
    observed = _matched_identity_receipts(receipts, target)
    if not target:
        candidates = {d["appId"] for d in observed}
        if len(candidates) == 1:
            target = next(iter(candidates))
        else:
            observed = []
    if target is not None:
        observed = [d for d in observed if d["appId"] == target]

    subject = ("App " + target) if target else "The requested app"
    if not observed:
        output = (
            "**Native class identity: not independently verified.** "
            + subject
            + " has no target-matched typed app metadata in the published "
              "read-only evidence. A successful inventory query or a model "
              "description cannot independently establish its name, type "
              "ID, built-in status or native parent class. An authoritative "
              "instance-to-type-to-native-class mapping is still needed."
        )
        return output, output != draft

    facts: list[str] = []
    disputed: list[str] = []
    for key, title in (
        ("reportedName", "name"),
        ("reportedLabel", "label"),
        ("reportedType", "type"),
        ("reportedAppTypeName", "app type name"),
    ):
        present, value, conflict = _source_value(observed, key)
        if conflict:
            disputed.append(title)
        elif present and (safe := _safe_label(value)) is not None:
            facts.append(f"{title} {safe!r}")
    present, value, conflict = _source_value(observed, "reportedNamespace")
    if conflict:
        disputed.append("namespace")
    elif present and isinstance(value, str) and _NAMESPACE.fullmatch(value):
        facts.append(f"namespace {value!r}")
    for key, title in (
        ("reportedSystem", "system"),
        ("reportedUser", "user"),
    ):
        present, value, conflict = _source_value(observed, key)
        if conflict:
            disputed.append(title)
        elif present and type(value) is bool:
            facts.append(f"{title}={str(value).lower()}")

    present, value, conflict = _source_value(observed, "appTypeId")
    if conflict:
        disputed.append("appTypeId")
    elif present and (valid_type := _positive_id(value)) is not None:
        facts.append(f"appTypeId={valid_type}")

    parents = [
        row["reportedParentAppId"] for row in observed
        if row.get("parentAppIdFieldPresent") is True
        and "reportedParentAppId" in row
    ]
    if parents and all(type(p) is type(parents[0]) and p == parents[0] for p in parents):
        parent = parents[0]
        if parent is None or _positive_id(parent) is not None:
            facts.append(
                "parentAppId=" + ("null" if parent is None else str(parent))
            )
    elif parents:
        disputed.append("parentAppId")

    # A childApps array describes rows returned in a bounded read, not
    # complete rule inventory, child type, executable rule status or ownership.
    child_counts = [
        row["returnedChildAppRows"] for row in observed
        if row.get("childCoverage") == "returned-page-only"
        and type(row.get("returnedChildAppRows")) is int
        and 0 <= row["returnedChildAppRows"] <= 1000
    ]
    if child_counts:
        if len(set(child_counts)) == 1:
            facts.append(f"{child_counts[0]} child-app rows returned in one page")
        else:
            disputed.append("returned child-app row count")

    text = (
        f"**{subject} — source-reported identity:** "
        + (", ".join(facts) + "." if facts else
           "No individual identity attributes were attested by the matching receipt.")
    )
    if disputed:
        text += (
            " Conflicting reads for " + ", ".join(disputed)
            + " were not treated as established facts."
        )
    text += (
        "\n\n**Native class/parent verification: unresolved.** "
        "These are reported fields from a target-matched read, not an "
        "authoritative binding between an instance, its app-type definition "
        "and a built-in native class. Child-app rows do not prove their "
        "types or the total installed rule count. "
        "A complete source-attested instance-to-type-to-native-class "
        "mapping is still required before certifying a native parent."
    )
    return text, text != draft


__all__ = ["project_app_class_identity_receipt", "reconcile_app_class_identity_answer"]
