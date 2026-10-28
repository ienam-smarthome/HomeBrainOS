"""Source-scoped, read-only V2 whole-hub diagnostics presentation.

The model may select the diagnostic objective, but the host collects data via
the established read-only System Check. No model-provided device ID, command,
log text, tool name or credential is executed. Only bounded, redacted summaries
are returned to the test browser.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


def _safe(value: Any, *, limit: int = 240) -> str:
    text = str(value or "")[:2000]
    # Log messages are untrusted and may contain credential-bearing URLs.
    text = re.sub(r"https?://[^\s<>]+", "[URL redacted]", text, flags=re.I)
    text = re.sub(
        r"(?i)\b(token|apikey|api_key|authorization|password|secret|bearer)\b"
        r"\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", text
    )
    text = "".join(ch if ch.isprintable() and ch not in "<>{}\x60" else " "
                   for ch in text)
    return " ".join(text.split())[:limit]


def format_system_diagnostics(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Format an already-collected System Check without claiming full coverage."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("System Check source snapshot unavailable")
    sections = snapshot.get("sections")
    sections = sections if isinstance(sections, dict) else {}
    issues = snapshot.get("issues")
    issues = issues if isinstance(issues, list) else []
    log = sections.get("logs") if isinstance(sections.get("logs"), dict) else {}
    device = sections.get("devices") if isinstance(sections.get("devices"), dict) else {}
    automation = sections.get("automations") if isinstance(sections.get("automations"), dict) else {}
    verified_logs = log.get("available") is True
    checked = _safe(snapshot.get("checked_at"), limit=80)
    severity = snapshot.get("severity_counts")
    severity = severity if isinstance(severity, dict) else {}
    lines = [
        "**Whole-hub System Check — read-only**",
        "Checked at: " + (checked or "time unavailable"),
        "Status: " + _safe(snapshot.get("status") or "unknown", limit=32),
        ("Flagged findings: "
         + str(max(0, int(snapshot.get("attention_count") or 0)))
         + " (critical " + str(max(0, int(severity.get("critical") or 0)))
         + ", warning " + str(max(0, int(severity.get("warning") or 0))) + ")."),
        "",
        "**Source coverage**",
        "- Hub/device snapshot: " + (
            "available" if device.get("available") is not False and device
            else "not verified available"
        ),
        "- Automation inventory: " + (
            "available" if automation.get("available") is not False and automation
            else "not verified available"
        ),
        "- Hub logs: " + (
            "bounded sample of " + str(int(log.get("entries_checked") or 0))
            + " returned rows" if verified_logs
            else "unavailable or failed — no assertion about the absence of errors"
        ),
    ]
    checked_hours = log.get("checked_hours")
    if verified_logs and type(checked_hours) is int:
        lines.append(
            "- Requested log lookback: " + str(checked_hours)
            + " hours; actual retained start/end coverage not proven"
        )
    projected = []
    for issue in issues[:16]:
        if not isinstance(issue, dict):
            continue
        name = _safe(issue.get("title") or "Unnamed finding", limit=100)
        detail = _safe(issue.get("detail"), limit=220)
        level = _safe(issue.get("severity") or "info", limit=16)
        domain = _safe(issue.get("domain") or "unknown", limit=32)
        count = issue.get("count")
        count_text = (" (repeated " + str(count) + " times)"
                      if type(count) is int and count > 1 else "")
        projected.append({"severity": level, "domain": domain,
                          "title": name, "detail": detail,
                          "count": count if type(count) is int else None})
        lines.append("")
        lines.append(
            "- **" + level.upper() + " / " + domain + ": " + name + "**"
            + count_text + (". " + detail if detail else "")
        )
    if not projected:
        lines.extend(["", "No flagged findings in the returned System Check."])
    if len(issues) > len(projected):
        lines.append(str(len(issues)-len(projected))
                     + " more finding(s) not displayed; retained by System Check.")
    lines.extend([
        "",
        "**Limits:** This report is based on bounded MCP snapshots, not a"
        " complete historical log export. Reported device state is not"
        " independent physical proof. No Hubitat writes were requested.",
    ])
    if not verified_logs:
        lines.append(
            "Log audit was unavailable; do not interpret the System Check"
            " status as proof that the hub has no errors."
        )
    answer = "\n".join(lines)
    return {
        "answer_mode": "semantic_system_diagnostics",
        "answer": {
            "text": answer, "displayed_record_ids": [],
            "omitted_material_record_ids": [],
            "validation_issues": ([] if verified_logs else ["log_source_unavailable"]),
            "root_cause_verified": False,
            "human_review_required": not verified_logs,
        },
        "report": {"text": answer, "technical_answer_retained": True},
        "system_audit": {
            "checked_at": checked, "status": _safe(snapshot.get("status"), limit=32),
            "attention_count": snapshot.get("attention_count"),
            "log_available": verified_logs,
            "log_rows_returned": log.get("entries_checked") if verified_logs else None,
            "log_coverage_complete": False,
            "device_section_available": bool(device) and device.get("available") is not False,
            "automation_section_available": bool(automation) and automation.get("available") is not False,
            "findings": projected,
        },
        "resolved_devices": [],
        "resolution_method": "semantic_system_scope",
        "test_mode": "explicit_read_only",
    }


__all__ = ["format_system_diagnostics"]
