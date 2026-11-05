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


def _extra_requested_checks(question: str) -> tuple[bool, bool, bool, bool, bool]:
    """Independent preflight obligations; prohibitions never grant write intent."""
    q = str(question or "")
    positive = " ".join(
        part for part in re.split(r"[\n.!?]+", q)
        if not re.match(r"^\s*(?:do not|don't|never|without|no)\b", part, re.I)
    )
    version_comparison = bool(re.search(
        r"\bhub_get_info\b|(?:serverInfo|initialize)[^\n.]{0,100}"
        r"(?:agree|match|compare|cross.check)", positive, re.I,
    ))
    dated_contract = bool(re.search(
        r"atDate#|Certain Time\s*\(and optional date\)|"
        r"\bdated[ -]?trigger\b|\bdate[\s-]*(?:field|format)\b",
        positive, re.I,
    ))
    readback = dated_contract and bool(re.search(
        r"\bread[\s-]*back\b|\bpersisted\b|\b(saved|stored)\s+date\b",
        positive, re.I,
    ))
    parent = bool(re.search(
        r"\b(?:verify|confirm|inspect|check|establish|identify|validate)\b"
        r"[^\n.]{0,160}\b(?:native\s+)?(?:Rule Machine\s+)?parent\b|"
        r"\bparent\s+(?:app\s+)?(?:identity|verification)\b",
        positive, re.I,
    ))
    authoring_contract = bool(re.search(
        r"\b(?:create|creating|creation|authoring|supported creation operations)\b",
        positive, re.I,
    ) and re.search(
        r"\b(?:dated[ -]?trigger|one[ -]?time|certain time|date format)\b",
        positive, re.I,
    ))
    return version_comparison, dated_contract, readback, parent, authoring_contract


def _requested_parent_id(question: str) -> str | None:
    """Only an unambiguous explicit app ID; never guess the user's parent."""
    found = set(re.findall(
        r"\b(?:app(?:lication)?|parent\s+app)\s*(?:id\s*)?[:#]?\s*"
        r"([1-9][0-9]{0,8})\b", question or "", re.I,
    ))
    return next(iter(found)) if len(found) == 1 else None


def _guide_contract_projection(content: Any) -> dict[str, Any]:
    """Safe structural guide diagnostics, never publish guide text or tokens."""
    empty = {
        "atDateNamed": False, "atDateTypeDateDeclared": False,
        "dateFormatDeclared": False, "documentedDateFormat": None,
        "nativeDateFieldGuideAttested": False,
        "namedTriggerFields": [], "typedTriggerFields": {},
        "certainTimeTriggerNamed": False,
        "createOperationDocumented": False, "parentIdParameterDocumented": False,
        "createContractDocumented": False, "gapCodes": [],
    }
    if not isinstance(content, str) or not 0 < len(content) <= 50000:
        return {**empty, "gapCodes": ["guide_unavailable_or_oversized"]}
    has_field = bool(re.search(r"atDate#", content, re.I))
    expected_types = {
        "time#": "enum", "atTime#": "time",
        "date#": "bool", "atDate#": "date",
    }
    typed_fields: dict[str, str] = {}
    for field, expected in expected_types.items():
        types_seen = []
        for match in re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(field), content, re.I):
            # Only a field's own declaration counts, not an unrelated
            # type=date example elsewhere in the source guide.
            row = content[match.end():].split("\n", 1)[0][:160]
            found = re.search(
                r"""(?i)\b(?:type|inputType|fieldType)\s*["']?\s*[:=]\s*["']?([a-zA-Z]+)\b""",
                row,
            )
            if found:
                types_seen.append(found.group(1).casefold())
        if types_seen and all(t == expected for t in types_seen):
            typed_fields[field] = expected
    typed = typed_fields.get("atDate#") == "date"
    fmt = bool(re.search(r"yyyy-MM-dd", content, re.I))
    explicit_refusal = bool(re.search(
        r"(?i)atDate#[^\n]{0,100}supported\s*[:=]\s*false", content,
    ))
    named = [name for name in ("time#", "atTime#", "date#", "atDate#")
             if re.search(re.escape(name), content, re.I)]
    certain = bool(re.search(
        r"Certain Time\s*\(and optional date\)", content, re.I,
    ))
    create = bool(
        re.search(r"\bhub_set_rule\b", content, re.I)
        and re.search(
            r"""(?i)\boperation\s*["']?\s*[:=]\s*["']?create\b""",
            content,
        )
    )
    parent = bool(re.search(r"\b(?:parent_id|parentId)\b", content))
    date_attested = has_field and typed and fmt and not explicit_refusal
    create_attested = bool(
        date_attested and certain and create and parent
        and len(typed_fields) == 4
    )
    gaps = []
    for missing, code in (
        (not has_field, "atdate_field_not_named"),
        (not typed, "atdate_input_type_not_declared"),
        (not fmt, "date_format_not_declared"),
        (explicit_refusal, "atdate_explicitly_unsupported"),
        (not certain, "certain_time_trigger_not_named"),
        (not create, "native_create_operation_not_documented"),
        (not parent, "parent_id_parameter_not_documented"),
        (len(named) != 4, "trigger_field_names_incomplete"),
        (len(typed_fields) != 4, "typed_trigger_field_contract_incomplete"),
    ):
        if missing:
            gaps.append(code)
    return {
        **empty,
        "atDateNamed": has_field,
        "atDateTypeDateDeclared": bool(typed),
        "dateFormatDeclared": fmt,
        "documentedDateFormat": "yyyy-MM-dd" if fmt else None,
        "nativeDateFieldGuideAttested": bool(date_attested),
        "namedTriggerFields": named,
        "typedTriggerFields": typed_fields,
        "certainTimeTriggerNamed": certain,
        "createOperationDocumented": create,
        "parentIdParameterDocumented": parent,
        "createContractDocumented": create_attested,
        "gapCodes": gaps,
    }


def _native_parent_projection(
    requested_id: str, instances: Any, types: Any,
    summary: Any, config: Any,
) -> dict[str, Any]:
    """Attest exact built-in type join plus independently observed parent role.

    Reuses the same Hubitat app/type evidence contract as native inventory,
    without publishing unrelated application names or child-app details.
    """
    result: dict[str, Any] = {
        "appId": requested_id, "verified": False, "appTypeId": None,
        "childRowsObserved": 0, "failureCode": "source_unavailable",
    }
    if not (isinstance(instances, dict) and isinstance(types, dict)
            and isinstance(instances.get("apps"), list)
            and isinstance(types.get("apps"), list)):
        return result
    def ident(value: Any) -> str | None:
        if type(value) not in (int, str):
            return None
        s = str(value)
        return s if re.fullmatch(r"[1-9][0-9]{0,8}", s) else None

    rows = [row for row in instances["apps"]
            if isinstance(row, dict) and ident(row.get("id")) == requested_id]
    if len(rows) != 1:
        result["failureCode"] = "app_id_missing_or_ambiguous"
        return result
    row = rows[0]
    typ = ident(row.get("appTypeId"))
    if (not typ or row.get("name") != "Rule Machine"
            or row.get("type") != "Rule Machine"
            or row.get("user") is not False
            or "parentId" not in row or row["parentId"] is not None):
        result["failureCode"] = "installed_app_identity_unverified"
        return result
    result["appTypeId"] = typ
    matched = [item for item in types["apps"]
               if isinstance(item, dict) and ident(item.get("id")) == typ]
    if len(matched) != 1:
        result["failureCode"] = "native_type_id_missing_or_ambiguous"
        return result
    item = matched[0]
    if (item.get("name") != "Rule Machine"
            or item.get("namespace") not in (None, "", "hubitat")
            or item.get("system") is not True
            or item.get("isBuiltIn") is not True):
        result["failureCode"] = "native_type_conflict_or_unverified"
        return result
    if not (isinstance(summary, dict) and summary.get("success") is True):
        result["failureCode"] = "app_summary_unavailable"
        return result
    meta = summary.get("app") if isinstance(summary.get("app"), dict) else summary
    if (ident(meta.get("id")) != requested_id
            or meta.get("type") != "Rule Machine"
            or meta.get("namespace") != "hubitat"
            or meta.get("user") is not False
            or (ident(meta["appTypeId"]) != typ
                if meta.get("appTypeId") is not None else False)):
        result["failureCode"] = "app_summary_identity_conflict"
        return result
    if not (isinstance(config, dict) and config.get("success") is True
            and isinstance(config.get("app"), dict)):
        result["failureCode"] = "parent_config_unavailable"
        return result
    root = config["app"]
    children = config.get("childApps")
    if (ident(root.get("id")) != requested_id
            or "parentAppId" not in root or root["parentAppId"] is not None
            or not isinstance(children, list) or not children
            or any(not isinstance(child, dict) for child in children)):
        result["failureCode"] = "parent_role_unverified"
        return result
    result.update(verified=True, childRowsObserved=min(len(children), 5000),
                  failureCode=None)
    return result



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
    want_version, want_date, want_readback, want_parent, want_create = _extra_requested_checks(question)
    for item in reversed(evidence):
        if (not isinstance(item, dict)
                or item.get("evidence_kind") != "typed_native_rule_readiness"
                or item.get("tool") != "homebrain_native_rule_readiness"
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
        parent_ok = (d.get("nativeParentIdentity") or {}).get("verified") is True
        create_ok = (d.get("nativeCreateContractGuideAttested") is True)
        readback_ok = d.get("nativeDatedDateReadbackVerified") is True
        complete = (
            preflight_complete
            and (not want_version or version_ok)
            and (not want_date or guide_date_ok)
            and (not want_readback or readback_ok)
            and (not want_parent or parent_ok)
            and (not want_create or create_ok)
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
        if want_parent:
            checks.append((
                "native_parent_identity", parent_ok,
                "exact-ID hub_list_apps instances/types + hub_get_app_config summary/full",
            ))
        if want_create:
            checks.append((
                "native_dated_create_contract_guide", create_ok,
                "installed native set_rule_reference explicit create/date/parent declarations",
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
            "nativeParentIdentity": d.get("nativeParentIdentity"),
            "nativeGuideContract": d.get("nativeGuideContract"),
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
    """Three core source reads; optional version/identity evidence when requested.

    No writes, model rounds, editor forms, or raw guide content are published.
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
    want_version, want_date, want_readback, want_parent, want_create = _extra_requested_checks(question)
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
    contract = _guide_contract_projection(None)
    for section in _GUIDES:
        result = await get(
            "hub_get_tool_guide", {"section": section},
            "tool guide " + section,
        )
        content = result.get("content") if isinstance(result, dict) else None
        # Only an actual section-specific guide proves availability.
        # Never publish the rotating acknowledgement key or guide content.
        marker = re.compile(
            r"I-HAVE-READ-THE-GUIDE-" + re.escape(section) + r"-[0-9a-fA-F]+"
        )
        guide_availability[section] = (
            isinstance(content, str) and len(content) > 0
            and bool(marker.search(content))
        )
        if section == "set_rule_reference" and (want_date or want_create):
            contract = _guide_contract_projection(
                content if guide_availability[section] else None
            )

    parent_id = _requested_parent_id(question) if want_parent else None
    parent_identity: dict[str, Any] = {
        "appId": parent_id, "verified": False, "appTypeId": None,
        "childRowsObserved": 0,
        "failureCode": ("explicit_parent_id_required" if parent_id is None
                        else "source_unavailable"),
    }
    if parent_id is not None:
        # Each request is an existing, non-mutating Hubitat source read.
        # Do not fall back to guessed parent IDs or rendered editor pages.
        inst = await get(
            "hub_read_apps_code",
            {"tool": "hub_list_apps", "args": {"scope": "instances"}},
            "native Rule Machine installed app identity",
        )
        types = await get(
            "hub_read_apps_code",
            {"tool": "hub_list_apps", "args": {"scope": "types"}},
            "native Rule Machine built-in type identity",
        )
        summary = await get(
            "hub_read_apps_code",
            {"tool": "hub_get_app_config", "args": {
                "appId": parent_id, "summary": True,
            }},
            "exact-ID app summary identity",
        )
        config = await get(
            "hub_read_apps_code",
            {"tool": "hub_get_app_config", "args": {
                "appId": parent_id, "includeSettings": False,
            }},
            "exact-ID app parent-role metadata",
        )
        parent_identity = _native_parent_projection(
            parent_id, inst, types, summary, config,
        )

    complete = (version is not None and timestamp is not None
                and all(guide_availability.values()))
    details = {
        "source": "MCP serverInfo + hub-local backups + native tool-guide sections",
        "mcpServerVersion": version,
        "mcpVersionSource": "MCP initialize serverInfo" if version else "unverified",
        "hubInfoMcpServerVersion": hub_info_version,
        "mcpVersionAgreement": version_agrees,
        "nativeDatedFieldGuideAttested": contract["nativeDateFieldGuideAttested"],
        "nativeCreateContractGuideAttested": contract["createContractDocumented"],
        "nativeGuideContract": contract,
        "nativeParentIdentity": parent_identity if want_parent else None,
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
    if want_date or want_create:
        lines.append(
            "Installed native date field declaration: "
            + ("source-attested" if contract["nativeDateFieldGuideAttested"]
               else "unverified")
        )
        lines.append(
            "Date guide checks: atDate# named="
            + str(contract["atDateNamed"]).lower()
            + "; atDate# type=date declared="
            + str(contract["atDateTypeDateDeclared"]).lower()
            + "; yyyy-MM-dd documented="
            + str(contract["dateFormatDeclared"]).lower() + "."
        )
        if contract["gapCodes"]:
            lines.append(
                "Guide evidence gaps (safe codes): "
                + ", ".join(contract["gapCodes"]) + "."
            )
    if want_create:
        lines.append(
            "Installed native dated-trigger creation guide contract: "
            + ("documented (guide only; runtime untested)"
               if contract["createContractDocumented"] else "unverified")
        )
    if want_parent:
        lines.append(
            "Requested native Rule Machine parent: app "
            + (parent_id or "ID not unambiguously supplied")
            + ("; exact built-in type and parent role verified"
               if parent_identity["verified"] else
               "; unverified ("
               + str(parent_identity["failureCode"]) + ")")
        )
        if parent_identity["verified"]:
            lines.append(
                "Source-attested appTypeId="
                + str(parent_identity["appTypeId"])
                + "; returned child rows="
                + str(parent_identity["childRowsObserved"])
                + " (not a complete rule inventory)."
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
