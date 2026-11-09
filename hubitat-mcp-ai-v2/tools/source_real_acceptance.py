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


def _validate_labels(labels: Any) -> dict[str, str]:
    if not isinstance(labels, dict) or set(labels) != set(LABEL_FIELDS):
        _fail("Provide exactly the six documented private device/app labels")
    for value in labels.values():
        if (not isinstance(value, str) or not value.strip() or
                len(value) > 120 or any(ord(ch) < 32 for ch in value) or
                "{" in value or "}" in value or "\u2028" in value or
                "\u2029" in value):
            _fail("Each device/app label must be a short single-line name")
    return {key: labels[key].strip() for key in LABEL_FIELDS}


def init(config: Path, directory: Path) -> dict:
    labels = _validate_labels(_read_json(config).get("labels"))
    if directory.exists() and any(directory.iterdir()):
        _fail("The private acceptance directory must start empty")
    if directory.exists() and not directory.is_dir():
        _fail("Acceptance destination is not a directory")
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for ident, domain, template in CASES:
        question = template.format_map(labels)
        cases.append({
            "id": ident, "domain": domain, "question": question,
            "question_sha256": _hash(question.encode("utf-8")),
        })
    document = {"schema": SCHEMA, "cases": cases,
                "source_provenance": "requires later human verification",
                "benchmark_type": "unseen-source-real-baseline-first-answers"}
    digest = _hash(_canonical(document))
    (directory / MANIFEST).write_bytes(_canonical(document))
    (directory / SEAL).write_text(digest + "\n", encoding="ascii")
    (directory / EXPORT_DIRECTORY).mkdir()
    return {"manifest_sha256": digest, "cases_frozen": len(cases),
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
    if (doc.get("schema") != SCHEMA or not isinstance(cases, list) or
            len(cases) != len(CASES)):
        _fail("Unrecognised or incomplete frozen manifest")
    expected = [x[0] for x in CASES]
    if [case.get("id") for case in cases if isinstance(case, dict)] != expected:
        _fail("Frozen case identifiers or ordering changed")
    for case in cases:
        if (not isinstance(case, dict) or set(case) !=
                {"id", "domain", "question", "question_sha256"} or
                not isinstance(case["question"], str) or
                case["domain"] != next(row[1] for row in CASES
                                       if row[0] == case["id"]) or
                _hash(case["question"].encode("utf-8")) != case["question_sha256"] or
                not case["question"].endswith("Do not change anything.")):
            _fail("Invalid frozen source-real question record")
    return doc, saved


def verify(directory: Path, *, reviews: Path | None = None) -> dict:
    manifest, sealed_digest = _load_manifest(directory)
    records: list[dict] = []
    ids: list[str] = []
    missing: list[str] = []
    carryover: list[str] = []
    attempted_commands: list[str] = []
    failed_responses: list[str] = []
    model_hashes: set[str] = set()
    versions: set[str] = set()
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
        records.append(record)
        ids.append(ident)

    if reviews is not None and missing:
        _fail("Complete all frozen cases before applying positional reviews")
    if reviews is not None and (carryover or attempted_commands):
        _fail("Do not rate a study with reported prior context or a device-command attempt")
    if reviews is not None and (len(model_hashes) != 1 or len(versions) != 1):
        _fail("Do not combine different models or add-on versions in a scored study")
    human_review = _read_json(reviews) if reviews else None
    try:
        outcome = summarize(records, human_reviews=human_review)
    except AuditInputError:
        _fail("Private human review is invalid or does not match captured cases")

    return {
        "schema": REPORT_SCHEMA,
        "manifest_sha256": sealed_digest,
        "cases_expected": len(manifest["cases"]),
        "cases_captured": len(ids),
        "captured_case_ids_in_review_order": ids,
        "missing_case_ids": missing,
        "prior_conversation_evidence_reported_case_ids": carryover,
        "attempted_device_command_case_ids": attempted_commands,
        "failed_first_answer_case_ids": failed_responses,
        "model_id_fingerprint_consistent": len(model_hashes) == 1 if records else None,
        "addon_version_consistent": len(versions) == 1 if records else None,
        "real_source_verified_from_export": False,
        "first_attempt_independently_verified": False,
        "read_only_permission_independently_verified": False,
        "new_cloud_calls": 0,
        "new_mcp_calls": 0,
        "review_eligibility": ("needs_operator_source_and_first_attempt_attestation"
                               if not carryover and not attempted_commands else
                               "requires_safety_or_context_review"),
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
    read = commands.add_parser("verify", help="Check first-answer exports offline")
    read.add_argument("--directory", required=True, type=Path)
    read.add_argument("--reviews", type=Path)
    read.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.config, args.directory)
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
