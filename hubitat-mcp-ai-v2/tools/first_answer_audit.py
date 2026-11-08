#!/usr/bin/env python3
"""Private-by-default, evidence-neutral scorecard for native MCP AI v2 exports.

Reads the Technical JSON *already exported by the user's v2 browser*. No Hubitat,
Home Assistant, model, network, database or credentials are accessed. Prints no
question, answer, device IDs, tool arguments, raw event rows or source payload.
Successful MCP calls are NOT equivalent to a correct or safe model answer.
Only successful source receipts contribute to history counts. Native MCP
content/text event lists count as source rows even without client annotations.
Native bounded log receipts also count returned log rows but cannot establish
absence of older errors or events from a limited latest-page response.
Standard device command acknowledgments and subsequent attribute reads are
reported separately; neither implies physical effects or model answer correctness.
Untrusted labels,
including model names, tool names and argument keys, are never echoed verbatim.

Usage:
    python hubitat-mcp-ai-v2/tools/first_answer_audit.py private-export.json
    python hubitat-mcp-ai-v2/tools/first_answer_audit.py first.json second.json --output audit.json

Keep input/export and locally generated audit files out of the public repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "homebrain-v2-first-answer-audit.v5"


class AuditInputError(ValueError):
    """The input is not a compatible first-answer Technical JSON export."""


def _nonnegative(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value) and value >= 0 else None


def _optional_int(value: Any) -> int | None:
    number = _nonnegative(value)
    return int(number) if number is not None and int(number) == number else None


def _read_scope(response_text: Any) -> dict | None:
    """Read *existing* client event metadata; never infer an upstream history cap."""
    if not isinstance(response_text, str):
        return None
    try:
        payload = json.loads(response_text)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    info = payload.get("client_event_source_scope")
    if not isinstance(info, dict):
        return None
    returned = _optional_int(info.get("events_returned"))
    if returned is None:
        return None
    return {
        "events_returned": returned,
        "scope_origin": "client_annotation",
        "returned_timestamps_both_present": (
            isinstance(info.get("oldest_returned_event"), str)
            and isinstance(info.get("newest_returned_event"), str)
        ),
        "requested_lookback_hours": _optional_int(info.get("requested_lookback_hours")),
        "requested_limit": _optional_int(info.get("requested_limit")),
        "limit_reached": info.get("limit_reached") is True,
        "upstream_reported_truncated": info.get("upstream_truncated") is True,
        "historical_coverage_complete": "not_established",
    }


def _arg_names(value: Any) -> list[str]:
    """Field names only; never export values or raw tool argument payloads."""
    if not isinstance(value, dict):
        return []
    return sorted(str(k)[:65] for k in value if isinstance(k, str))[:30]


def _effective_args(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    leaf = value.get("args")
    return leaf if isinstance(leaf, dict) and isinstance(value.get("tool"), str) else value


def _native_event_scope(response_text: Any, call: dict[str, Any]) -> dict | None:
    """Count returned rows in a native device-event MCP response, not a search hit.

    Live flat tools can return an MCP content/text envelope without the
    optional client_event_source_scope annotation. Recognise the native event
    leaf contract, including its gateway equivalent; never treat any arbitrary
    JSON object's events field as historical evidence. Retention is unknown.
    """
    request = call.get("arguments")
    leaf = request.get("tool") if isinstance(request, dict) else None
    if call.get("name") != "hub_list_device_events" and leaf != "hub_list_device_events":
        return None
    if not isinstance(response_text, str):
        return None
    try:
        envelope = json.loads(response_text)
    except (TypeError, ValueError):
        return None
    if (not isinstance(envelope, dict) or envelope.get("isError") is True
            or not isinstance(envelope.get("content"), list)):
        return None
    args = _effective_args(request)
    requested_limit = _optional_int(args.get("limit"))
    for block in envelope["content"]:
        if (not isinstance(block, dict) or block.get("type") != "text"
                or not isinstance(block.get("text"), str)):
            continue
        try:
            body = json.loads(block["text"])
        except (TypeError, ValueError):
            continue
        if (not isinstance(body, dict) or not isinstance(body.get("events"), list)
                or ("device" not in body and "deviceId" not in body)):
            continue
        if body.get("success") is False or body.get("isError") is True:
            continue
        events = body["events"]
        if not all(isinstance(e, dict) for e in events):
            continue
        # Actual returned list length is reliable even when a count field has
        # a different meaning. At the request limit, pagination MAY be needed;
        # neither limit hit nor an empty result proves native retention depth.
        return {
            "events_returned": len(events),
            "scope_origin": "native_event_rows",
            "returned_timestamps_both_present": bool(events) and all(
                isinstance(event.get("date"), str) for event in events
            ),
            "requested_lookback_hours": _optional_int(args.get("hoursBack")),
            "requested_limit": requested_limit,
            "limit_reached": bool(requested_limit) and len(events) >= requested_limit,
            "upstream_reported_truncated": body.get("upstream_truncated") is True,
            "historical_coverage_complete": "not_established",
        }
    return None


def _native_log_scope(response_text: Any, call: dict[str, Any]) -> dict | None:
    """Recognise returned native log rows, not complete retained log coverage.

    A broad log query can match many more rows than its returned latest-page
    sample. Its success does not establish absence of older errors. No log
    messages, timestamps, names, selectors or matched counts are exported.
    """
    request = call.get("arguments")
    leaf = request.get("tool") if isinstance(request, dict) else None
    if call.get("name") != "hub_get_logs" and leaf != "hub_get_logs":
        return None
    if not isinstance(response_text, str):
        return None
    try:
        envelope = json.loads(response_text)
    except (TypeError, ValueError):
        return None
    if (not isinstance(envelope, dict) or envelope.get("isError") is True
            or not isinstance(envelope.get("content"), list)):
        return None
    args = _effective_args(request)
    requested_limit = _optional_int(args.get("limit"))
    for block in envelope["content"]:
        if (not isinstance(block, dict) or block.get("type") != "text"
                or not isinstance(block.get("text"), str)):
            continue
        try:
            body = json.loads(block["text"])
        except (TypeError, ValueError):
            continue
        if (not isinstance(body, dict) or not isinstance(body.get("mode"), str)
                or not isinstance(body.get("entries"), list)
                or body.get("isError") is True or body.get("success") is False):
            continue
        entries = body["entries"]
        if not all(isinstance(entry, dict) for entry in entries):
            continue
        matched = _optional_int(body.get("matched"))
        return {
            "rows_returned": len(entries),
            "reported_matched_exceeds_returned": (
                matched is not None and matched > len(entries)
            ),
            "requested_limit_reached": (
                requested_limit is not None and requested_limit > 0
                and len(entries) >= requested_limit
            ),
            "has_requested_since": isinstance(args.get("since"), str)
            and bool(args["since"].strip()),
            "log_window_completeness": "not_established",
        }
    return None


def _native_content_body(response_text: Any) -> dict | None:
    """Read a native MCP content/text leaf without exporting raw source values."""
    if not isinstance(response_text, str):
        return None
    try:
        envelope = json.loads(response_text)
    except (TypeError, ValueError):
        return None
    if (not isinstance(envelope, dict) or envelope.get("isError") is True
            or not isinstance(envelope.get("content"), list)):
        return None
    for block in envelope["content"]:
        if (not isinstance(block, dict) or block.get("type") != "text"
                or not isinstance(block.get("text"), str)):
            continue
        try:
            body = json.loads(block["text"])
        except (TypeError, ValueError):
            continue
        if (isinstance(body, dict) and body.get("isError") is not True
                and body.get("success") is not False):
            return body
    return None


def _native_call_matches(call: dict, leaf: str) -> bool:
    arguments = call.get("arguments")
    return (call.get("name") == leaf or
            (isinstance(arguments, dict) and arguments.get("tool") == leaf))


def _executed_successful_call(call: dict) -> bool:
    return (call.get("success") is True
            and call.get("operation_executed") is not False
            and call.get("result_kind") not in {
                "tool_catalog", "prior_evidence_read", "contract_error",
            })


def _device_key(value: Any) -> str | None:
    if (isinstance(value, (str, int)) and not isinstance(value, bool)
            and str(value).strip()):
        return str(value).strip()
    return None


def _action_expected_attribute(arguments: dict) -> tuple[str, str | float] | None:
    """Limited standard commands only; never infer device-specific effects."""
    command = arguments.get("command")
    if command in ("on", "off"):
        return "switch", command
    if command != "setLevel":
        return None
    values = arguments.get("parameters")
    if not isinstance(values, list) or not values:
        return None
    try:
        number = float(values[0])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or isinstance(values[0], bool):
        return None
    return "level", number


def _action_receipts(calls: list[dict]) -> dict:
    """Report structural command/observation receipts, NOT action success.

    Source-order post-command reads are contemporaneous observations of
    Hubitat's reported state, not proof of physical completion or exclusive
    causality. A command response's embedded state can be pre-command data,
    so it is deliberately excluded from independent follow-up observations.
    Never export device IDs, action parameters, source labels or values.
    """
    attempted = 0
    acknowledged: list[tuple[int, str, dict, bool]] = []
    for i, call in enumerate(calls):
        if not _native_call_matches(call, "hub_call_device_command"):
            continue
        attempted += 1
        if not _executed_successful_call(call):
            continue
        args = _effective_args(call.get("arguments"))
        device = _device_key(args.get("deviceId"))
        command = args.get("command")
        body = _native_content_body(call.get("response"))
        if (device is None or not isinstance(command, str) or not body
                or body.get("success") is not True
                or body.get("command") != command):
            continue
        acknowledged.append((i, device, args, isinstance(body.get("state"), dict)))

    have_reads = 0
    observed_rows = 0
    multiple_attributes = 0
    expected_match = 0
    expected_mismatch = 0
    no_comparable = 0
    for index, device, args, _ in acknowledged:
        observed: dict[str, Any] = {}
        for later in calls[index + 1:]:
            if _native_call_matches(later, "hub_call_device_command"):
                next_device = _device_key(
                    _effective_args(later.get("arguments")).get("deviceId")
                )
                if next_device == device:
                    break
            if not (_native_call_matches(later, "hub_get_device_attribute")
                    and _executed_successful_call(later)):
                continue
            read_args = _effective_args(later.get("arguments"))
            if _device_key(read_args.get("deviceId")) != device:
                continue
            body = _native_content_body(later.get("response"))
            attribute = read_args.get("attribute")
            if (not body or not isinstance(attribute, str)
                    or body.get("attribute") != attribute
                    or "value" not in body or body["value"] is None):
                continue
            observed[attribute] = body["value"]
            observed_rows += 1
        if observed:
            have_reads += 1
            if len(observed) >= 2:
                multiple_attributes += 1
        expected = _action_expected_attribute(args)
        if expected is None or expected[0] not in observed:
            no_comparable += 1
            continue
        attribute, value = expected
        current = observed[attribute]
        if attribute == "switch":
            matches = isinstance(current, str) and current.lower() == value
        else:
            try:
                reading = float(current)
                matches = math.isfinite(reading) and reading == value
            except (ValueError, TypeError):
                matches = False
        if matches:
            expected_match += 1
        else:
            expected_mismatch += 1
    return {
        "device_commands_attempted": attempted,
        "native_command_acknowledgments": len(acknowledged),
        "commands_with_embedded_state_snapshot": sum(
            has_state for _, _, _, has_state in acknowledged
        ),
        "commands_with_subsequent_independent_attribute_read": have_reads,
        "commands_without_subsequent_independent_attribute_read": (
            len(acknowledged) - have_reads
        ),
        "independent_post_command_attribute_rows": observed_rows,
        "commands_with_two_or_more_attributes_read": multiple_attributes,
        "expected_attribute_matched_at_last_read": expected_match,
        "expected_attribute_not_matched_at_last_read": expected_mismatch,
        "no_comparable_expected_attribute_read": no_comparable,
        "physical_effect_and_causality": "not_established",
        "answer_outcome_claim_quality": "human_review_required",
    }


def audit_export(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise AuditInputError("Expected the browser's Technical JSON object")
    response = document.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("tool_calls"), list):
        raise AuditInputError("Missing response.tool_calls; not a compatible v2 export")
    question = document.get("question")
    if not isinstance(question, str) or not question.strip():
        raise AuditInputError("Question is missing from Technical JSON")
    calls = response["tool_calls"]
    if not all(isinstance(call, dict) for call in calls):
        raise AuditInputError("All response.tool_calls entries must be objects")
    model = document.get("model")
    version = document.get("ui_version")
    if not isinstance(model, str) or not isinstance(version, str):
        raise AuditInputError("Missing version/model; export may not be from v2")

    counts: Counter = Counter()
    names: set[str] = set()
    requested_field_counts: list[int] = []
    targets: set[tuple[str, str]] = set()
    attributes: set[tuple[str, str]] = set()
    event_scopes: list[dict] = []
    log_scopes: list[dict] = []
    for call in calls:
        result_kind = call.get("result_kind")
        if result_kind == "tool_catalog":
            counts["catalog_only"] += 1
        elif result_kind == "prior_evidence_read":
            counts["prior_receipt_reads"] += 1
        elif result_kind == "contract_error":
            counts["local_contract_rejections"] += 1
        elif call.get("success") is False:
            counts["other_failed_attempts"] += 1
        if result_kind != "prior_evidence_read" and result_kind != "tool_catalog":
            counts["native_tool_attempts"] += 1
            if call.get("success") is True:
                counts["successful_native_attempts"] += 1
            elif call.get("success") is False:
                counts["failed_native_attempts"] += 1
            else:
                counts["unknown_success_native_attempts"] += 1
        if result_kind == "contract_error" and call.get("operation_executed") is False:
            counts["known_nonexecuted_contract_errors"] += 1
        elif call.get("operation_executed") is False:
            counts["known_nonexecuted_operations"] += 1
        elif call.get("operation_executed") is True:
            counts["reported_executed_operations"] += 1

        raw_name = call.get("name")
        if isinstance(raw_name, str) and len(raw_name) <= 120:
            names.add(raw_name)
        args = _effective_args(call.get("arguments"))
        requested_field_counts.append(len(_arg_names(args)))
        # Keep distinct requested selectors in memory, but never include their
        # private values in the result. A distinct requested target is NOT
        # proof that it returned history or that the target was present.
        for key, value in args.items():
            if not isinstance(key, str) or not isinstance(value, (str, int)) \
                    or isinstance(value, bool):
                continue
            normalized = key.lower()
            if normalized in {"deviceid", "appid", "ruleid", "id"}:
                targets.add((normalized, str(value)))
            if normalized in {"attribute", "attributename", "field"}:
                attributes.add((normalized, str(value)))
        # An executed, successful read is necessary but not sufficient for
        # source-window completeness or a factual/causal claim.
        valid_read = (call.get("success") is True
                      and call.get("operation_executed") is not False
                      and result_kind not in {
                          "tool_catalog", "prior_evidence_read", "contract_error"
                      })
        scope = _read_scope(call.get("response")) or _native_event_scope(
            call.get("response"), call
        )
        if scope is not None:
            if valid_read:
                event_scopes.append(scope)
            else:
                counts["excluded_non_success_event_scopes"] += 1
        log_scope = _native_log_scope(call.get("response"), call)
        if log_scope is not None:
            if valid_read:
                log_scopes.append(log_scope)
            else:
                counts["excluded_non_success_log_scopes"] += 1
    attempts = counts["native_tool_attempts"]
    failures = counts["failed_native_attempts"]
    return {
        "schema": SCHEMA,
        "review_status": "not_measured",
        "quality_result": None,
        "quality_note": (
            "Tool success, receipt count, event timestamps, and first-turn status "
            "do not grade factual accuracy, complete device coverage, "
            "causal calibration or write permissions. Those require source review."
        ),
        "build": {
            # Only controlled version syntax is emitted verbatim. Identifiers
            # controlled by external models/tools stay in the private source.
            "version": version if re.fullmatch(
                r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9._-]+)?", version
            ) else "unrecognised",
            "model_sha256_prefix": hashlib.sha256(
                model.encode("utf-8")
            ).hexdigest()[:16],
        },
        "question_sha256_prefix": hashlib.sha256(question.encode("utf-8")).hexdigest()[:16],
        "source": {
            "type": "locally_imported_browser_technical_export",
            "first_answer_isolated": (
                "prior_session_context_present"
                if (_optional_int(response.get("prior_sources_indexed")) or 0) > 0
                or (_optional_int(response.get("prior_receipts_used")) or 0) > 0
                else "no_prior_context_reported_not_proof_of_new_session"
            ),
            "raw_question_answer_arguments_and_tool_payloads_exported": False,
        },
        "performance": {
            "browser_elapsed_ms": _nonnegative(document.get("client_elapsed_ms")),
            "server_elapsed_ms": _nonnegative(document.get("server_elapsed_ms")),
            "model_rounds": _optional_int(response.get("rounds")),
            "schema_only_gateway_discoveries": _optional_int(
                response.get("leaf_schema_discoveries")
            ),
        },
        "native_tools": {
            "attempted": attempts, "successful": counts["successful_native_attempts"],
            "failed": failures, "unknown_status": counts["unknown_success_native_attempts"],
            "locally_rejected": counts["local_contract_rejections"],
            "known_nonexecuted_contract_errors": counts["known_nonexecuted_contract_errors"],
            "other_failed_attempts": counts["other_failed_attempts"],
            "distinct_model_selected_tool_names": len(names),
            "requested_argument_field_counts_per_call": requested_field_counts,
            "distinct_requested_id_selectors": len(targets),
            "distinct_requested_attribute_filters": len(attributes),
        },
        "history_receipts": {
            "event_scope_receipts": len(event_scopes),
            "scope_origin_native_event_rows": sum(
                s["scope_origin"] == "native_event_rows" for s in event_scopes
            ),
            "scope_origin_client_annotation": sum(
                s["scope_origin"] == "client_annotation" for s in event_scopes
            ),
            "excluded_non_success_event_scopes": counts["excluded_non_success_event_scopes"],
            "event_rows_returned_total": sum(s["events_returned"] for s in event_scopes),
            "unique_events_across_receipts": "not_established",
            "any_request_limit_reached": any(s["limit_reached"] for s in event_scopes),
            "any_upstream_truncation_flag": any(
                s["upstream_reported_truncated"] for s in event_scopes
            ),
            "all_history_windows_complete": "not_established",
            "source_receipts_with_any_event_timestamp": sum(
                bool(s["returned_timestamps_both_present"]) for s in event_scopes
            ),
        },
        "log_receipts": {
            "source_receipts": len(log_scopes),
            "rows_returned_total": sum(s["rows_returned"] for s in log_scopes),
            "unique_log_rows_across_receipts": "not_established",
            "receipts_where_reported_matches_exceed_returned": sum(
                s["reported_matched_exceeds_returned"] for s in log_scopes
            ),
            "any_log_request_limit_reached": any(
                s["requested_limit_reached"] for s in log_scopes
            ),
            "receipts_with_requested_since": sum(
                s["has_requested_since"] for s in log_scopes
            ),
            "excluded_non_success_log_scopes": counts[
                "excluded_non_success_log_scopes"
            ],
            "all_log_windows_complete": "not_established",
            "absence_of_older_errors_from_sample": "not_established",
        },
        "action_receipts": _action_receipts(calls),
        "human_review": {
            "grounding": "not_measured",
            "group_member_and_attribute_coverage": "not_measured",
            "command_vs_observed_state": "not_measured",
            "causal_certainty": "not_measured",
            "useful_first_response": "not_measured",
            "read_only_token_permissions": "not_verified_by_transcript",
        },
    }


def summarize(records: list[dict]) -> dict:
    """Descriptive metrics only; no auto-scoring of answer correctness."""
    n = len(records)
    elapsed = [
        r["performance"]["browser_elapsed_ms"] / 1000
        for r in records if r["performance"]["browser_elapsed_ms"] is not None
    ]
    times = sorted(elapsed)
    counts = [r["native_tools"] for r in records]
    return {
        "schema": "homebrain-v2-first-answer-summary.v5",
        "samples": n,
        "quality_status": "not_measured",
        "grounded_claim_rate": None,
        "useful_first_answer_rate": None,
        "unsupported_definitive_causal_claim_count": None,
        "tool_attempts": sum(x["attempted"] for x in counts),
        "tool_attempt_failures": sum(x["failed"] for x in counts),
        "median_browser_seconds": round(statistics.median(times), 3) if times else None,
        "p95_browser_seconds": times[math.ceil(.95 * len(times)) - 1] if times else None,
        "history_complete": "not_established_by_exports",
        "details": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", nargs="+", type=Path, help="Private browser Technical JSON exports")
    parser.add_argument("--output", type=Path, help="Private JSON report path, default stdout")
    args = parser.parse_args()
    records = []
    try:
        for source in args.exports:
            document = json.loads(source.read_text(encoding="utf-8"))
            records.append(audit_export(document))
    except (AuditInputError, OSError, ValueError) as exc:
        parser.error("Cannot audit an input export: " + type(exc).__name__ + ". "
                     "Keep raw technical logs private and verify the file schema.")
    report = json.dumps(summarize(records), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
