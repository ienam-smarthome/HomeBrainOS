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


def _extra_requested_checks(question: str) -> tuple[bool, bool, bool]:
    """Additional read-only proof obligations beyond the core 3-source preflight."""
    q = str(question or "")
    version_comparison = bool(re.search(
        r"\bhub_get_info\b|(?:serverInfo|initialize)[^\n.]{0,100}"
        r"(?:agree|match|compare|cross.check)", q, re.I,
    ))
    dated_contract = bool(re.search(
        r"atDate#|Certain Time\s*\(and optional date\)|"
        r"\bdated\b[^\n.]{0,85}\b(?:trigger|one.time|rule)\b|"
        r"\bdate[\s-]*field\b", q, re.I,
    ))
    readback = dated_contract and bool(re.search(
        r"\bread[\s-]*back\b|\bpersisted\b|\b(saved|stored)\s+date\b",
        q, re.I,
    ))
    return version_comparison, dated_contract, readback


def _guide_dated_field_attestation(content: Any) -> bool:
    """Only an explicit date *field* declaration attests documentation.

    Generic 'date supported' or a release version is insufficient; neither
    a guide nor this check attests persisted state or allows a rule write.
    """
    if not isinstance(content, str) or len(content) > 50000:
        return False
    return bool(
        re.search(r"atDate#", content, re.I)
        and re.search(r"(?i)\btype\s*[:=]\s*[\"']?date\b", content)
        and re.search(r"yyyy-MM-dd|YYYY-MM-DD", content)
        and not re.search(r"(?i)atDate#[^\n]{0,100}supported\s*[:=]\s*false", content)
    )


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
    want_version, want_date, want_readback = _extra_requested_checks(question)
    for item in reversed(evidence):
        if (not isinstance(item, dict)
                or item.get("evidence_kind") != "typed_native_rule_readiness"
                or item.get("tool") != "homebrain_native_rule_readiness"
                or item.get("success") is not True
                or item.get("effect") != "read"
                or item.get("mutates") is not False):
            continue
        d = item.get("details")
        if not isinstance(d, dict):
            continue
        # Keep the core preflight distinct from a request to establish actual
        # native dated-field support, version agreement or persisted readback.
        preflight_complete = d.get("preflightEvidenceComplete") is True
        version_ok = d.get("mcpVersionAgreement") is True
        guide_date_ok = d.get("nativeDatedFieldGuideAttested") is True
        readback_ok = d.get("nativeDatedDateReadbackVerified") is True
        complete = (
            preflight_complete
            and (not want_version or version_ok)
            and (not want_date or guide_date_ok)
            and (not want_readback or readback_ok)
        )
        checks = [
            ("mcp_server_version", d.get("mcpServerVersion") is not None,
             "MCP initialize serverInfo"),
            ("hub_local_backup", d.get("latestHubLocalBackupUtc") is not None,
             "read-only hub_list_backups(scope=hub_local)"),
            ("native_rule_tool_guides",
             isinstance(d.get("toolGuideAvailability"), dict)
             and len(d["toolGuideAvailability"]) == 2
             and all(v is True for v in d["toolGuideAvailability"].values()),
             "read-only hub_get_tool_guide sections"),
        ]
        if want_version:
            checks.append((
                "mcp_version_agreement", version_ok,
                "MCP initialize serverInfo and read-only hub_get_info.mcpServerVersion",
            ))
        if want_date:
            checks.append((
                "native_dated_field_guide", guide_date_ok,
                "installed set_rule_reference explicit atDate# date declaration",
            ))
        if want_readback:
            checks.append((
                "native_dated_date_readback", readback_ok,
                "read-only native dated Rule Machine trigger state",
            ))
        return {
            "domain": "native_rule_readiness",
            "status": "preflight-source-complete" if complete else "partial-evidence",
            "evidenceComplete": complete,
            "questionResolved": complete,
            "preflightEvidenceComplete": preflight_complete,
            "readinessForMutation": False,
            "requirements": [
                {"key": k, "state": "observed" if ok else "checked-unverified",
                 "necessary": True, "source": origin}
                for k, ok, origin in checks
            ],
            "limitations": [
                "Source checks do not authorise Rule Machine creation, confirm "
                "a native date-trigger write/readback, prove a fresh backup "
                "against live hub time, or verify target device ownership."
            ],
        }
    return {
        "domain": "native_rule_readiness",
        "status": "partial-evidence",
        "evidenceComplete": False,
        "questionResolved": False,
        "preflightEvidenceComplete": False,
        "readinessForMutation": False,
        "limitations": ["No typed native Rule Machine preflight receipt was published."],
    }


async def read_native_rule_readiness(
    mcp: Any, recorder: Any, *,
    available_names: set[str] | frozenset[str],
    question: str = "",
) -> tuple[str, dict[str, Any]]:
    """Core three source reads; optional hub_get_info for explicit cross-check.

    No write, model round, confirmation, or secret guide token is published.
    """
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
    want_version, want_date, want_readback = _extra_requested_checks(question)
    hub_info_version: str | None = None
    if want_version:
        info = await get("hub_get_info", {}, "installed server version check")
        candidate = info.get("mcpServerVersion") if isinstance(info, dict) else None
        if isinstance(candidate, str) and _VERSION.fullmatch(candidate.strip()):
            hub_info_version = candidate.strip()
    version_agrees = (
        version == hub_info_version
        if version is not None and hub_info_version is not None else None
    )
    backup = await get(
        "hub_read_apps_code",
        {"tool": "hub_list_backups", "args": {"scope": "hub_local"}},
        "hub-local backup listing",
    )
    timestamp, count, backup_gap = _backup_timestamp(backup)
    guide_availability: dict[str, bool] = {}
    dated_field_attested = False
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
        if section == "set_rule_reference" and want_date:
            dated_field_attested = (
                guide_availability[section]
                and _guide_dated_field_attestation(content)
            )

    complete = (version is not None and timestamp is not None
                and all(guide_availability.values()))
    details = {
        "source": "MCP serverInfo + hub-local backups + native tool-guide sections",
        "mcpServerVersion": version,
        "mcpVersionSource": "MCP initialize serverInfo" if version else "unverified",
        "hubInfoMcpServerVersion": hub_info_version,
        "mcpVersionAgreement": version_agrees,
        "nativeDatedFieldGuideAttested": dated_field_attested,
        # No actual dated-rule ID was supplied for a read-back; do not
        # silently infer persistence from an installed guide or changelog.
        "nativeDatedDateReadbackVerified": False,
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
    if want_version:
        lines.extend([
            "MCP Rule Server version from hub_get_info: "
            + (hub_info_version or "not verified"),
            "Initialize/hub_get_info version agreement: "
            + ("verified" if version_agrees is True else
               "conflict" if version_agrees is False else "not verified"),
        ])
    if want_date:
        lines.append(
            "Installed guide explicitly documents atDate# as a date field: "
            + ("yes (guide only; no persisted date proven)"
               if dated_field_attested else "not verified")
        )
    if want_readback:
        lines.append(
            "Native dated-trigger saved-state readback: not checked; "
            "no matching existing dated rule was identified by this preflight."
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
