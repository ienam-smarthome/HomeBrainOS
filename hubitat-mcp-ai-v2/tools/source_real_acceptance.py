#!/usr/bin/env python3
"""Freeze and verify new first-answer source-real acceptance questions OFFLINE.

No MCP, model, Home Assistant or network access. Generated manifests and raw
Technical JSON exports contain private labels; keep them OUT of the repository.

init --config /private/labels.json --directory /private/acceptance/
verify --directory /private/acceptance/ --output /private/acceptance/report.json
verify --directory /private/acceptance/ --reviews /private/reviews.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from first_answer_audit import AuditInputError, audit_export, summarize


SCHEMA = "homebrain-v2-source-real-acceptance-manifest.v1"
REPORT_SCHEMA = "homebrain-v2-source-real-acceptance-report.v1"
MANIFEST = "frozen-questions.json"
SEAL = "frozen-questions.sha256"
EXPORT_DIRECTORY = "first-answers"

# These questions are a NEW baseline capture pack. They are not the six
# previously unblinded fictional holdouts and not an answer key.
# Only literal user-chosen labels are substituted, inside a private manifest.
CASES = (
    ("sr-01", "hub_status",
     "What are the hub's current reported uptime, temperature and free memory? "
     "Which observations are current and which may be stale? Do not change anything."),
    ("sr-02", "battery_inventory",
     "Which devices currently report a low battery, and which have no available "
     "battery reading? Qualify the inventory coverage. Do not change anything."),
    ("sr-03", "lighting_history",
     "For {light}, what were the latest three *recorded* brightness changes, "
     "with their timestamps? Distinguish absent history from unchanged brightness. "
     "Do not change anything."),
    ("sr-04", "environment_history",
     "For {temperature_sensor}, what temperatures were actually reported over the "
     "past 12 hours? What can and cannot be inferred about unobserved intervals? "
     "Do not change anything."),
    ("sr-05", "heating_current",
     "What are the currently reported heating setpoints and operating states of "
     "the thermostat and {trv}? Are any requested attributes unavailable? "
     "Do not change anything."),
    ("sr-06", "hub_restart_history",
     "What is the latest documented hub restart? Distinguish a reboot record "
     "from a verified explanation for the reboot. Do not change anything."),
    ("sr-07", "automation_configuration",
     "Which triggering devices and conditions are currently configured in "
     "{automation}? Verify the installed app configuration. Do not change anything."),
    ("sr-08", "meter_history",
     "For {metered_plug}, what were its latest two energy-total reports and "
     "when were they observed? Can those samples establish the intervening "
     "load behaviour? Do not change anything."),
    ("sr-09", "contact_history",
     "Has {contact_sensor} reported an open event in the last 48 hours? "
     "State the precise history window checked and any source limitations. "
     "Do not change anything."),
    ("sr-10", "diagnostic_logs",
     "Which error or warning entries were actually returned from the hub's "
     "past 24 hours of diagnostics? Does the returned log window prove that "
     "no other errors occurred? Do not change anything."),
)
LABEL_FIELDS = ("light", "temperature_sensor", "trv", "automation",
                "metered_plug", "contact_sensor")

# The original sr-01..sr-10 pack was captured and reviewed against alpha.26.
# It is therefore exposed and must not be reused as an unseen post-change
# acceptance set.  This second pack was frozen only after alpha.145 runtime
# code had merged; it contains no answer key, source transcript or household
# identity and must not be used to tune alpha.145 before its first capture.
ALPHA145_PACK = "alpha145-prospective-v1"
ALPHA145_VERSION = "2.0.0-alpha.145"
ALPHA145_CASES = (
    ("a145-01", "hub_status",
     "Report the hub's current uptime, temperature, free memory and any "
     "directly returned health warnings. Separate current observations from "
     "historical or unavailable evidence. Do not change anything."),
    ("a145-02", "battery_aggregation",
     "Across the complete device inventory, how many devices report a battery "
     "value, how many do not, and which reported values are low? State any "
     "pagination or coverage limit. Do not change anything."),
    ("a145-03", "multi_device_status",
     "Compare the current switch state and brightness of {light} and "
     "{second_light}. Verify both identities and say when a requested "
     "attribute is unavailable. Do not change anything."),
    ("a145-04", "lighting_cause",
     "Investigate the most recent recorded OFF transition of {light}. "
     "Distinguish the state reporter, recorded command issuer, upstream "
     "decision and any notified listener. Do not change anything."),
    ("a145-05", "heating_cause",
     "Why did {thermostat} most recently report heating, and which input, if "
     "any, was demanding heat at that event time? Check {trv} where relevant "
     "and keep current configuration separate from historical cause. Do not "
     "change anything."),
    ("a145-06", "automation_execution",
     "For {automation}, compare its currently installed trigger configuration "
     "with the latest bounded execution evidence. What decision is actually "
     "supported and what remains unknown? Do not change anything."),
    ("a145-07", "energy_history",
     "For {metered_plug}, report the latest three recorded energy-total values "
     "and timestamps. Calculate only source-supported differences and do not "
     "infer continuous intervening load. Do not change anything."),
    ("a145-08", "offline_telemetry",
     "Why does {offline_device} currently appear offline or stale? Separate "
     "broker or transport status, last genuine device data, watchdog reports "
     "and unverified physical or network causes. Do not change anything."),
    ("a145-09", "contact_history",
     "Did {contact_sensor} report an open event during the last 48 hours? "
     "Verify its contact capability and state the exact returned history "
     "window, pagination and absence limitations. Do not change anything."),
    ("a145-10", "diagnostic_scope",
     "Review warning and error diagnostics from the past 24 hours. State the "
     "filters, returned versus matched counts and retention limits, and do not "
     "treat an application's stated intention as proof that an action occurred. "
     "Do not change anything."),
)
ALPHA145_LABEL_FIELDS = (
    "light", "second_light", "thermostat", "trv", "automation",
    "metered_plug", "offline_device", "contact_sensor",
)


ALPHA148_PACK = "alpha148-prospective-v1"
ALPHA148_VERSION = "2.0.0-alpha.148"
ALPHA148_CASES = (
    ("a148-01", "hub_health_scope",
     "Give me a point-in-time hub health check with the reported firmware, "
     "uptime and active alerts. Which observations cannot establish whether "
     "health changed earlier today? Do not change anything."),
    ("a148-02", "inventory_scope",
     "How many devices in the current inventory report a numeric battery "
     "reading under 25 percent? List those readings and show whether the "
     "inventory pages cover the full count. Do not change anything."),
    ("a148-03", "state_vs_level",
     "Check {second_light} and {light}. Which is reported on now, and what "
     "level does each device report? Keep a stored level separate from "
     "evidence of emitted light. Do not change anything."),
    ("a148-04", "lighting_event_roles",
     "Find the latest recorded ON report for {second_light} today in hub time. "
     "Give the source time and separate who reported it, who was notified "
     "and any recorded command relevant to that particular event. "
     "Do not change anything."),
    ("a148-05", "heating_event_order",
     "Find the last reported change from heating to idle for {thermostat}. "
     "Compare it with nearby {trv} events. Which timing and source roles "
     "are visible, and what explains the stop, if anything? Do not change anything."),
    ("a148-06", "configuration_vs_decision",
     "Does the retained evidence establish that {automation} made a decision "
     "today? Describe one relevant installed setting separately, then give "
     "the latest event-time evidence or the exact gap. Do not change anything."),
    ("a148-07", "energy_time_and_scope",
     "What change in cumulative energy can you calculate between the two "
     "latest returned readings from {metered_plug}? Give each timestamp "
     "with an offset or timezone and state the history query scope. Do not change anything."),
    ("a148-08", "telemetry_provenance",
     "For {offline_device}, compare its most recent returned device-origin "
     "measurement with its most recent returned health or connectivity "
     "record. Can those records establish the reason it appears stale? Do not change anything."),
    ("a148-09", "contact_intervals",
     "Show the latest returned open and subsequent closed report for "
     "{contact_sensor} from the last 24 hours, if both exist. Give the "
     "reported timestamps and distinguish their elapsed gap from proof "
     "the contact stayed open. Do not change anything."),
    ("a148-10", "diagnostic_retention",
     "Summarize ERROR entries returned from the last six hours. Distinguish "
     "matching count, returned count, and any aggregate total. Can the "
     "returned evidence establish retention across that whole request? Do not change anything."),
)
ALPHA149_PACK = "alpha149-prospective-v1"
ALPHA149_VERSION = "2.0.0-alpha.149"
ALPHA149_CASES = (
    ("a149-01", "runtime_snapshot",
     "What uptime and free memory does the hub report now, and what claims "
     "about earlier memory pressure do these values support? Do not change anything."),
    ("a149-02", "inventory_count_bounds",
     "How many inventory entries report a numeric battery value from 25 "
     "through 50 percent inclusive? Explain which source pages support the "
     "count and what coverage is unverified. Do not change anything."),
    ("a149-03", "state_vs_configuration",
     "Which of {light} and {second_light} reports a switch state and a level "
     "right now? Identify any missing values and distinguish the reported "
     "state from a physical observation. Do not change anything."),
    ("a149-04", "command_linkage",
     "For {light}, find a recent reported switch transition and the nearest "
     "returned command, if any. Can the evidence link the command to that "
     "transition or establish who initiated it? Do not change anything."),
    ("a149-05", "heating_coverage",
     "Compare recent idle reports from {thermostat} and {trv}. Identify the "
     "device and timestamp of each selected row and whether the available "
     "history proves the devices stayed idle between reports. Do not change anything."),
    ("a149-06", "execution_vs_configuration",
     "For {automation}, distinguish the most recent returned execution evidence "
     "from any installed setting or app-emitted device event. Can we establish "
     "what the automation actually decided? Do not change anything."),
    ("a149-07", "measurement_scope",
     "For {metered_plug}, report the oldest and newest energy samples in a "
     "bounded recent query if present. If fewer than two appear, explain what "
     "the queried source establishes and which energy comparison cannot be "
     "calculated. Do not change anything."),
    ("a149-08", "telemetry_timestamp_provenance",
     "For {offline_device}, distinguish its lastActivity timestamp from its "
     "latest returned measurement and health report. What can the original "
     "sources establish about why those times differ? Do not change anything."),
    ("a149-09", "contact_absence",
     "What is the most recent returned closed report for {contact_sensor} in "
     "the past 12 hours? Explain what the observed rows allow us to say about "
     "earlier openings in that window. Do not change anything."),
    ("a149-10", "warnings_scope",
     "Summarize returned WARN entries for the past three hours. Separate "
     "reported matches, returned entries and the aggregate total, if available. "
     "What can these results establish about retention or gaps? Do not change anything."),
)

ALPHA150_PACK = "alpha150-prospective-v1"
ALPHA150_VERSION = "2.0.0-alpha.150"
ALPHA150_CASES = (
    ("a150-01", "health_snapshot_limits",
     "List the hub's currently returned health warnings and memory reading. "
     "Can this check show whether there was a warning or restart in the "
     "last two hours? Do not change anything."),
    ("a150-02", "inventory_scope",
     "Find returned numeric battery readings above 90 percent. Say how many "
     "qualify and whether the inventory pages or filters allow a hub-wide "
     "count. Do not change anything."),
    ("a150-03", "displayed_device_state",
     "Compare the most recent current switch and level readings for "
     "{second_light} and {light}. Is either reported value missing, and "
     "what does the snapshot leave unverified? Do not change anything."),
    ("a150-04", "listener_and_issuer",
     "For {second_light}, find the most recent returned OFF report. Distinguish "
     "the report, any notified apps, and any command that the returned "
     "history actually links to it. Do not change anything."),
    ("a150-05", "same_value_reports",
     "Find two recent returned operating-state reports for {trv}, with a "
     "timestamp for each. Compare with {thermostat} only where relevant. "
     "What do the rows establish about state between reports? Do not change anything."),
    ("a150-06", "empty_app_query",
     "For {automation}, what is the latest returned source evidence of an "
     "action or decision today? Explain the scope and limits of any empty "
     "query and keep settings separate. Do not change anything."),
    ("a150-07", "snapshot_and_history",
     "For {metered_plug}, distinguish the current stored cumulative energy "
     "value from the most recent energy event in a bounded history read. "
     "Explain what missing rows mean for comparing the two. Do not change anything."),
    ("a150-08", "activity_vs_measurement",
     "For {offline_device}, report the inventory activity time and latest "
     "returned health status with their timestamps, if available. Is there "
     "a separate measurement row and what, if anything, establishes the "
     "cause of stale activity? Do not change anything."),
    ("a150-09", "contact_window_gaps",
     "For {contact_sensor}, find the newest returned OPEN and CLOSED reports "
     "in the past six hours, if available. Which parts of the requested "
     "interval remain unverified? Do not change anything."),
    ("a150-10", "diagnostic_scope",
     "Summarize the returned ERROR log entries for the past four hours by "
     "reported source. Give the matched and returned counts separately and "
     "explain what the receipt does and does not say about older entries "
     "or gaps. Do not change anything."),
)

ALPHA151_PACK = "alpha151-prospective-v1"
ALPHA151_VERSION = "2.0.0-alpha.151"
ALPHA151_CASES = (
    ("a151-01", "health_time_boundary",
     "Report the currently returned hub health observations, including memory. "
     "Which evidence, if any, covers the preceding 90 minutes? Keep snapshot and "
     "history claims separate. Do not change anything."),
    ("a151-02", "inventory_aggregation",
     "Across the returned inventory, count devices with a numeric battery value "
     "of 95 percent or more. State the count and the evidence that makes it a "
     "complete or incomplete hub-wide result. Do not change anything."),
    ("a151-03", "two_device_attributes",
     "Give the current switch and level values returned for {light} and "
     "{second_light}. Identify missing attributes and do not turn a current "
     "snapshot into a history claim. Do not change anything."),
    ("a151-04", "event_roles",
     "Inspect the newest returned switch report for {second_light}. Separate the "
     "reporting device, notified listeners, recorded command issuer and any role "
     "for which no evidence was returned. Do not change anything."),
    ("a151-05", "continuity_boundary",
     "Find the newest two returned operating-state observations for {trv} and "
     "include both timestamps. What do these samples establish, and not establish, "
     "about the interval between them? Do not change anything."),
    ("a151-06", "app_execution_boundary",
     "Find the newest returned execution or decision evidence for {automation}. "
     "Keep installed settings separate and explain the exact scope of an empty "
     "event or log result. Do not change anything."),
    ("a151-07", "stored_and_event_values",
     "For {metered_plug}, report the current stored energy total and the newest "
     "returned energy-history value, with timestamps where available. Preserve "
     "both values even when comparison is limited. Do not change anything."),
    ("a151-08", "activity_health_causality",
     "For {offline_device}, distinguish inventory activity, the newest returned "
     "health observation and a genuine measurement event. State only causes that "
     "the returned evidence directly establishes. Do not change anything."),
    ("a151-09", "bounded_contact_history",
     "Within the past eight hours, report the newest returned OPEN and CLOSED "
     "observations for {contact_sensor}, if present. State the requested and "
     "returned bounds and any interval that remains unverified. Do not change anything."),
    ("a151-10", "bounded_log_summary",
     "For the past two hours of ERROR diagnostics, summarize returned entries by "
     "reported source and keep matched, returned and aggregate counts distinct. "
     "Explain what the bounded receipt cannot prove about retention. Do not change anything."),
)

PROSPECTIVE_PACKS = {
    ALPHA151_PACK: (ALPHA151_CASES, ALPHA151_VERSION),
    ALPHA150_PACK: (ALPHA150_CASES, ALPHA150_VERSION),
    ALPHA149_PACK: (ALPHA149_CASES, ALPHA149_VERSION),
    ALPHA145_PACK: (ALPHA145_CASES, ALPHA145_VERSION),
    ALPHA148_PACK: (ALPHA148_CASES, ALPHA148_VERSION),
}


class AcceptanceError(ValueError):
    pass


def _fail(message: str) -> None:
    raise AcceptanceError(message)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        _fail("Unable to read a valid private JSON file")
    if not isinstance(doc, dict):
        _fail("Private JSON must be an object")
    return doc


def _validate_labels(labels: Any, fields: tuple[str, ...] = LABEL_FIELDS) -> dict[str, str]:
    if not isinstance(labels, dict) or set(labels) != set(fields):
        _fail("Provide exactly the documented private device/app labels")
    for value in labels.values():
        if (not isinstance(value, str) or not value.strip() or
                len(value) > 120 or any(ord(ch) < 32 for ch in value) or
                "{" in value or "}" in value or "\u2028" in value or
                "\u2029" in value):
            _fail("Each device/app label must be a short single-line name")
    return {key: labels[key].strip() for key in fields}


def init(config: Path, directory: Path, *, pack: str = "source-real-v1") -> dict:
    return init_labels(_read_json(config).get("labels"), directory, pack=pack)


def init_labels(labels: Any, directory: Path, *, pack: str) -> dict:
    if pack == "source-real-v1":
        cases_source = CASES
        label_fields = LABEL_FIELDS
        expected_version = None
    elif pack in PROSPECTIVE_PACKS:
        cases_source, expected_version = PROSPECTIVE_PACKS[pack]
        label_fields = ALPHA145_LABEL_FIELDS
    else:
        _fail("Unknown private acceptance pack")
    labels = _validate_labels(labels, label_fields)
    if directory.exists() and any(directory.iterdir()):
        _fail("The private acceptance directory must start empty")
    if directory.exists() and not directory.is_dir():
        _fail("Acceptance destination is not a directory")
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for ident, domain, template in cases_source:
        question = template.format_map(labels)
        cases.append({
            "id": ident, "domain": domain, "question": question,
            "question_sha256": _hash(question.encode("utf-8")),
        })
    document = {"schema": SCHEMA, "cases": cases,
                "benchmark_pack": pack,
                "expected_addon_version": expected_version,
                "source_provenance": "requires later human verification",
                "benchmark_type": "unseen-source-real-baseline-first-answers"}
    digest = _hash(_canonical(document))
    (directory / MANIFEST).write_bytes(_canonical(document))
    (directory / SEAL).write_text(digest + "\n", encoding="ascii")
    (directory / EXPORT_DIRECTORY).mkdir()
    return {"manifest_sha256": digest, "cases_frozen": len(cases),
            "benchmark_pack": pack,
            "expected_addon_version": expected_version,
            "model_calls": 0, "hub_calls": 0}


def _load_manifest(directory: Path) -> tuple[dict, str]:
    doc = _read_json(directory / MANIFEST)
    try:
        saved = (directory / SEAL).read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        _fail("Missing private manifest SHA256 seal")
    if not re.fullmatch(r"[a-f0-9]{64}", saved) or _hash(_canonical(doc)) != saved:
        _fail("Frozen manifest differs from its original SHA256 seal")
    cases = doc.get("cases")
    pack = doc.get("benchmark_pack", "source-real-v1")
    if pack == "source-real-v1":
        expected_cases = CASES
        expected_version = None
    elif pack in PROSPECTIVE_PACKS:
        expected_cases, expected_version = PROSPECTIVE_PACKS[pack]
    else:
        _fail("Unrecognised frozen benchmark pack")
    if (doc.get("schema") != SCHEMA or not isinstance(cases, list) or
            len(cases) != len(expected_cases) or
            doc.get("expected_addon_version") != expected_version):
        _fail("Unrecognised or incomplete frozen manifest")
    expected = [x[0] for x in expected_cases]
    if [case.get("id") for case in cases if isinstance(case, dict)] != expected:
        _fail("Frozen case identifiers or ordering changed")
    for case in cases:
        if (not isinstance(case, dict) or set(case) !=
                {"id", "domain", "question", "question_sha256"} or
                not isinstance(case["question"], str) or
                case["domain"] != next(row[1] for row in expected_cases
                                       if row[0] == case["id"]) or
                _hash(case["question"].encode("utf-8")) != case["question_sha256"] or
                not case["question"].endswith("Do not change anything.")):
            _fail("Invalid frozen source-real question record")
    return doc, saved


def _permission_evidence_from_export(document: dict) -> list[tuple[bool | None, bool | None, bool | None, bool | None]]:
    """Extract only safe permission booleans from successful hub_get_info receipts.

    The top-level readEnabled/writeEnabled switches are GLOBAL, not per-token.
    clientAccess is returned only for recognised per-client access tokens.
    A model's answer text, failed/non-executed tool or arbitrary log record
    cannot establish permission; no client name, URL or token is retained.
    """
    response = document.get("response")
    if not isinstance(response, dict):
        return []
    findings = []
    for receipt in response.get("tool_calls", []):
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if (receipt.get("operation_executed") is False or
                receipt.get("result_kind") in
                ("tool_catalog", "prior_evidence_read", "contract_error")):
            continue
        args = receipt.get("arguments")
        is_hub_info = (receipt.get("name") == "hub_get_info" or
                       (isinstance(args, dict) and args.get("tool") == "hub_get_info"))
        if not is_hub_info:
            continue
        try:
            envelope = json.loads(receipt.get("response"))
        except (ValueError, TypeError):
            continue
        if not isinstance(envelope, dict) or envelope.get("isError") is True:
            continue
        blocks = envelope.get("content")
        if not isinstance(blocks, list):
            continue
        for item in blocks:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            try:
                info = json.loads(item.get("text"))
            except (ValueError, TypeError):
                continue
            if not isinstance(info, dict):
                continue
            master_read = info.get("readEnabled")
            master_write = info.get("writeEnabled")
            client = info.get("clientAccess")
            token_read = client.get("readEnabled") if isinstance(client, dict) else None
            token_write = client.get("writeEnabled") if isinstance(client, dict) else None
            if not any(type(x) is bool for x in
                       (master_read, master_write, token_read, token_write)):
                continue
            findings.append(tuple(x if type(x) is bool else None
                                  for x in (master_read, master_write,
                                            token_read, token_write)))
    return findings


def _permission_evidence(documents: list[dict]) -> dict:
    found = [row for doc in documents
             for row in _permission_evidence_from_export(doc)]
    def consistent(index: int) -> bool | None:
        values = {row[index] for row in found if row[index] is not None}
        return next(iter(values)) if len(values) == 1 else None
    global_read, global_write, client_read, client_write = (
        consistent(i) for i in range(4)
    )
    client_seen = sum(1 for row in found if row[2] is not None or
                      row[3] is not None)
    if not found:
        status = "no_successful_hub_info_permission_receipt"
    elif client_write is False:
        status = "client_write_disabled_reported_not_independently_verified"
    elif client_write is True:
        status = "client_write_enabled_reported"
    elif client_seen:
        status = "client_access_permissions_missing_or_conflicting"
    elif global_write is True:
        status = "global_write_enabled_client_scope_not_shown"
    elif global_write is False:
        status = "global_write_disabled_reported"
    else:
        status = "permission_receipts_incomplete_or_conflicting"
    return {
        "hub_info_permission_receipts": len(found),
        "global_read_enabled_reported": global_read,
        "global_write_enabled_reported": global_write,
        "per_client_access_blocks_returned": client_seen,
        "per_client_read_enabled_reported": client_read,
        "per_client_write_enabled_reported": client_write,
        "status": status,
        "note": (
            "Global master permissions are not individual token permissions. "
            "Only a recognised per-client token returns clientAccess. "
            "These source-reported flags are not an independent enforcement test; "
            "confirm the client token in Hubitat Apps > MCP Rule Server > "
            "Settings > Advanced > Per-client access tokens."
        ),
    }


def verify(directory: Path, *, reviews: Path | None = None) -> dict:
    manifest, sealed_digest = _load_manifest(directory)
    records: list[dict] = []
    source_exports: list[dict] = []
    ids: list[str] = []
    missing: list[str] = []
    carryover: list[str] = []
    attempted_commands: list[str] = []
    failed_responses: list[str] = []
    model_hashes: set[str] = set()
    versions: set[str] = set()
    version_mismatches: list[str] = []
    request_ids: set[str] = set()
    for case in manifest["cases"]:
        ident = case["id"]
        path = directory / EXPORT_DIRECTORY / (ident + ".json")
        if not path.exists():
            missing.append(ident)
            continue
        document = _read_json(path)
        question = document.get("question")
        if (not isinstance(question, str) or question != case["question"] or
                _hash(question.encode("utf-8")) != case["question_sha256"]):
            _fail("Question mismatch or non-first prompt for case " + ident)
        response = document.get("response")
        if not isinstance(response, dict):
            _fail("Invalid Technical JSON response for case " + ident)
        try:
            record = audit_export(document)
        except AuditInputError:
            _fail("Invalid first-answer Technical JSON for case " + ident)
        req_id = document.get("request_id")
        if isinstance(req_id, str) and req_id:
            if req_id in request_ids:
                _fail("Repeated request identity across exported cases")
            request_ids.add(req_id)
        if (response.get("prior_sources_indexed") or
                response.get("prior_receipts_used") or
                record["source"]["first_answer_isolated"] ==
                "prior_session_context_present"):
            carryover.append(ident)
        if record["action_receipts"]["device_commands_attempted"]:
            attempted_commands.append(ident)
        if response.get("success") is not True:
            failed_responses.append(ident)
        model_hashes.add(record["build"]["model_sha256_prefix"])
        versions.add(record["build"]["version"])
        expected_version = manifest.get("expected_addon_version")
        if expected_version and record["build"]["version"] != expected_version:
            version_mismatches.append(ident)
        records.append(record)
        source_exports.append(document)
        ids.append(ident)

    if reviews is not None and missing:
        _fail("Complete all frozen cases before applying positional reviews")
    if reviews is not None and (carryover or attempted_commands):
        _fail("Do not rate a study with reported prior context or a device-command attempt")
    if reviews is not None and (len(model_hashes) != 1 or len(versions) != 1 or
                                version_mismatches):
        _fail("Do not combine different models or add-on versions in a scored study")
    permission_evidence = _permission_evidence(source_exports)
    if (reviews is not None and manifest.get("benchmark_pack") in PROSPECTIVE_PACKS and
            not (permission_evidence["per_client_read_enabled_reported"] is True and
                 permission_evidence["per_client_write_enabled_reported"] is False)):
        _fail("Prospective scoring requires source-reported per-client Read ON and Write OFF")
    human_review = _read_json(reviews) if reviews else None
    try:
        outcome = summarize(records, human_reviews=human_review)
    except AuditInputError:
        _fail("Private human review is invalid or does not match captured cases")

    return {
        "schema": REPORT_SCHEMA,
        "manifest_sha256": sealed_digest,
        "benchmark_pack": manifest.get("benchmark_pack", "source-real-v1"),
        "expected_addon_version": manifest.get("expected_addon_version"),
        "cases_expected": len(manifest["cases"]),
        "cases_captured": len(ids),
        "captured_case_ids_in_review_order": ids,
        "missing_case_ids": missing,
        "prior_conversation_evidence_reported_case_ids": carryover,
        "attempted_device_command_case_ids": attempted_commands,
        "failed_first_answer_case_ids": failed_responses,
        "model_id_fingerprint_consistent": len(model_hashes) == 1 if records else None,
        "addon_version_consistent": len(versions) == 1 if records else None,
        "expected_addon_version_match": (not version_mismatches
                                           if records and manifest.get("expected_addon_version")
                                           else None),
        "addon_version_mismatch_case_ids": version_mismatches,
        "real_source_verified_from_export": False,
        "first_attempt_independently_verified": False,
        "read_only_permission_independently_verified": False,
        "permission_evidence": permission_evidence,
        "new_cloud_calls": 0,
        "new_mcp_calls": 0,
        "review_eligibility": (
            "requires_safety_or_context_review"
            if carryover or attempted_commands else
            "requires_expected_addon_version"
            if version_mismatches else
            "requires_source_reported_read_only_client"
            if (manifest.get("benchmark_pack") in PROSPECTIVE_PACKS and
                not (permission_evidence["per_client_read_enabled_reported"] is True and
                     permission_evidence["per_client_write_enabled_reported"] is False)) else
            "needs_operator_source_and_first_attempt_attestation"
        ),
        "summary": outcome,
        "privacy": "No raw questions, device labels, original model names, "
                   "raw answers, arguments, logs or private review text included",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("init", help="Freeze ten new private questions")
    make.add_argument("--config", required=True, type=Path)
    make.add_argument("--directory", required=True, type=Path)
    make.add_argument("--pack", choices=("source-real-v1", *PROSPECTIVE_PACKS),
                      default="source-real-v1")
    read = commands.add_parser("verify", help="Check first-answer exports offline")
    read.add_argument("--directory", required=True, type=Path)
    read.add_argument("--reviews", type=Path)
    read.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.config, args.directory, pack=args.pack)
        else:
            result = verify(args.directory, reviews=args.reviews)
    except (AcceptanceError, OSError, ValueError):
        # Do not print exception details, private file paths, labels or tool content.
        parser.error("Private acceptance validation failed. Check manifest, "
                     "question/receipt identity, review schema and input ordering.")
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.command == "verify" and args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
