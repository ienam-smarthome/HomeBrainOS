"""Bounded read-only automation dependency inspection for full hub audits.

Separation of proof:
  * An app ID matching a scheduler key is a candidate, not callback ownership.
  * A current app config is proof of current settings, not historical execution.
  * Identical textual action labels are a possible overlap, not shared device ID.
  * Only typed device IDs inside action-scoped structures are ID-level edges.
No passwords, raw settings, URLs, source code, or whole configuration dumps are
stored in receipts or reported to the user.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from mcp_client import tool_succeeded

_MAX_APPS = 6
_MAX_PARAGRAPHS = 24
_RELEVANT = re.compile(r"\b(?:heartbeat|redundan|failover|backup hub|"
                       r"light|lighting|lamp|dimmer|motion)\b", re.I)
_ACTION = re.compile(
    r"(?:\bTHEN\b\s*)?(?:\b(?:on|off|toggle|dim|set\s+level|"
    r"set\s+color|turn\s+on|turn\s+off)\s*:\s*)([^.;\n]{1,85})", re.I
)
_URL = re.compile(r"(?:https?://|www\.|%[0-9a-f]{2})", re.I)
_SECRET = re.compile(r"(?i)\b(?:token|secret|password|api.?key|authorization|"
                     r"credential|private|username|pin)\b")
_STATUS = {"active", "disabled", "paused", "broken", "unknown"}
_TARGET_ID_KEYS = {"deviceid", "deviceids", "targetdeviceid", "targetdeviceids"}
_SENSITIVE = re.compile(r"(?i)(?:https?://\S+|www\.\S+|"
                        r"(?:api.?key|token|password|secret)\s*[:=]\s*\S+)")


def _safe(text: Any, n: int = 110) -> str:
    value = re.sub(r"[<>\r\n\x60\[\]{}|*]", " ", str(text or ""))
    value = _SENSITIVE.sub("[redacted]", value)
    return re.sub(r"\s+", " ", value).strip()[:n]


def select_automation_probes(
    automation_section: dict[str, Any] | None,
    job_summary: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Pick confirmed installed IDs by deterministic impact class; no hardcodes."""
    if not isinstance(automation_section, dict) or not isinstance(job_summary, dict):
        return []
    if job_summary.get("status") != "parsed":
        return []
    rows = automation_section.get("inventory_identities")
    candidates_by_type = job_summary.get("candidateIdsByType")
    if not isinstance(rows, list) or not isinstance(candidates_by_type, dict):
        return []
    candidates = {
        str(v) for v in candidates_by_type.get("app", [])
        if str(v).isdigit()
    } if isinstance(candidates_by_type.get("app"), list) else set()
    installed: dict[str, dict[str, str]] = {}
    for item in rows[:500]:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "")
        if not ident.isdigit() or ident in installed:
            continue
        installed[ident] = {
            "id": ident,
            "name": _safe(item.get("name") or "Unnamed automation"),
            "status": str(item.get("status") or "unknown").casefold(),
            "type": str(item.get("type") or "app"),
        }

    def choose(predicate, reason: str, maximum: int, existing: set[str]):
        selected = []
        for item in sorted(installed.values(), key=lambda r: int(r["id"])):
            if item["id"] in existing or not predicate(item):
                continue
            selected.append({**item, "reason": reason})
            existing.add(item["id"])
            if len(selected) == maximum:
                break
        return selected

    visited: set[str] = set()
    disabled = choose(
        lambda row: row["id"] in candidates and row["status"] == "disabled",
        "disabled configuration + scheduler-key candidate",
        2, visited,
    )
    heartbeat = choose(
        lambda row: bool(re.search(r"(?i)\b(?:heartbeat|failover|redundan)\b", row["name"])),
        "heartbeat/failover configuration candidate",
        1, visited,
    )
    lighting = choose(
        lambda row: bool(re.search(r"(?i)\b(?:lighting|light|lamp|dimmer)\b", row["name"]))
        and row["status"] in _STATUS,
        "lighting dependency comparison candidate",
        _MAX_APPS - len(disabled) - len(heartbeat), visited,
    )
    return (disabled + heartbeat + lighting)[:_MAX_APPS]


def _app_record(response: Any, expected: str) -> dict[str, Any] | None:
    if not isinstance(response, dict) or response.get("success") is False:
        return None
    app = response.get("app")
    if not isinstance(app, dict) or str(app.get("id") or "") != expected:
        return None
    page = response.get("page")
    if not isinstance(page, dict) or not isinstance(page.get("sections"), list):
        return None
    return response


def _ids(value: Any) -> set[str]:
    if isinstance(value, int) and 0 < value < 10**9:
        return {str(value)}
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d{1,8}", value):
        return {value}
    if isinstance(value, list):
        return set.union(set(), *(_ids(item) for item in value[:30]))
    return set()


def _explicit_action_ids(page: dict[str, Any]) -> list[str]:
    """Action-scoped *typed* references only; never mine numbers from prose."""
    found: set[str] = set()

    def visit(item: Any, in_action: bool, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(item, dict):
            for key, value in list(item.items())[:40]:
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                action = in_action or normalized in ("action", "actions", "actiondevices",
                                                    "target", "targets", "then")
                if action and normalized in _TARGET_ID_KEYS:
                    found.update(_ids(value))
                elif isinstance(value, (dict, list)):
                    visit(value, action, depth + 1)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child, in_action, depth + 1)

    # Page sections may have specific action-scoped input fields. Do not
    # interpret raw config paragraph text as an authoritative device ID.
    visit(page.get("actions", []), True, 0)
    for section in page.get("sections", [])[:24]:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "")
        if re.search(r"(?i)\b(?:action|then)\b", title):
            visit(section.get("inputs", []), True, 0)
            visit(section.get("devices", []), True, 0)
    return sorted(found, key=int)[:20]


def summarise_config(data: dict[str, Any], ident: str) -> dict[str, Any] | None:
    verified = _app_record(data, ident)
    if verified is None:
        return None
    page = verified["page"]
    action_labels: set[str] = set()
    trigger_present = False
    action_present = False
    paragraph_count = 0
    for section in page.get("sections", [])[:24]:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "")
        if re.search(r"(?i)\b(?:trigger|condition|required expression)\b", title):
            trigger_present = True
        if re.search(r"(?i)\b(?:action|then)\b", title):
            action_present = True
        for paragraph in (section.get("paragraphs") or [])[:_MAX_PARAGRAPHS]:
            if not isinstance(paragraph, str):
                continue
            paragraph_count += 1
            # Model/HTML and URL examples sometimes contain sensitive values.
            if _URL.search(paragraph) or _SECRET.search(paragraph):
                continue
            if re.search(r"(?i)\b(?:trigger|when|if|mode change)\b", paragraph):
                trigger_present = True
            if re.search(r"(?i)\b(?:then|on\s*:|off\s*:|toggle\s*:)\b", paragraph):
                action_present = True
            for item in _ACTION.findall(paragraph)[:4]:
                safe = _safe(item, 80).casefold().strip(" .,:")
                if safe and not _SECRET.search(safe):
                    action_labels.add(safe)
    return {
        "id": ident,
        "configVerified": True,
        "triggerTextPresent": trigger_present,
        "actionTextPresent": action_present,
        "actionLabelCandidates": sorted(action_labels)[:8],
        "typedActionDeviceIds": _explicit_action_ids(page),
        "scannedParagraphs": min(paragraph_count, 24 * _MAX_PARAGRAPHS),
    }


def analyse_dependency_probes(probes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare direct ID edges separately from name-only action evidence."""
    successes = [x for x in probes if x.get("configVerified") is True]
    id_matches, text_matches = [], []
    for pos, first in enumerate(successes):
        for second in successes[pos + 1:]:
            if not first.get("actionTextPresent") or not second.get("actionTextPresent"):
                continue
            ids = sorted(
                set(first.get("typedActionDeviceIds") or [])
                & set(second.get("typedActionDeviceIds") or []),
                key=int,
            )
            labels = sorted(
                set(first.get("actionLabelCandidates") or [])
                & set(second.get("actionLabelCandidates") or [])
            )
            if ids:
                id_matches.append({
                    "appIds": [first["id"], second["id"]],
                    "targetDeviceIds": ids[:8],
                    "proof": "matching typed action-device IDs in current configurations",
                    "executionVerified": False,
                })
            elif labels:
                text_matches.append({
                    "appIds": [first["id"], second["id"]],
                    "sharedActionText": labels[:3],
                    "proof": "identical action wording; device identity unverified",
                    "executionVerified": False,
                })
    return {
        "inspected": len(probes),
        "configurationReadsVerified": len(successes),
        "typedActionDeviceOverlaps": id_matches[:5],
        "textOnlyActionCandidates": text_matches[:5],
        "callbackOwnersVerified": False,
        "historicalExecutionVerified": False,
        "evidenceScope": "current read-only app configurations, not rule execution history",
    }


async def inspect_automation_dependencies(
    mcp: Any,
    installed: dict[str, Any] | None,
    scheduled: dict[str, Any] | None,
    *,
    checked_at: str | None = None,
    max_elapsed: float = 6.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bounded optional reads of exact installed app IDs, never mutations."""
    selected = select_automation_probes(installed, scheduled)
    evidence: list[dict[str, Any]] = []
    outcome: dict[str, Any] = {
        "selected": selected,
        "attempts": [],
        "sourceStatus": "not-requested" if not selected else "unavailable",
        "summary": analyse_dependency_probes([]),
    }
    if not selected:
        return outcome, evidence
    try:
        manifest = {t.name: t for t in await asyncio.wait_for(mcp.list_tools(), timeout=1.0)}
        gateway = manifest.get("hub_read_apps_code")
        if gateway is None:
            outcome["sourceStatus"] = "gateway-unavailable"
            return outcome, evidence
    except (Exception, asyncio.CancelledError) as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        outcome["sourceStatus"] = "discovery-unavailable"
        return outcome, evidence

    # One global budget and max two concurrent reads, without retries. App
    # settings/source-code and write gateways are explicitly disallowed.
    start = time.monotonic()
    semaphore = asyncio.Semaphore(2)

    async def inspect(item: dict[str, str]) -> dict[str, Any]:
        async with semaphore:
            remaining = max_elapsed - (time.monotonic() - start)
            if remaining <= 0:
                return {**item, "configVerified": False, "reasonUnavailable": "time budget"}
            arguments = {
                "tool": "hub_get_app_config",
                "args": {"appId": item["id"], "includeSettings": False},
            }
            began = time.monotonic()
            status = False
            description = "unavailable"
            summary = None
            try:
                response = await asyncio.wait_for(
                    mcp.call_tool(gateway.name, arguments),
                    timeout=min(2.5, remaining),
                )
                status = tool_succeeded(response)
                summary = summarise_config(response.data, item["id"]) if status else None
                status = summary is not None
                description = "verified app ID and rendered page" if status else "unusable or mismatched source"
            except (Exception, asyncio.CancelledError) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                description = type(exc).__name__
            evidence.append({
                "tool": gateway.name,
                "sub_tool": "hub_get_app_config",
                "arguments": arguments,
                "timestamp": checked_at,
                "success": bool(status),
                "supports_live_claim": bool(status),
                "evidence_kind": "chat_audit_app_dependency_configuration",
                "mutates": False, "effect": "read",
                "elapsed_ms": round(1000 * (time.monotonic() - began)),
                "summary": f"App {item['id']}: {description}; read-only configuration, no raw settings",
            })
            return {
                **item,
                "configVerified": bool(status),
                **(summary or {}),
                **({"reasonUnavailable": description} if not status else {}),
            }

    attempts = await asyncio.gather(*(inspect(item) for item in selected))
    outcome["attempts"] = attempts
    outcome["sourceStatus"] = "partially-verified" if any(
        a.get("configVerified") for a in attempts
    ) else "unavailable"
    outcome["summary"] = analyse_dependency_probes(attempts)
    return outcome, evidence


def render_dependency_findings(report: dict[str, Any] | None) -> str:
    lines = ["### Automation configuration and dependency investigation"]
    if not isinstance(report, dict):
        return "\n".join(lines + ["- Not checked; app configuration evidence absent."])
    targets = report.get("selected") or []
    if not targets:
        return "\n".join(lines + [
            "- No eligible installed-app/scheduler candidates were established.",
            "- Overlapping triggers and disabled-job execution remain unverified.",
        ])
    summary = report.get("summary") or {}
    checked = summary.get("configurationReadsVerified", 0)
    lines.append(
        f"- Targeted {len(targets)} known installed app ID(s); "
        f"{checked} configuration pages verified. "
        "No raw settings or source code retrieved."
    )
    for item in (report.get("attempts") or targets)[:_MAX_APPS]:
        status = "verified current config" if item.get("configVerified") else "config unavailable"
        desc = _safe(item.get("reason") or "", 58)
        lines.append(
            f"- {_safe(item.get('name'))} (app {item.get('id')}): "
            f"{status}; selected for {desc}."
        )
        if item.get("configVerified"):
            lines.append(
                f"  - Trigger/condition text {'present' if item.get('triggerTextPresent') else 'not established'}; "
                f"action text {'present' if item.get('actionTextPresent') else 'not established'}; "
                f"{len(item.get('typedActionDeviceIds') or [])} typed action-device ID(s)."
            )
    for overlap in summary.get("typedActionDeviceOverlaps") or []:
        lines.append(
            f"- **Configuration-level shared target:** apps "
            f"{'/'.join(overlap['appIds'])} have matching typed action-device IDs "
            f"{', '.join(overlap['targetDeviceIds'])}. Not proof that either fired."
        )
    for overlap in summary.get("textOnlyActionCandidates") or []:
        lines.append(
            f"- **Text-only possible overlap:** apps "
            f"{'/'.join(overlap['appIds'])} share action wording "
            f"{', '.join(_safe(v, 60) for v in overlap['sharedActionText'])}. "
            "Actual target-device identity and competing execution are unverified."
        )
    lines.append(
        "- **Still unverified:** scheduler callback ownership, whether any disabled "
        "app executes jobs, and overlapping runtime triggers/conditions. Even matching "
        "current action-device IDs alone does not justify disabling or deleting rules."
    )
    return "\n".join(lines)


__all__ = [
    "select_automation_probes", "summarise_config",
    "analyse_dependency_probes", "inspect_automation_dependencies",
    "render_dependency_findings",
]
