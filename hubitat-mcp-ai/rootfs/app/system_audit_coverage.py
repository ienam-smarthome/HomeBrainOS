"""Route-aware source sufficiency for whole-hub health and performance audits.

A whole-hub audit is not a historical causal investigation of a single device.
Section availability, bounded source sampling and actual unqueried components
must be tracked separately; tool success cannot establish an absence of faults.
"""
from __future__ import annotations

import re
from typing import Any


def assess_system_audit_sources(
    route: str,
    question: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    kind = str(route or "")
    question_lower = " ".join(str(question or "").lower().split())
    rows = [row for row in evidence if isinstance(row, dict)]
    health_audit = kind == "comprehensive-system-audit" and any(
        r.get("tool") == "health_audit.run" for r in rows
    )
    performance_audit = (
        kind != "comprehensive-system-audit"
        and bool(re.search(r"\b(?:audit|review|analyse|analyze|investigate)\b",
                           question_lower))
        and bool(re.search(r"\b(?:hub|system|performance)\b", question_lower))
        and any(r.get("evidence_kind") == "host_planned_performance_source"
                for r in rows)
    )
    if not (health_audit or performance_audit):
        return None
    checked: set[str] = set()
    capped = False
    if health_audit:
        domain = "system_health_audit"
        required = ["audit_devices", "audit_automations", "audit_logs"]
        for row in rows:
            if row.get("tool") != "health_audit.run":
                continue
            section = str(row.get("sub_tool") or "")
            if row.get("success") is True and section in {
                "devices", "automations", "logs"
            }:
                checked.add("audit_" + section)
                if section == "logs":
                    # The returned summary describes at most a bounded row
                    # sample, not an exhaustive historical log stream.
                    capped = True
    else:
        domain = "system_performance_audit"
        required = ["hub_metrics", "performance_stats", "diagnostic_logs"]
        # Device availability is an additional obligation only when actually
        # requested. Performance stats do not establish device reachability.
        if any(phrase in question_lower for phrase in (
            "offline device", "unavailable device", "device availability",
            "device health", "device connectivity",
        )):
            required.append("device_state")
        if any(phrase in question_lower for phrase in (
            "automation fault", "broken automation", "broken rule",
        )):
            required.append("automation_health")
        for row in rows:
            if row.get("success") is not True:
                continue
            tool = str(row.get("sub_tool") or "")
            if tool == "hub_get_metrics":
                checked.add("hub_metrics")
            if tool == "hub_get_performance_stats":
                checked.add("performance_stats")
            if tool == "hub_get_logs":
                checked.add("diagnostic_logs")
            if tool in ("hub_get_device_health", "hub_list_devices"):
                checked.add("device_state")
            if tool in ("hub_get_rule_health", "hub_list_rules"):
                checked.add("automation_health")
    missing = [key for key in required if key not in checked]
    bounded = bool(capped)
    partial = bool(missing or bounded)
    return {
        "domain": domain,
        "status": "partial-evidence" if partial else "source-checks-complete",
        "evidenceComplete": False if partial else None,
        "assessmentScope": "route-matched-whole-hub-read-only",
        "sourceCoverage": {
            "requiredSourceKinds": required,
            "checkedSourceKinds": sorted(checked),
            "missingSourceKinds": missing,
            "sourceKindsChecked": not missing,
            "note": (
                "A successful section/tool read establishes scoped evidence "
                "availability only, not that all faults or historical events "
                "were found."
            ),
        },
        "sourceIntegrityWarnings": (
            ["System Check log records form a bounded sample, not a complete "
             "historical log inventory."] if bounded else []
        ),
        "causalInitiatorVerified": None,
        "completionNote": (
            "A whole-hub health/performance audit does not require individual "
            "switch-event and command-history proof unless an individual "
            "historical cause is being investigated."
        ),
        "partial": partial,
        "missing": missing,
    }


__all__ = ["assess_system_audit_sources"]
