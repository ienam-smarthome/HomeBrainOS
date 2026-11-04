"""Source-scoped, no-write native Rule Machine readiness preflight.

This is a multi-objective read, not a Rule Machine inventory, date-trigger
acceptance, scheduling authorization, or a model-driven automation.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from mcp_client import tool_succeeded

_EXPECTED_SERVER = "hubitat-mcp-rule-server"
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?$")
_GUIDES = ("set_rule_reference", "builtin_app_tools_rules")


def is_native_rule_readiness_question(question: str) -> bool:
    """Read-only multi-source *positive* objective, ignoring prohibitions.

    Do not classify a rule-list request as readiness because it merely
    says 'do not create a backup' or 'do not call a tool guide'.
    """
    q = str(question or "")
    if not re.search(r"\bread[\s-]*only\b", q, re.I):
        return False
    if not re.search(r"\b(?:preflight|readiness|prerequisites?)\b", q, re.I):
        return False
    if not re.search(r"\b(?:rule machine|native rules?|mcp rule server)\b", q, re.I):
        return False
    clauses = re.split(r"[\n.!?]+", q)
    positive = " ".join(
        clause for clause in clauses
        if not re.match(r"^\s*(?:do not|don't|never|without|no)\b", clause, re.I)
    )
    version = bool(re.search(
        r"\b(?:mcp|server)\b[^.]{0,110}\bversion\b|"
        r"\bversion\b[^.]{0,110}\b(?:mcp|server)\b", positive, re.I
    ))
    backup = bool(re.search(
        r"\bbackup(?:s)?\b[^.]{0,110}\b(?:timestamp|inventory|freshness|newest|latest)\b|"
        r"\b(?:newest|latest|freshness)\b[^.]{0,110}\bbackup(?:s)?\b",
        positive, re.I
    ))
    guide = bool(re.search(
        r"\b(?:tool guides?|set_rule_reference|builtin_app_tools_rules)\b",
        positive, re.I
    ))
    return sum((version, backup, guide)) >= 2


def _server_version(mcp: Any) -> str | None:
    info = getattr(mcp, "server_info", None)
    if not isinstance(info, dict) or info.get("name") != _EXPECTED_SERVER:
        return None
    value = info.get("version")
    if not isinstance(value, str) or not _VERSION.fullmatch(value.strip()):
        return None
    return value.strip()


def _backup_timestamp(data: Any) -> tuple[str | None, int | None, str | None]:
    """Source-timed *latest* or explicit reason. Never guess from filename."""
    if not isinstance(data, dict):
        return None, None, "hub-local backup inventory unavailable"
    if (data.get("partial") is True or data.get("hubBackupErrors")
            or data.get("scope") not in (None, "hub_local")):
        return None, None, "hub-local backup inventory was partial or conflicted"
    records = data.get("hubLocalBackups")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        return None, None, "hub-local backup list was unavailable or malformed"
    if not records:
        return None, 0, "no hub-local backups returned"
    parsed = []
    for record in records:
        raw = record.get("createTimeOrig")
        if not isinstance(raw, str) or len(raw) > 80:
            return None, len(records), "backup timestamps were incomplete"
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None, len(records), "backup timestamps were not parseable"
        if when.tzinfo is None or when.utcoffset() is None:
            return None, len(records), "backup timestamps lacked an offset"
        parsed.append(when.astimezone(timezone.utc))
    return max(parsed).isoformat(), len(records), None


def native_rule_readiness_coverage(
    question: str, evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not is_native_rule_readiness_question(question):
        return None
    for item in reversed(evidence):
        if (not isinstance(item, dict)
                or item.get("evidence_kind") != "typed_native_rule_readiness"
                or item.get("effect") != "read"
                or item.get("mutates") is not False):
            continue
        d = item.get("details")
        if not isinstance(d, dict):
            continue
        complete = d.get("preflightEvidenceComplete") is True
        return {
            "domain": "native_rule_readiness",
            "status": "preflight-source-complete" if complete else "partial-evidence",
            "evidenceComplete": complete,
            "questionResolved": complete,
            "readinessForMutation": False,
            "requirements": [
                {
                    "key": key,
                    "state": "observed" if value else "checked-unverified",
                    "necessary": True,
                    "source": source,
                }
                for key, value, source in (
                    ("mcp_server_version", d.get("mcpServerVersion") is not None,
                     "MCP initialize serverInfo"),
                    ("hub_local_backup", d.get("latestHubLocalBackupUtc") is not None,
                     "read-only hub_list_backups(scope=hub_local)"),
                    ("native_rule_tool_guides", all(d.get("toolGuideAvailability", {}).values())
                     and len(d.get("toolGuideAvailability", {})) == 2,
                     "read-only hub_get_tool_guide sections"),
                )
            ],
            "limitations": [
                "Source checks do not verify date-trigger execution, a fresh-backup "
                "age against a live hub clock, disposable test-switch ownership "
                "or Internet-blocking enforcement."
            ],
        }
    return {
        "domain": "native_rule_readiness",
        "status": "partial-evidence",
        "evidenceComplete": False,
        "questionResolved": False,
        "readinessForMutation": False,
        "limitations": ["The requested read-only preflight was not executed."],
    }


async def read_native_rule_readiness(
    mcp: Any, recorder: Any, *,
    available_names: set[str] | frozenset[str],
) -> tuple[str, dict[str, Any]]:
    """At most three source calls; *only* the permitted read-only commands."""
    async def get(gateway: str, arguments: dict[str, Any], label: str) -> dict[str, Any] | None:
        request = arguments
        data = None
        start = time.monotonic()
        if gateway in available_names:
            try:
                result = await mcp.call_tool(gateway, request)
                if tool_succeeded(result) and isinstance(result.data, dict):
                    data = result.data
            except Exception:
                pass
        recorder.record(
            gateway, request,
            success=data is not None,
            elapsed_ms=round((time.monotonic() - start) * 1000),
            summary="Native rule read-only preflight: " + label,
            supports_live_claim=False, evidence_kind="native_rule_readiness_source",
            effect="read", mutates=False,
        )
        return data

    # MCP initialize serverInfo is an independent server-supplied identity,
    # not a hub firmware version nor the HomeBrain add-on's version number.
    version = _server_version(mcp)
    backup = await get(
        "hub_read_apps_code",
        {"tool": "hub_list_backups", "args": {"scope": "hub_local"}},
        "hub-local backup listing",
    )
    timestamp, count, backup_gap = _backup_timestamp(backup)
    guide_availability: dict[str, bool] = {}
    for section in _GUIDES:
        result = await get(
            "hub_get_tool_guide", {"section": section},
            "tool guide " + section,
        )
        content = result.get("content") if isinstance(result, dict) else None
        # Only a nonempty section-specific guide proves availability.
        # The secret/rotating acknowledgement key is NEVER published.
        marker = re.compile(
            r"I-HAVE-READ-THE-GUIDE-" + re.escape(section) + r"-[0-9a-fA-F]+"
        )
        guide_availability[section] = (
            isinstance(content, str) and len(content) > 0
            and bool(marker.search(content))
        )

    complete = (version is not None and timestamp is not None
                and all(guide_availability.values()))
    details = {
        "source": "MCP serverInfo + hub-local backups + native tool-guide sections",
        "mcpServerVersion": version,
        "mcpVersionSource": "MCP initialize serverInfo" if version else "unverified",
        "latestHubLocalBackupUtc": timestamp,
        "hubLocalBackupCount": count,
        "backupTimestampGap": backup_gap,
        "toolGuideAvailability": guide_availability,
        "preflightEvidenceComplete": complete,
        "readinessForMutation": False,
    }
    lines = [
        "**Native Rule Machine readiness — read-only preflight**", "",
        "MCP Rule Server version (server-supplied): "
        + (version or "unverified; no trustworthy serverInfo version"),
        "Newest hub-local backup (source timestamp): "
        + (timestamp or "unverified (" + (backup_gap or "not returned") + ")"),
        "Rule Machine tool-guide sections:",
    ]
    for section in _GUIDES:
        lines.append(
            "- " + section + ": "
            + ("readable" if guide_availability[section] else "unverified/unavailable")
        )
    lines.extend([
        "",
        "No backup, device, rule, action, or router setting was changed. "
        "Even complete read-only preflight evidence does not authorize a "
        "scheduled test, prove a fresh backup at the hub's current clock, "
        "or establish an Internet block.",
    ])
    recorder.record(
        "homebrain_native_rule_readiness", {},
        success=complete,
        elapsed_ms=0,
        summary="Source-scoped native Rule Machine readiness projection",
        supports_live_claim=complete,
        evidence_kind="typed_native_rule_readiness",
        effect="read", mutates=False,
        details=details,
    )
    return "\n".join(lines), details
