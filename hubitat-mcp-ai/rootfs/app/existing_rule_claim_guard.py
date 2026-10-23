"""Fail-closed, receipt-grounded output for installed Rule Machine verification.

A model may see app page content in its transient tool messages while final API
receipts only retain response key names. That is not enough for users (or the
completion contract) to audit claims about exact triggers, action order,
duplicate absence or controller delay settings. Until a typed projection
retains verifiable semantic facts, prefer a bounded partial report instead
of presenting unsupported specifics as verified configuration.
"""
from __future__ import annotations

import re
from typing import Any


def _gateway_arguments(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("arguments") or {}
    for _ in range(3):
        if not isinstance(args, dict):
            return {}
        inner = args.get("args")
        if not isinstance(inner, dict):
            break
        args = inner
    return args if isinstance(args, dict) else {}


def _target_id(row: dict[str, Any]) -> str:
    detail = row.get("details") or {}
    app_id = detail.get("appId") if isinstance(detail, dict) else None
    if app_id is None:
        app_id = _gateway_arguments(row).get("appId")
    return str(app_id or "")


def _typed_health(receipts: list[dict[str, Any]]) -> list[str]:
    lines = []
    observed = set()
    for row in receipts:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("evidence_kind") != "native_rule_evidence"
                or row.get("sub_tool") != "hub_get_rule_health"):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        app_id = _target_id(row)
        health = details.get("verifiedHealth")
        if (not app_id or not isinstance(health, dict)
                or any(not isinstance(health.get(k), bool)
                       for k in health if k in ("stopped", "broken"))):
            continue
        facts = [f"{key}={str(health[key]).lower()}"
                 for key in ("stopped", "broken") if type(health.get(key)) is bool]
        if not facts or app_id in observed:
            continue
        observed.add(app_id)
        lines.append(f"- App {app_id}: " + ", ".join(facts)
                     + " (typed rule-health receipt)")
    return lines


def _typed_variables(receipts: list[dict[str, Any]]) -> list[str]:
    lines = []
    seen = set()
    for row in receipts:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("evidence_kind") != "native_rule_evidence"
                or row.get("sub_tool") != "hub_list_rule_local_variables"):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        app_id = _target_id(row)
        count = details.get("returnedVariableCount")
        if (not app_id or type(count) is not int or count < 0
                or app_id in seen):
            continue
        seen.add(app_id)
        lines.append(f"- App {app_id}: {count} local variable(s) returned"
                     + " (bounded native variable read)")
    return lines


def _typed_setting_fragments(receipts: list[dict[str, Any]]) -> list[str]:
    """Render exact allowlisted current fields without certifying rule topology."""
    lines = []
    seen: set[str] = set()
    for row in receipts:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("evidence_kind") != "typed_existing_rule_partial_settings"
                or row.get("sub_tool") != "hub_get_app_config"):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict) or details.get("settingsReadable") is not True:
            continue
        app_id = _target_id(row)
        if (not app_id or app_id in seen
                or app_id != str(_gateway_arguments(row).get("appId") or "")):
            continue
        seen.add(app_id)
        fragments = []
        for fact in details.get("indexedFields") or []:
            if not isinstance(fact, dict):
                continue
            key = str(fact.get("key") or "")
            if not re.fullmatch(r"(?:delayMinute|cancelAct|onOffSwitch|onOff)\.[1-9]\d{0,3}", key):
                continue
            if "minutes" in fact and type(fact["minutes"]) in (int, float):
                fragments.append(f"{key}={fact['minutes']} minutes")
            elif "value" in fact and type(fact["value"]) is bool:
                fragments.append(f"{key}={str(fact['value']).lower()}")
            elif isinstance(fact.get("deviceIds"), list) and all(
                re.fullmatch(r"[1-9]\d{0,8}", str(x)) for x in fact["deviceIds"]
            ):
                fragments.append(f"{key} device IDs {', '.join(map(str, fact['deviceIds'][:8]))}")
        for fact in details.get("controllerFields") or []:
            if not isinstance(fact, dict):
                continue
            key = str(fact.get("key") or "")
            if key == "inactiveAction" and fact.get("value") in ("off", "on", "none"):
                fragments.append(f"{key}={fact['value']}")
            elif key in {"scheduledOffEnabled", "backupOffEnabled",
                         "verifyAfterOffEnabled", "manualOverrideEnabled"} and (
                    type(fact.get("value")) is bool):
                fragments.append(f"{key}={str(fact['value']).lower()}")
            elif re.fullmatch(
                r"(?:inactive|motionInactive|motionOff|backupOff|verifyAfterOff)"
                r"[A-Za-z]{0,36}(?:Seconds|Minutes|Delay)", key,
            ) and type(fact.get("numericValue")) in (int, float):
                fragments.append(
                    f"{key}={fact['numericValue']} "
                    f"({fact.get('unitFromKey') or 'unspecified unit'})"
                )
        if fragments:
            lines.append(f"- App {app_id}: " + "; ".join(fragments[:22])
                         + " (individual persisted setting values only)")
        if details.get("settingsTruncated") is True:
            lines.append(f"- App {app_id}: settings projection truncated; no "
                         "complete action tree or all-settings claim")
    return lines


def _page_read_observations(receipts: list[dict[str, Any]]) -> list[str]:
    """Present declassified editor page syntax as source text, never compiled logic."""
    out = []
    seen = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("tool") != "hub_read_apps_code" or row.get("sub_tool") != "hub_get_app_config":
            continue
        details = row.get("details")
        if not isinstance(details, dict) or details.get("pageReadVerified") is not True:
            continue
        args = _gateway_arguments(row)
        app_id = str(args.get("appId") or "")
        page = str(args.get("pageName") or "")
        if (not re.fullmatch(r"[1-9]\d{1,7}", app_id)
                or app_id != str(details.get("appId") or "")
                or page != details.get("pageName")
                or page not in ("selectActions", "selectTriggers")
                or (app_id, page) in seen):
            continue
        seen.add((app_id, page))
        actions = details.get("recognizedActionRows")
        if not isinstance(actions, list):
            continue
        if page == "selectTriggers":
            out.append(
                f"- App {app_id}: selectTriggers editor page was read; "
                "trigger contents not independently parsed or verified."
            )
            continue
        fragments = []
        for action in actions[:32]:
            if not isinstance(action, dict):
                continue
            kind = str(action.get("kind") or "")
            if kind not in {
                "cancel-delayed-actions", "if", "end-if", "else-if",
                "else", "off", "on", "delay",
            }:
                continue
            if kind == "delay":
                seconds = action.get("seconds")
                if type(seconds) is not int or not 0 <= seconds <= 86399:
                    continue
                qualifier = " (cancelable in page text)" if action.get("cancelable") is True else ""
                fragments.append(f"delay {seconds}s{qualifier}")
            else:
                fragments.append(kind)
        if fragments:
            out.append(
                f"- App {app_id}: selectActions editor page displayed "
                + " → ".join(fragments)
                + " (recognised rows, encounter order; may be incomplete)."
            )
        else:
            out.append(
                f"- App {app_id}: selectActions editor page was read, but no "
                "allowlisted action syntax was recoverable."
            )
        if details.get("pageRowsTruncated") is True:
            out.append(f"- App {app_id}: editor page observation was truncated.")
    return out


def calibrate_existing_rule_verification(
    message: str,
    receipts: list[dict[str, Any]],
    coverage: dict[str, Any] | None,
    *,
    request: str = "",
) -> str:
    """Never render unverified model interpretation as certified rule facts.

    Preserve substantive synthesis if typed, target-matched semantic evidence
    completed the stored-logic requirement. Otherwise replace it with a
    host-assembled partial report from verified evidence only.
    """
    draft = str(message or "").strip()
    if not isinstance(coverage, dict) or coverage.get("domain") != "existing_rule_verification":
        return draft
    banner = ("**Read-only existing-rule verification — no modifying Hubitat "
              "tool calls were recorded.**")
    # Avoid the legacy design-review heading regardless of the answer author.
    draft = re.sub(
        r"^\s*\*\*Read-only rule design review[^\n]*\*\*\s*",
        "", draft, count=1, flags=re.I,
    ).strip()
    requirements = {
        str(x.get("key")): str(x.get("state"))
        for x in coverage.get("requirements") or []
        if isinstance(x, dict)
    }
    if requirements.get("stored_logic") == "observed":
        return banner + "\n\n" + draft if draft else banner

    verified = (_typed_health(receipts) + _typed_variables(receipts)
                + _typed_setting_fragments(receipts))
    page_observations = _page_read_observations(receipts)
    lines = [
        banner, "",
        "### Verified from retained typed evidence",
        *(verified or ["- No typed rule-health or local-variable values were retained."]),
        "",
        "Individual setting values above establish only the named fields, "
        "not their position in a complete executable action tree.",
        "",
        *(["### Editor-page observations (not compiled rule facts)",
           *page_observations, ""] if page_observations else []),
        "### Not independently verified",
        "- Complete triggers, ordered actions, nested IF structure, action "
        "conditions, delay cancellation semantics and active/enabled status; "
        "partial settings are not a compiled action-tree export.",
        "- Exact-name duplicate absence or count; a rule-list response whose "
        "receipt exposes only field names cannot establish matching app IDs.",
        "- The comparison controller's effective inactivity-OFF duration, "
        "backup delay, active lockout countdown or interference with the target rule.",
        "- Runtime triggering, delay cancellation and actual OFF commands.",
        "",
        "**Investigation remains partial.** Retrieve a target-matched, typed "
        "configuration/action-tree projection and complete exact-name rule "
        "inventory before certifying these points. No device or automation "
        "changes are authorised by this report.",
    ]
    return "\n".join(lines)


__all__ = ["calibrate_existing_rule_verification"]
