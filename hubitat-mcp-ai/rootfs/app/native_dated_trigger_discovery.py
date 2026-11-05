"""Source-bounded discovery of *existing* native dated Rule Machine triggers.

Runs only for an explicit read-only existing-dated-trigger investigation.
The native hub_set_rule operation=read returns persisted state without
rendering the editor. Do not call operation=form, mutate a rule, or infer
that no dated rules exist from an incomplete/hidden app inventory.
"""
from __future__ import annotations

from datetime import date
import re
import time
from typing import Any

from mcp_client import MCPTool, tool_succeeded
from tool_registry import ToolEffect, classify_tool_effect

_READ_GATEWAYS = ("hub_manage_native_rules_and_apps", "hub_manage_rule_machine")
_PAGE_LIMIT = 4
_SCAN_LIMIT = 12
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/()-]{0,95}$")
_ID = re.compile(r"^[1-9][0-9]{0,8}$")
_FIELD = re.compile(r"^(time|atTime|date|atDate)([1-9][0-9]{0,3})$")
_OFFSET = re.compile(r"\b(?:scan\s+)?offset\s*[:=]?\s*([0-9]{1,4})\b", re.I)
_REDACT = re.compile(r"(?i)(password|secret|token|api.?key|credential)")


def is_existing_dated_trigger_question(question: str) -> bool:
    """Positive request for stored dated triggers, not prospective creation."""
    text = str(question or "")
    return bool(
        re.search(r"\bread[ -]?only\b", text, re.I)
        and re.search(r"\bexisting\b|\balready[ -]?existing\b", text, re.I)
        and re.search(r"\b(?:rule machine|native rule)\b", text, re.I)
        and re.search(r"\b(?:dated triggers?|certain time|atDate#|date field)\b", text, re.I)
        and re.search(r"\b(?:search|inspect|investigat|find|scan|readback)\w*\b", text, re.I)
        # Prohibitions such as "Do not create a test rule" are restrictions,
        # not a positive creation intent. The explicit existing/read-only
        # requirements above are the authority for this narrow read route.
    )


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    raw = str(value)
    return raw if _ID.fullmatch(raw) else None


def _safe_name(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_LABEL.fullmatch(value.strip()) and not _REDACT.search(value):
        return value.strip()
    return None


def _requested_offset(question: str) -> int:
    match = _OFFSET.search(question or "")
    value = int(match.group(1)) if match else 0
    return value if 0 <= value <= 500 else 0


def _date(value: Any) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def project_existing_dated_fields(document: Any, rule_id: str) -> dict[str, Any] | None:
    """Project only relevant persisted fields; never raw settings or app code."""
    if not isinstance(document, dict) or _id(document.get("rule_id")) != rule_id:
        return None
    if document.get("truncated") is True or document.get("nextCursor") is not None:
        return None
    settings, triggers = document.get("settings"), document.get("triggers")
    if not isinstance(settings, list) or len(settings) > 256:
        return None
    if not isinstance(triggers, dict) or len(triggers) > 100:
        return None
    typed: dict[str, dict[str, Any]] = {}
    for row in settings:
        if not isinstance(row, dict):
            return None
        name = row.get("name")
        match = _FIELD.fullmatch(name) if isinstance(name, str) else None
        if match is None:
            continue
        field, index = match.groups()
        kind = row.get("type")
        expected = {"time": "enum", "atTime": "time", "date": "bool", "atDate": "date"}[field]
        # A mis-typed or duplicated field must never become valid readback.
        entry = typed.setdefault(index, {})
        if field in entry:
            return None
        observed: dict[str, Any] = {"name": name, "type": kind}
        value = row.get("value")
        observed["typeMatchesExpected"] = kind == expected
        if kind == expected:
            if field == "date" and type(value) is bool:
                observed["value"] = value
            elif field == "atDate" and (valid := _date(value)) is not None:
                observed["value"] = valid
            elif field in ("time", "atTime") and isinstance(value, str) and len(value) <= 80 and not _REDACT.search(value):
                observed["value"] = value
        entry[field] = observed
    returned: list[dict[str, Any]] = []
    for idx in sorted(typed, key=int):
        fields = typed[idx]
        toggle = fields.get("date") or {}
        at_date = fields.get("atDate") or {}
        time_field = fields.get("time") or {}
        at_time = fields.get("atTime") or {}
        has_trigger = idx in triggers and isinstance(triggers[idx], str)
        positive = bool(
            has_trigger
            and toggle.get("typeMatchesExpected") is True
            and toggle.get("value") is True
            and at_date.get("typeMatchesExpected") is True
            and _date(at_date.get("value")) is not None
            and time_field.get("typeMatchesExpected") is True
            and isinstance(time_field.get("value"), str)
            and at_time.get("typeMatchesExpected") is True
            and isinstance(at_time.get("value"), str)
        )
        returned.append({
            "triggerId": idx,
            "fields": fields,
            "nativeTriggerRowPresent": has_trigger,
            "savedDatedFieldSetObserved": positive,
            "dateEnabled": toggle.get("value") if type(toggle.get("value")) is bool else None,
        })
    return {
        "ruleId": rule_id,
        "source": "hub_set_rule:read",
        "requestedSections": ["triggers", "settings"],
        "returnedDateFieldGroups": returned[:32],
        "projectionTruncated": len(returned) > 32,
        "savedDatedFieldSetObserved": any(x["savedDatedFieldSetObserved"] for x in returned),
        "completeRequestedSections": True,
        "runtimeExecutionVerified": False,
    }


async def read_existing_dated_triggers(
    mcp: Any, recorder: Any, *,
    question: str,
    available_names: set[str] | frozenset[str],
) -> tuple[str, dict[str, Any]]:
    """At most four inventory pages and twelve approved native *read* calls."""
    offset = _requested_offset(question)
    seen_ids: set[str] = set()
    candidates: list[dict[str, str]] = []
    pages_read = 0
    pages_complete = False
    cursor: str | None = None
    if "hub_read_apps_code" in available_names:
        for _ in range(_PAGE_LIMIT):
            args: dict[str, Any] = {"scope": "instances", "filter": "children"}
            if cursor is not None:
                args["cursor"] = cursor
            call = {"tool": "hub_list_apps", "args": args}
            st = time.monotonic()
            try:
                reply = await mcp.call_tool("hub_read_apps_code", call)
                data = getattr(reply, "data", None)
                good = tool_succeeded(reply) and isinstance(data, dict)
            except Exception:
                data, good = None, False
            recorder.record(
                "hub_read_apps_code", call, success=bool(good),
                elapsed_ms=round((time.monotonic() - st) * 1000),
                summary="Read-only existing Rule Machine child-app inventory page",
                evidence_kind="native_dated_discovery_inventory_source",
                supports_live_claim=False, effect="read", mutates=False,
            )
            if not good or not isinstance(data.get("apps"), list):
                break
            pages_read += 1
            for item in data["apps"]:
                if not isinstance(item, dict) or item.get("type") != "Rule-5.1" or item.get("user") is not False:
                    continue
                ident = _id(item.get("id"))
                parent = _id(item.get("parentId"))
                if ident is None or parent is None or ident in seen_ids:
                    continue
                seen_ids.add(ident)
                candidates.append({"id": ident, "parentId": parent,
                                   "label": _safe_name(item.get("name")) or "(label withheld)"})
            next_cursor = data.get("nextCursor")
            if next_cursor is None:
                pages_complete = True
                break
            if not isinstance(next_cursor, str) or not next_cursor.isdigit() or next_cursor == cursor:
                break
            cursor = next_cursor

    candidates.sort(key=lambda row: int(row["id"]))
    selected = candidates[offset:offset + _SCAN_LIMIT]
    gateway = next((g for g in _READ_GATEWAYS if g in available_names), None)
    scanned = []
    verified = []
    if gateway:
        for candidate in selected:
            rule_id = candidate["id"]
            args = {"tool": "hub_set_rule", "args": {
                "operation": "read", "rule_id": int(rule_id),
                "args": {"sections": ["triggers", "settings"]},
            }}
            if classify_tool_effect(MCPTool(gateway, gateway, {}), args) is not ToolEffect.READ:
                break
            st = time.monotonic()
            try:
                reply = await mcp.call_tool(gateway, args)
                success = tool_succeeded(reply)
                result = project_existing_dated_fields(
                    getattr(reply, "data", None), rule_id,
                ) if success else None
            except Exception:
                result = None
            recorder.record(
                gateway, args, success=result is not None,
                elapsed_ms=round((time.monotonic() - st) * 1000),
                summary=("Persisted native dated-field read verified"
                         if result is not None else "Native dated-field read unavailable or incomplete"),
                evidence_kind="typed_native_dated_trigger_fields",
                supports_live_claim=result is not None,
                effect="read", mutates=False,
                details=result if result is not None else {"ruleId": rule_id, "source": "hub_set_rule:read"},
            )
            scanned.append({"ruleId": rule_id, "readVerified": result is not None})
            if result and result["savedDatedFieldSetObserved"]:
                verified.append({"ruleId": rule_id, "label": candidate["label"],
                                 "evidence": result["returnedDateFieldGroups"]})
                break

    more = bool(offset + len(scanned) < len(candidates) or not pages_complete)
    proof = bool(verified)
    details = {
        "source": "hub_list_apps children + hub_set_rule:read",
        "inventoryPagesRead": pages_read,
        "inventoryPageTraversalComplete": pages_complete,
        "eligibleVisibleNativeRules": len(candidates),
        "scanOffset": offset,
        "scanLimit": _SCAN_LIMIT,
        "scannedRuleIds": scanned,
        "nativeReadGatewayAvailable": gateway is not None,
        "savedDatedFieldReadbackVerified": proof,
        "verifiedDatedRules": verified,
        "moreCandidatesMayExist": more,
        "absenceProven": False,
        "readinessForMutation": False,
    }
    recorder.record(
        "homebrain_native_dated_trigger_discovery", {},
        success=True, elapsed_ms=0, effect="read", mutates=False,
        supports_live_claim=proof,
        evidence_kind="typed_native_dated_trigger_discovery",
        summary="Bounded read-only existing native Rule Machine date-field scan",
        details=details,
    )
    lines = ["**Existing native dated-trigger discovery — read-only**",
             f"Visible native Rule-5.1 candidates in returned inventory: {len(candidates)}.",
             f"Inventory pages read: {pages_read}; page traversal complete: {'yes' if pages_complete else 'no'}.",
             f"Scan offset: {offset}; attempted native rule reads: {len(scanned)}.",
             "Read source: hub_set_rule(operation=read), triggers and settings only; no editor form was opened."]
    if gateway is None:
        lines.append("Approved native rule-document read gateway unavailable; no trigger state was inspected.")
    if verified:
        first = verified[0]
        dates = []
        for entry in first["evidence"]:
            if entry["savedDatedFieldSetObserved"]:
                val = entry["fields"]["atDate"]["value"]
                dates.append(f"trigger {entry['triggerId']} atDate={val}, date enabled")
        lines.append(f"**Stored dated fields found in rule {first['ruleId']} ({first['label']}):** " + "; ".join(dates) + ".")
        lines.append("The saved date/time fields and native trigger row are source-observed; actual scheduling, firing and one-shot semantics are NOT established.")
    else:
        lines.append("**No verified enabled dated-trigger field set was found in this bounded scan.** This is not evidence that none exist.")
    if more:
        lines.append(f"Additional visible candidates or pages may remain. Resume with scan offset {offset + len(scanned)}; no absence verdict is possible.")
    lines.append("No modifying Hubitat calls, form opens, or writer authorization. Native dated-rule creation remains blocked.")
    return "\n\n".join(lines), details


def existing_dated_trigger_coverage(
    question: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not is_existing_dated_trigger_question(question):
        return None
    for row in reversed(receipts):
        if not isinstance(row, dict) or row.get("evidence_kind") != "typed_native_dated_trigger_discovery":
            continue
        if (row.get("tool") != "homebrain_native_dated_trigger_discovery"
                or row.get("effect") != "read" or row.get("mutates") is not False):
            continue
        data = row.get("details")
        if not isinstance(data, dict) or data.get("source") != "hub_list_apps children + hub_set_rule:read":
            continue
        resolved = data.get("savedDatedFieldReadbackVerified") is True and bool(data.get("verifiedDatedRules"))
        return {
            "domain": "native_dated_trigger_discovery",
            "status": "dated-field-readback-observed" if resolved else "partial-evidence",
            "evidenceComplete": resolved,
            "questionResolved": resolved,
            "readinessForMutation": False,
            "requirements": [
                {"key": "native_rule_inventory", "state": "observed" if data.get("inventoryPagesRead", 0) > 0 else "checked-unverified"},
                {"key": "existing_dated_trigger_readback", "state": "observed" if resolved else "checked-unverified"},
            ],
            "limitations": [
                "A bounded sample cannot prove that no dated rules exist; "
                "stored date fields cannot verify scheduling or runtime firing."
            ],
        }
    return {
        "domain": "native_dated_trigger_discovery",
        "status": "partial-evidence",
        "evidenceComplete": False,
        "questionResolved": False,
        "readinessForMutation": False,
        "limitations": ["No typed read-only native dated-trigger discovery projection was published."],
    }


__all__ = [
    "is_existing_dated_trigger_question", "read_existing_dated_triggers",
    "project_existing_dated_fields", "existing_dated_trigger_coverage",
]
