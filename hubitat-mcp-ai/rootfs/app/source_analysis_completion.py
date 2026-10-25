"""Bounded completion for read-only, source-led device investigations.

Whole-file receipts certify contiguous retrieval only. They cannot certify
method behaviour or root cause. Stop duplicate read expansion once scoped
implementation, device configuration, event history and logs were queried.
"""
from __future__ import annotations

import re
from typing import Any

from investigation_objective import resolve_primary_objective

from adaptive_investigation_policy import source_evidence_request
from source_evidence_metadata import contiguous_source_coverage


_GENERIC_SOURCE_FAILURE = re.compile(
    r"(?:could not produce a valid structured action|"
    r"cannot produce a valid structured action|"
    r"couldn't produce a valid structured action|"
    r"no (?:valid|structured) action (?:was )?(?:provided|produced)|"
    r"found hubitat tools relevant.*no command was sent)",
    re.I | re.S,
)


def source_analysis_failed(message: str) -> bool:
    """Recognise an action-parser failure, never a proof of source analysis."""
    text = str(message or "").strip()
    if not text:
        return True
    # Only allowlisted generic failures: do not discard legitimate responses
    # which discuss why a separate historical action was never executed.
    return bool(_GENERIC_SOURCE_FAILURE.search(text) and len(text) < 1200)


_METHOD_GAP = re.compile(
    r"(?is)(?:methods?|implementations?|code\s+paths?).{0,900}?"
    r"(?:not\s+(?:present|visible|shown)|outside\s+the\s+(?:visible\s+)?"
    r"(?:excerpt|source\s+span)|cannot\s+be\s+traced|"
    r"could\s+not\s+be\s+(?:traced|reviewed))"
)


def source_answer_focus(
    request: str, answer: str,
) -> dict[str, Any]:
    """Minimal objective fidelity check; NOT code-method proof.

    Full source retrieval alone cannot certify an unrelated answer. When a
    user explicitly names a Groovy method, require the final explanation to
    actually address that name. This is deliberately narrower than semantic
    grading and cannot prove the explanation's correctness.
    """
    question = str(request or "")
    response = str(answer or "")
    # Resolve once with the same objective parser used by routing.
    # "inspect the method body" must not create a fictitious method=body.
    objective = resolve_primary_objective(question)
    symbol = objective.method_symbol if objective.is_source else None
    wants_exception = bool(re.search(
        r"(?i)\b(?:LimitExceededException|excessive[- ]load|overload)\b",
        question,
    ))
    if symbol is None and not wants_exception:
        return {
            "required": False, "satisfied": None, "method": None,
            "missing": [],
            "note": "No explicit method identifier or load-error objective found.",
        }
    method_mentioned = (
        re.search(
            r"(?<![A-Za-z_0-9])" + re.escape(symbol) + r"(?![A-Za-z_0-9])",
            response, re.I,
        ) is not None if symbol else True
    )
    exception_context = bool(re.search(
        r"(?i)\b(?:LimitExceededException|excessive[- ]load|overload)\b",
        response,
    ))
    missing = []
    if symbol and not method_mentioned:
        missing.append("named_method_not_addressed")
    if wants_exception and not exception_context:
        missing.append("requested_load_error_not_addressed")
    return {
        "required": bool(symbol or wants_exception),
        "satisfied": not missing, "method": symbol,
        "missing": missing,
        "note": "Keyword alignment is not certification of method-body analysis or causation.",
    }


def source_method_claim_gap(message: str) -> bool:
    """The answer itself admits material method/code paths were not examined."""
    return bool(_METHOD_GAP.search(str(message or "")))


def _leaf(row: dict[str, Any]) -> str:
    arguments = row.get("arguments") or {}
    return str(row.get("sub_tool") or (
        arguments.get("tool") if isinstance(arguments, dict) else ""
    ) or "")


def _args(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("arguments")
    if not isinstance(data, dict):
        return {}
    leaf_args = data.get("args")
    return leaf_args if isinstance(leaf_args, dict) else data


def source_trace_ready_for_synthesis(
    request: str, receipts: list[dict[str, Any]],
) -> bool:
    """Source, configuration, event history, logs for one named device.

    This is a stop for *new exploratory tool calls*, never a claim that
    any Groovy method, broker state or physical device is verified.
    """
    text = str(request or "")
    if not source_evidence_request(text):
        return False
    if not re.search(r"\b(?:driver|device)\b", text, re.I):
        return False
    if not re.search(r"\b(?:events?|logs?|correlat\w*|timeline)\b", text, re.I):
        return False
    if not contiguous_source_coverage(receipts).get("fullImplementationVerified"):
        return False
    device_configs: set[str] = set()
    scoped_events: set[str] = set()
    scoped_logs: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") != "read":
            continue
        operation, arguments = _leaf(row), _args(row)
        device = str(arguments.get("deviceId") or "")
        if not re.fullmatch(r"\d{1,9}", device):
            continue
        if operation == "hub_get_device" and arguments.get("mode") == "configuration":
            device_configs.add(device)
        if operation == "hub_list_device_events":
            scoped_events.add(device)
        if operation == "hub_get_logs":
            scoped_logs.add(device)
    return bool(device_configs & scoped_events & scoped_logs)


_RUNTIME_REQUEST = re.compile(
    r"(?i)\b(?:correlat\w*|runtime\s+observations?|"
    r"current(?:ly)?|today|offline\s+state|"
    r"actual\s+(?:state|failure|cause)|incident|"
    r"historical\s+(?:logs?|events?))\b"
)
_DEVICE_ID_IN_QUESTION = re.compile(
    r"(?i)\bdevice\s*(?:id\s*)?#?\s*(\d{2,9})\b"
)


def _app_source_runtime_evidence_status(
    request: str,
    receipts: list[dict[str, Any]],
    app_id: str,
) -> dict[str, Any]:
    """Check app-relevant scopes, not physical driver telemetry.

    A successful zero-row app/device log read establishes only that the
    bounded query completed. It does not establish historical non-execution.
    """
    question = str(request or "")
    relevant = bool(re.search(
        r"(?i)\b(?:logs?|runtime|correlat\w*|"
        r"LimitExceededException|excessive[- ]load|execution|scheduler)\b",
        question,
    ))
    device_match = _DEVICE_ID_IN_QUESTION.search(question)
    device_id = device_match.group(1) if device_match else None
    config_required = bool(re.search(
        r"(?i)\b(?:configuration|settings|configured)\b", question,
    ))
    log_required = bool(re.search(
        r"(?i)\b(?:logs?|correlat\w*|LimitExceededException)\b", question,
    ))
    targets = ["app_logs"] if log_required else []
    if log_required and device_id:
        targets.append("device_logs")
    if config_required:
        targets.append("app_configuration")
    checked: set[str] = set()
    log_counts: dict[str, int | None] = {}
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("mutates") is True
                or receipt.get("effect") != "read"):
            continue
        op, args = _leaf(receipt), _args(receipt)
        source_app = str(args.get("appId") or "")
        source_device = str(args.get("deviceId") or "")
        if op == "hub_get_app_config" and source_app == app_id:
            checked.add("app_configuration")
        if op == "hub_get_logs":
            scope = None
            if source_app == app_id:
                scope = "app_logs"
            elif device_id and source_device == device_id:
                scope = "device_logs"
            if scope:
                checked.add(scope)
                details = receipt.get("details") or {}
                if isinstance(details, dict):
                    count = details.get("logCount")
                    if type(count) is int:
                        log_counts[scope] = count
    return {
        "required": relevant,
        "satisfied": not relevant or all(name in checked for name in targets),
        "checked": sorted(checked),
        "missing": [name for name in targets if name not in checked],
        "scope": "installed_app_source",
        "historicalEventConfirmed": any(
            count > 0 for count in log_counts.values()
            if type(count) is int
        ),
        "boundedLogCounts": log_counts,
        "note": (
            "Successful bounded app/device log queries verify reads, not "
            "24-hour/72-hour coverage, app method execution, a physical "
            "device state, or historical exception absence."
        ),
    }


def source_runtime_evidence_status(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Explicit source+runtime investigations also require scoped live reads.

    A Groovy source download cannot establish the runtime failure of a
    physical device. Only current-request successful, non-mutating receipts
    count; never assume past conversation data or unscoped logs.
    """
    objective = resolve_primary_objective(request)
    if objective.is_source and objective.installed_app_id:
        return _app_source_runtime_evidence_status(
            request, receipts, objective.installed_app_id
        )
    required = bool(_RUNTIME_REQUEST.search(str(request or "")))
    status: dict[str, Any] = {
        "required": required, "satisfied": not required,
        "checked": [], "missing": [],
    }
    if not required:
        return status
    specified = _DEVICE_ID_IN_QUESTION.search(str(request or ""))
    wanted_id = specified.group(1) if specified else None
    targets: dict[str, set[str]] = {
        "device_state": set(), "device_history": set(), "device_logs": set(),
    }
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("mutates") is True
                or receipt.get("effect") != "read"):
            continue
        op, args = _leaf(receipt), _args(receipt)
        device = str(args.get("deviceId") or "")
        if not device.isdigit() or (wanted_id and device != wanted_id):
            continue
        if op == "hub_get_device":
            if args.get("mode") in ("summary", "status", "attributes"):
                targets["device_state"].add(device)
        elif op == "hub_list_device_events":
            targets["device_history"].add(device)
        elif op == "hub_get_logs":
            targets["device_logs"].add(device)
    status["checked"] = [key for key, ids in targets.items() if ids]
    status["missing"] = [key for key, ids in targets.items() if not ids]
    shared = set.intersection(*targets.values())
    status["satisfied"] = bool(shared)
    return status


def source_failure_summary(receipts: list[dict[str, Any]]) -> str:
    """Truthful final read-out when code interpretation never completed."""
    coverage = contiguous_source_coverage(receipts)
    total = coverage.get("totalLength")
    ids = {
        str((row.get("details") or {}).get("sourceCodeId"))
        for row in receipts
        if isinstance(row, dict) and row.get("success") is True
        and isinstance(row.get("details"), dict)
        and row["details"].get("sourceRetrieved") is True
        and str(row["details"].get("sourceCodeId") or "").isdigit()
    }
    source_note = (
        "The entire Groovy source was retrieved by verified contiguous "
        + str(total) + "-offset-unit coverage"
        if coverage.get("fullImplementationVerified") and isinstance(total, int)
        else "Only partial or unverified Groovy source coverage was obtained"
    )
    code_note = " (source code ID " + next(iter(ids)) + ")" if len(ids) == 1 else ""
    had_events = any(
        isinstance(row, dict) and row.get("success") is True
        and _leaf(row) == "hub_list_device_events" for row in receipts
    )
    had_logs = any(
        isinstance(row, dict) and row.get("success") is True
        and _leaf(row) == "hub_get_logs" for row in receipts
    )
    return (
        "**Source investigation incomplete — analysis was not produced.** "
        + source_note + code_note + ". "
        + ("Device event history was queried. " if had_events else
           "Device event history was not verified as checked. ")
        + ("Hubitat logs were queried. " if had_logs else
           "Hubitat logs were not verified as checked. ")
        + "However, the model did not provide a valid explanation of the "
        "relevant Groovy methods, their callers or the runtime observations. "
        "Full source retrieval is not proof of method execution, MQTT broker "
        "traffic, physical power or root cause. No device command was sent "
        "as part of this read-only investigation."
    )



# A raw installed-app property is stored configuration, not a verified
# runtime branch. These checks use successful read receipts, not prompt words.
_RAW_SETTING = re.compile(
    r"(?i)(?:\x60[A-Za-z_]\w{2,}\x60|[A-Za-z_]\w{2,})\s*"
    r"(?:=|:|\s+is(?:\s+(?:set\s+)?to)?)\s*"
    r"(?:\x60?none\x60?|true|false|enabled|disabled|\x60[^ \n]+\x60)"
)
_BEHAVIOUR_CLAIM = re.compile(
    r"(?i)\b(?:means?|therefore|explains?|because|prevents?|"
    r"disables?|ensures?|never|always|automatically|configured\s+to|"
    r"will\s+not|cannot)\b"
)


def configuration_semantics_evidence_gap(
    receipts: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Installed app configs read without app-matched implementation reads."""
    config_apps: set[str] = set()
    source_apps: set[str] = set()
    code_ids: set[str] = set()
    configured_code_ids: dict[str, str] = {}
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("mutates") is True
                or receipt.get("effect") not in (None, "read")):
            continue
        op, args = _leaf(receipt) or str(receipt.get("tool") or ""), _args(receipt)
        installed_id = str(args.get("appId") or "")
        if op == "hub_get_app_config" and installed_id.isdigit():
            config_apps.add(installed_id)
            details = receipt.get("details") or {}
            if isinstance(details, dict):
                verified_code = details.get("appTypeId") or details.get("sourceCodeId")
                if str(verified_code or "").isdigit():
                    configured_code_ids[installed_id] = str(verified_code)
        elif op == "homebrain_read_groovy_source" and installed_id.isdigit():
            source_apps.add(installed_id)
        elif op == "hub_get_source":
            code_id = str(args.get("id") or args.get("sourceId") or "")
            if code_id.isdigit():
                code_ids.add(code_id)
    return tuple(sorted(
        app_id for app_id in config_apps
        if app_id not in source_apps
        and configured_code_ids.get(app_id) not in code_ids
    ))


def configuration_semantics_followup(
    answer: str,
    receipts: list[dict[str, Any]],
) -> str | None:
    """One bounded, read-only AI evidence invitation, never a tool route."""
    unchecked_apps = configuration_semantics_evidence_gap(receipts)
    if not unchecked_apps:
        return None
    draft = str(answer or "")
    if not (_RAW_SETTING.search(draft) and _BEHAVIOUR_CLAIM.search(draft)):
        return None
    return (
        "HOST CONFIGURATION-SEMANTICS CHECK (READ ONLY): This answer "
        "interprets stored application values as definitive runtime behaviour "
        "without inspecting the app's source. For installed app ID(s) "
        + ", ".join(unchecked_apps[:2])
        + ", determine from the advertised read-only source tool whether "
        "the relevant handler, conditions and defaults actually implement "
        "the proposed meaning. The source workbench accepts the *installed* "
        "app ID, not a guessed source code ID. Prefer a source read capable "
        "of disproving your explanation; do not expand unrelated apps. "
        "If source is unavailable, distinguish observed raw configuration "
        "from UNKNOWN effective semantics and do NOT recommend a setting "
        "change as a verified fix. The model chooses the next allowed read."
    )


_UNCERTAINTY = re.compile(
    r"(?i)(?:not\s+(?:verified|proven|established)|"
    r"cannot\s+(?:infer|determine|prove)|"
    r"does\s+not\s+(?:prove|establish)|"
    r"unknown|unverified|requires?\s+(?:source|code)|"
    r"without\s+(?:source|code))"
)
_SETTING_CHANGE_ADVICE = re.compile(
    r"(?i)(?:\bto\s+(?:fix|enable|resolve|correct|restore)\b|"
    r"\b(?:should|must|need(?:s)?\s+to)\s+(?:change|set|disable|enable)\b|"
    r"\b(?:changing|setting)\s+\w+.*\b(?:fix|resolve|enable)\b)"
)


def guard_unverified_config_behavior(
    answer: str,
    receipts: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Do not present inferred setting semantics or fixes as verified code.

    Preserve unrelated observations, timelines and headings; remove only the
    unsupported interpretive paragraph and setting-change recommendations
    tied to the same inferred setting. Generic source evidence check; no
    special knowledge of one property, controller or user setup.
    """
    if not configuration_semantics_evidence_gap(receipts):
        return str(answer or ""), False
    parts = str(answer or "").split("\n\n")
    setting_names: set[str] = set()
    suspect: set[int] = set()
    for index, paragraph in enumerate(parts):
        if paragraph.lstrip().startswith("|"):
            continue
        normalized = paragraph.replace("**", "").replace('"', "").replace("'", "")
        if _UNCERTAINTY.search(normalized):
            continue
        if not (_RAW_SETTING.search(normalized)
                and _BEHAVIOUR_CLAIM.search(normalized)):
            continue
        name = _RAW_SETTING.search(normalized)
        if name:
            raw_key = re.match(r"(?:\x60?)([A-Za-z_]\w{2,})", name.group())
            if raw_key:
                setting_names.add(raw_key.group(1).casefold())
        suspect.add(index)
    if not suspect:
        return str(answer or ""), False
    for index, paragraph in enumerate(parts):
        if index in suspect:
            parts[index] = (
                "The current app configuration was retrieved, but the "
                "implementation of the cited setting was not verified in "
                "the installed Groovy source. The stored value alone "
                "cannot establish effective automatic behaviour or its "
                "historical cause."
            )
        elif (setting_names
              and _SETTING_CHANGE_ADVICE.search(paragraph)
              and not _UNCERTAINTY.search(paragraph)
              and any(re.search(r"(?i)(?<!\w)" + re.escape(name) + r"(?!\w)",
                                paragraph)
                      for name in setting_names)):
            parts[index] = (
                "A change to that setting is not justified by the returned "
                "configuration evidence alone. Verify the installed "
                "implementation and effective UI settings first."
            )
    return "\n\n".join(parts), True

__all__ = ["source_answer_focus", 
    "source_analysis_failed", "source_trace_ready_for_synthesis",
    "source_failure_summary", "source_method_claim_gap",
    "source_runtime_evidence_status",
    "configuration_semantics_evidence_gap",
    "configuration_semantics_followup",
    "guard_unverified_config_behavior",
]
