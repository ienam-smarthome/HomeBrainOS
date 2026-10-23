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

    verified = _typed_health(receipts) + _typed_variables(receipts)
    lines = [
        banner, "",
        "### Verified from retained typed evidence",
        *(verified or ["- No typed rule-health or local-variable values were retained."]),
        "",
        "### Not independently verified",
        "- Complete triggers, ordered actions, nested IF structure, cancelable "
        "delay, device bindings and active/enabled status; successful app-page "
        "reads returned only generic response field names.",
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
