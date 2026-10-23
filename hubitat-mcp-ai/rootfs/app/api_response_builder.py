from __future__ import annotations

from copy import deepcopy
from current_state_claim_contract import ground_current_device_status
from investigation_evidence_ledger import reconcile_command_denials
from lockout_claim_consistency import annotate_lockout_disagreement
import re
from typing import Any

from causal_claim_verification import verify_causal_claims
from causal_coverage_claim_guard import guard_causal_controller_history_coverage
from causal_attribution_guard import (
    guard_unproven_upstream_manual_exclusion,
    guard_causal_sensor_source_attribution,
)
from evidence_source_guard import (
    guard_checked_source_absence_claim,
    has_performance_evidence,
)
from evidence_ledger import checked_source_categories
from history_cardinality_guard import guard_history_interval_cardinality
from history_temporal_analysis import guard_history_duration_claim
from location_correlation_guard import guard_location_correlation_claim
from performance_causality_guard import guard_performance_log_causality
from observed_app_exception_guard import guard_observed_app_exception_denials
from observed_long_method_guard import guard_observed_long_method_denials
from technical_metrics_presenter import (
    present_request_metrics,
    present_request_outcome,
)


_NO_HISTORY_DATA = re.compile(
    r"\b(?:no\s+(?:recorded\s+)?data|no\s+history|no\s+(?:recorded\s+)?events?|"
    r"nothing\s+(?:was\s+)?recorded)\b",
    re.I,
)


def _participating_model(metrics: dict[str, Any], model: str) -> str | None:
    details = metrics.get("model_round_details")
    if isinstance(details, list) and details:
        last = details[-1]
        if isinstance(last, dict) and isinstance(last.get("model"), str):
            return last["model"]
    counters = metrics.get("counters")
    if not isinstance(counters, dict):
        return str(model)
    try:
        model_rounds = int(counters.get("model_rounds") or 0)
    except (TypeError, ValueError):
        model_rounds = 0
    return str(model) if model_rounds > 0 else None



def _guard_exclusive_history_date_claim(
    message: str, evidence: list[dict[str, Any]],
) -> str:
    """An all-evidence single-date claim cannot ignore dated command receipts.

    A command from another date is NOT proof of a requested switch transition.
    Correct only the false scope summary, not a narrower claim that the exact
    focal event at a particular time was missing.
    """
    # Prefer a precise, dated cross-source correction before replacing a
    # longer prose fragment. Doing this first avoids "the The checked..." and
    # retains both calendar dates rather than only the raw first command ISO.
    from datetime import date
    dates_seen: set[str] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("events", "commandEvents", "boundaryEvents", "correlationEvents"):
            for item in details.get(key) or []:
                stamp = item.get("date") if isinstance(item, dict) else None
                if isinstance(stamp, str) and re.match(
                    r"^\d{4}-\d{2}-\d{2}[T ]", stamp
                ):
                    dates_seen.add(stamp[:10])
    cross_date = re.compile(
        r"(?i)evidence\s+gathered\s+in\s+this\s+turn\s+"
        r"exclusively\s+covers\s+activity\s+from\s+"
        r"\*\*[^\n.]+\*\*"
    )
    if len(dates_seen) >= 2 and cross_date.search(message):
        observed = ", ".join(
            f"{date.fromisoformat(day).day} "
            f"{date.fromisoformat(day).strftime('%B %Y')}"
            for day in sorted(dates_seen)
        )
        return cross_date.sub(
            "checked source records include activity dated " + observed
            + "; this does not prove the cause of the requested focal event",
            message, count=1,
        )
    # A bounded evidence summary must not erase a separately recorded command.
    # This only corrects coverage claims and never treats the command as proof
    # of the requested focal activation.
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        rows = details.get("events") or details.get("commandEvents")
        if not isinstance(rows, list):
            continue
        for event in rows:
            if not isinstance(event, dict):
                continue
            stamp = event.get("date")
            if not isinstance(stamp, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", stamp):
                continue
            from datetime import date
            day = date.fromisoformat(stamp[:10]).strftime("%d %B %Y").lstrip("0")
            # Correct the observed failure: "history and logs only cover
            # events from 16 October", when a 12 October command was read.
            denial = re.search(
                r"(?i)(?:history|logs|evidence)[^\n.]{0,120}"
                r"(?:only|exclusively)\s+(?:cover|covers|contain|contains|include|includes)"
                r"[^\n.]{0,90}\.",
                message,
            )
            if denial and day.lower() not in denial.group(0).lower():
                name = str(event.get("name") or "device event")
                who = event.get("producedBy") or {}
                producer = str(who.get("label") or "unknown source") if isinstance(who, dict) else "unknown source"
                return (
                    message[:denial.start()]
                    + "The checked history includes multiple dates; source coverage is incomplete."
                    + message[denial.end():]
                    + f"\n\n**Additional verified command/history:** {name} at {stamp}, attributed to {producer}."
                    + " This does not establish the cause of the requested activation."
                )
    import datetime
    dates: set[str] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("events", "commandEvents", "boundaryEvents", "correlationEvents"):
            rows = details.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                value = row.get("date")
                if isinstance(value, str) and re.match(r"^\\d{4}-\\d{2}-\\d{2}[T ]", value):
                    dates.add(value[:10])
    if len(dates) < 2:
        return message
    pattern = re.compile(
        r"(?i)(?:the\\s+)?evidence\\s+gathered\\s+in\\s+this\\s+turn\\s+"
        r"exclusively\\s+covers\\s+activity\\s+from\\s+\\*\\*[^\\n.]+\\*\\*"
    )
    if not pattern.search(message):
        return message
    observed = ", ".join(
        datetime.date.fromisoformat(d).strftime("%-d %B %Y")
        for d in sorted(dates)
    )
    return pattern.sub(
        "The checked device and command records include dates " + observed
        + "; those records do not by themselves verify the requested event's initiator",
        message,
        count=1,
    )


def _mark_history_correction(receipt: dict[str, Any]) -> None:
    details = receipt.get("details")
    if isinstance(details, dict):
        details["finalAnswerCorrectionApplied"] = True


def _history_absence_replacement(receipt: dict[str, Any]) -> str | None:
    """Return a compact deterministic correction for a false no-history claim."""

    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        return None
    if interval_count <= 0:
        return None

    label = str(details.get("label") or "").strip()
    duration = str(temporal.get("totalActiveDuration") or "").strip()
    lower_bound = bool(temporal.get("totalIsLowerBound"))
    noun = "interval" if interval_count == 1 else "intervals"
    qualifier = "at least " if lower_bound and duration else ""
    if duration:
        return (
            f"{label} has recorded history in this evidence: {interval_count} active "
            f"{noun} totaling {qualifier}{duration}."
        )
    return f"{label} has recorded history in this evidence: {interval_count} active {noun}."


def _partial_zero_replacement(receipt: dict[str, Any]) -> str | None:
    """Describe zero observed active time without turning a lower bound into zero."""

    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        return None
    source_integrity_verified = temporal.get("sourceIntegrityVerified")
    if source_integrity_verified is None:
        source_integrity_verified = details.get("historySourceIntegrityVerified")
    unverified_stream = (
        source_integrity_verified is False
        or str(temporal.get("durationReliability") or "").casefold()
        == "unverified-event-stream"
        or str(temporal.get("sourceIntegrity") or "").casefold() == "unverified"
        or str(details.get("historySourceIntegrity") or "").casefold() == "unverified"
    )
    incomplete_boundary = bool(temporal.get("totalIsLowerBound"))
    if interval_count != 0 or not (incomplete_boundary or unverified_stream):
        return None

    label = str(details.get("label") or "The device").strip() or "The device"
    active = str(temporal.get("activeState") or "active").strip() or "active"
    inactive = str(temporal.get("inactiveState") or "inactive").strip() or "inactive"
    window = str(temporal.get("windowLabel") or "the requested window").strip()
    if unverified_stream:
        return (
            f"No bounded {active} interval was established for {label} during {window} "
            f"from the recorded device-event rows. The event stream has not been "
            f"independently verified as complete, so this does not prove it stayed "
            f"{inactive} throughout that window."
        )
    return (
        f"No {active} interval was established for {label} during {window}, but the "
        f"history boundary is incomplete, so this does not prove it stayed "
        f"{inactive} throughout that window."
    )


def _deterministic_unverified_zero_history_response(
    evidence: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    """Return the safe final answer for one zero/unverified history result.

    This is intentionally not wording-sensitive. When the current turn has one
    successful device-history receipt, zero bounded intervals, and an explicitly
    unverified event stream, the model cannot safely conclude that the device was
    inactive, that there was "no record", or that all activity happened later.
    Serialize the deterministic evidence statement directly instead of trying to
    enumerate every English absence phrase.
    """

    local_histories = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
    ]
    categories = checked_source_categories(evidence)
    material_other = categories & {
        "related_device_history",
        "location_history",
        "logs",
        "rules_apps",
        "device_filter",
        "live_context",
    }
    # Whole-answer deterministic fallback is only for a simple single-source
    # history query. Once an investigation gathered another source class, the
    # model-authored analysis must survive and any correction stays localized.
    if len(local_histories) != 1 or material_other:
        return None

    receipt = local_histories[0]
    if (
        not isinstance(receipt.get("details"), dict)
        or not isinstance(receipt["details"].get("temporalAnalysis"), dict)
    ):
        return None
    details = receipt["details"]
    temporal = details["temporalAnalysis"]
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        return None
    if interval_count != 0:
        return None

    source_integrity_verified = temporal.get("sourceIntegrityVerified")
    if source_integrity_verified is None:
        source_integrity_verified = details.get("historySourceIntegrityVerified")
    unverified_stream = (
        source_integrity_verified is False
        or str(temporal.get("durationReliability") or "").casefold()
        == "unverified-event-stream"
        or str(temporal.get("sourceIntegrity") or "").casefold() == "unverified"
        or str(details.get("historySourceIntegrity") or "").casefold() == "unverified"
    )
    if not unverified_stream:
        return None

    replacement = _partial_zero_replacement(receipt)
    if replacement is None:
        return None
    return replacement, receipt


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", text)


def _guard_partial_zero_claims(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Reject model wording that upgrades a partial zero lower bound to proof."""

    text = str(message or "")
    receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and _partial_zero_replacement(receipt) is not None
    ]
    if not receipts:
        return text, False

    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        comparable = re.sub(r"[*_`]", "", sentence).casefold()
        for receipt in receipts:
            details = receipt.get("details") or {}
            temporal = details.get("temporalAnalysis") or {}
            label = str(details.get("label") or "").strip()
            attribute = str(details.get("attribute") or "").strip()
            active = str(temporal.get("activeState") or "active").strip()
            inactive = str(temporal.get("inactiveState") or "inactive").strip()
            label_matches = bool(label and label.casefold() in comparable)
            attribute_data_absence = bool(
                attribute
                and (
                    re.search(
                        rf"\bno\s+(?:recorded\s+)?{re.escape(attribute.casefold())}"
                        r"\s+(?:data|history)\b",
                        comparable,
                        re.I,
                    )
                    or re.search(
                        rf"\bno\s+(?:recorded\s+)?{re.escape(attribute.casefold())}"
                        r"\s+(?:events?|activity|readings?)\b",
                        comparable,
                        re.I,
                    )
                    or re.search(
                        rf"\bno\s+{re.escape(attribute.casefold())}"
                        r"\s+(?:events?|activity|readings?)\s+"
                        r"(?:were\s+)?(?:recorded|found|observed)\b",
                        comparable,
                        re.I,
                    )
                    or re.search(
                        rf"\bno\s+{re.escape(attribute.casefold())}"
                        r"\s+(?:was|were)\s+(?:recorded|found|observed)\b",
                        comparable,
                        re.I,
                    )
                )
            )
            if not label_matches and not attribute_data_absence:
                continue
            unsupported_zero = attribute_data_absence or bool(_NO_HISTORY_DATA.search(sentence))
            unsupported_zero = unsupported_zero or bool(
                re.search(
                    rf"\b(?:was|is|were|are)\s+(?:not|never)\s+{re.escape(active)}\b",
                    comparable,
                    re.I,
                )
            )
            unsupported_zero = unsupported_zero or bool(
                re.search(
                    rf"\b(?:stayed|remained|was|is)\s+{re.escape(inactive)}\b.*\b(?:throughout|all)\b",
                    comparable,
                    re.I,
                )
            )
            if not unsupported_zero:
                continue
            replacement = _partial_zero_replacement(receipt)
            if replacement is None:
                continue
            pieces[index] = replacement
            _mark_history_correction(receipt)
            changed = True
            break
    return "".join(pieces), changed


def _guard_history_absence_claims(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct a named no-data claim contradicted by current-turn history proof.

    This guard is intentionally narrow. It only edits a sentence that both names
    the exact history device and contains an explicit no-data/no-history phrase,
    and only when that same request has deterministic temporal proof of one or
    more active intervals for the device. It does not infer anything from prior
    conversation or from unrelated receipts.
    """

    text = str(message or "")
    receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and isinstance(receipt.get("details"), dict)
    ]
    if not receipts or not _NO_HISTORY_DATA.search(text):
        return text, False

    # Split only on sentence whitespace so formatting/newlines are preserved well
    # enough for the WebUI while keeping the replacement local to the contradiction.
    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _NO_HISTORY_DATA.search(sentence):
            continue
        comparable = re.sub(r"[*_`]", "", sentence).casefold()
        for receipt in receipts:
            details = receipt.get("details") or {}
            label = str(details.get("label") or "").strip()
            if not label or label.casefold() not in comparable:
                continue
            replacement = _history_absence_replacement(receipt)
            if replacement is None:
                continue
            pieces[index] = replacement
            _mark_history_correction(receipt)
            changed = True
            break
    return "".join(pieces), changed


def _guard_history_message(
    message: str,
    evidence: list[dict[str, Any]],
) -> str:
    """Keep the serialized answer consistent with deterministic history proof."""

    deterministic_zero = _deterministic_unverified_zero_history_response(evidence)
    if deterministic_zero is not None:
        replacement, receipt = deterministic_zero
        if str(message or "").strip() != replacement.strip():
            _mark_history_correction(receipt)
        return replacement

    corrected, partial_zero_applied = _guard_partial_zero_claims(message, evidence)
    corrected, absence_applied = _guard_history_absence_claims(corrected, evidence)
    corrected, cardinality_receipts = guard_history_interval_cardinality(
        corrected, evidence
    )
    for receipt in cardinality_receipts:
        _mark_history_correction(receipt)
    corrected, duration_applied = guard_history_duration_claim(corrected, evidence)
    if duration_applied:
        for receipt in evidence:
            if not isinstance(receipt, dict):
                continue
            if receipt.get("tool") != "homebrain_device_history":
                continue
            if isinstance(receipt.get("details"), dict):
                _mark_history_correction(receipt)
                break
    # Keep the local variable explicit so future guards can share this boundary
    # without losing whether any serializer-side correction happened.
    _ = (
        partial_zero_applied
        or absence_applied
        or bool(cardinality_receipts)
        or duration_applied
    )
    return corrected


def build_agent_response(
    outcome: Any,
    *,
    model: str,
    elapsed_ms: int,
    version: str,
) -> dict[str, Any]:
    """Build the stable /api/ask response without exposing private request data."""

    metrics = getattr(outcome, "metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    outcome_presentation = present_request_outcome(metrics.get("outcome"))
    evidence = deepcopy(list(getattr(outcome, "evidence", []) or []))
    message = _guard_history_message(
        str(getattr(outcome, "message", "")),
        evidence,
    )
    message, state_claims_corrected = ground_current_device_status(
        message, evidence, str(getattr(outcome, "request_class", "")),
    )
    message = _guard_exclusive_history_date_claim(message, evidence)
    message, command_contradictions = reconcile_command_denials(message, evidence)
    message, lockout_discrepancy = annotate_lockout_disagreement(message)
    message, _ = guard_location_correlation_claim(message, evidence)
    # Re-apply graph-backed action ownership, log absence and sensor-order
    # invariants at the final serialization boundary. The host-verified
    # requestedBoundary receipt safely resolves the focal event when the
    # original question is not carried into the API builder.
    message, _ = verify_causal_claims(message, evidence)

    # Post-synthesis API serialization enforces the same causal claim
    # integrity contract: model revisions must not restore unsupported
    # exclusions or misattribute recorded sensor events to empty app logs.
    message, _ = guard_causal_controller_history_coverage(
        message, evidence, original_user=""
    )
    message, _ = guard_unproven_upstream_manual_exclusion(message, evidence)
    message, _ = guard_causal_sensor_source_attribution(message, evidence)
    performance_scope = has_performance_evidence(evidence)
    message, _ = guard_checked_source_absence_claim(
        message, evidence, performance_request=performance_scope
    )
    # A successful log read may contain an explicit app overload exception even
    # when the model wrongly says no such rows were returned. Repair only
    # categorical denials/exclusivity with matching structured ERROR receipts.
    message, exception_denials_corrected = guard_observed_app_exception_denials(
        message, evidence
    )
    # Correct unqualified denials of source-scoped long-running WARN methods
    # only when successful structured current-turn log evidence contradicts them.
    message, long_method_denials_corrected = guard_observed_long_method_denials(
        message, evidence
    )
    # This final serializer runs after model synthesis. A causal device answer
    # may have read app logs; that alone does not make it a performance report.
    # Never let performance-only repair instructions leak across that boundary.
    if performance_scope:
        message, _ = guard_performance_log_causality(message, evidence)

    result = {
        "success": True,
        "route": getattr(outcome, "route", "unified-mcp-agent"),
        "intent": "native-function-calling",
        "request_class": str(getattr(outcome, "request_class", "tool-driven")),
        "message": message,
        "choices": list(getattr(outcome, "choices", []) or []),
        "confirmation_required": bool(
            getattr(outcome, "confirmation_required", False)
        ),
        "confirmation_count": int(getattr(outcome, "confirmation_count", 0) or 0),
        "automation_items": list(getattr(outcome, "automation_items", []) or []),
        "evidence": evidence,
        "metrics": deepcopy(metrics),
        "evidence_validation": {
            "contradictions_corrected": command_contradictions,
            "lockout_disagreement": lockout_discrepancy,
        },
        "metric_rows": present_request_metrics(metrics),
        "outcome_presentation": deepcopy(outcome_presentation),
        "model": _participating_model(metrics, model),
        "elapsed_ms": max(0, int(elapsed_ms)),
        "version": str(version),
    }
    if getattr(outcome, "route", "") == "comprehensive-system-audit":
        ai_status = getattr(outcome, "ai_analysis_status", None)
        if ai_status in ("disabled_by_configuration", "completed",
                         "timed_out", "unavailable", "empty_response"):
            result["ai_analysis"] = {
                "status": ai_status,
                "read_only": True,
                "tool_calls_allowed": False,
            }
            if ai_status == "completed":
                # The optional audit model bypasses the ordinary agent round
                # counters. Read actual provider attribution recorded by the
                # successful transport round, not the configured default.
                actual_model = str(
                    getattr(outcome, "ai_analysis_model", None) or ""
                ).strip()
                actual_provider = str(
                    getattr(outcome, "ai_analysis_provider", None) or ""
                ).strip()
                result["model"] = actual_model or None
                result["ai_analysis"]["model_verified"] = bool(actual_model)
                if actual_provider:
                    result["ai_analysis"]["provider"] = actual_provider
                repairs = getattr(outcome, "ai_advisory_repairs", ()) or ()
                if repairs:
                    result["ai_analysis"]["evidence_calibration"] = list(repairs)
                    result["evidence_validation"]["audit_ai_advisory_calibrated"] = True
            else:
                # The globally configured model name is not evidence that a
                # model answered this particular deterministic audit.
                result["model"] = None
    if long_method_denials_corrected:
        result["evidence_validation"]["observed_long_method_denial_corrected"] = True
    if exception_denials_corrected:
        result["evidence_validation"]["observed_app_exception_denial_corrected"] = True
    if state_claims_corrected:
        result["evidence_validation"]["unsupported_status_fields_removed"] = (
            state_claims_corrected
        )
    if getattr(outcome, "route", "") == "investigation-timeout":
        # Returning verified tool receipts does not mean the requested
        # investigation was completed or a historical cause established.
        result["success"] = False
        result["status_verification"] = "incomplete-timeout"
        result["metrics"]["outcome"] = "unresolved"
        result["outcome_presentation"] = deepcopy(
            present_request_outcome("unresolved")
        )
    if getattr(outcome, "route", "") == "scoped-app-status":
        result["success"] = bool(getattr(outcome, "complete", False))
        result["status_verification"] = "partial" if not result["success"] else "configuration_read"
    counters = metrics.get("counters") if isinstance(metrics.get("counters"), dict) else {}
    blocked_write_reason = any(
        int(counters.get(key, 0) or 0) > 0
        for key in (
            "rule_create_staging_unverified",
            "proposal_write_attempts_blocked",
            "write_unverified_no_confirmation",
        )
    )
    # An API exchange that successfully returned a refusal is not a
    # completed Hubitat write. Never show a positive 'Success' badge when
    # all attempted proposals were blocked and nothing is pending approval.
    if (result["request_class"] == "write"
            and blocked_write_reason
            and not result["confirmation_required"]
            and not any(row.get("success") and row.get("mutates")
                        for row in evidence if isinstance(row, dict))):
        result["success"] = False
        result["status_verification"] = "no-write-performed"
        result["metrics"]["outcome"] = "unresolved"
        result["metric_rows"] = present_request_metrics(result["metrics"])
        result["outcome_presentation"] = deepcopy(
            present_request_outcome("unresolved")
        )
    rounds = metrics.get("model_round_details") or []
    # Report actual participating models even when Auto hybrid selected paid.
    if isinstance(rounds, list) and rounds:
        usage: dict[str, int] = {}
        for entry in rounds:
            if not isinstance(entry, dict):
                continue
            model_used = str(entry.get("model") or "").strip()
            if model_used:
                usage[model_used] = usage.get(model_used, 0) + 1
        if usage:
            provider_rounds = [
                entry for entry in rounds
                if isinstance(entry, dict)
            ]
            claude_count = sum(
                1 for entry in provider_rounds
                if str(entry.get("provider") or "") == "anthropic"
            )
            paid_count = sum(
                1 for entry in provider_rounds
                if str(entry.get("provider") or "") != "anthropic"
                and str(entry.get("model") or "").casefold().startswith(
                    ("deepseek-v4", "glm-5.3")
                )
            ) + claude_count
            free_count = sum(usage.values()) - paid_count
            result["model_usage"] = {
                "models": usage,
                "paid_rounds": paid_count,
                "free_rounds": free_count,
                "paid_used": paid_count > 0,
                "charges_controlled_by": (
                    "ollama-free-allowance" if paid_count == 0
                    else "anthropic-account" if claude_count == paid_count
                    else "ollama-and-anthropic-accounts" if claude_count
                    else "ollama-account"
                ),
            }
            if paid_count and free_count and not counters.get("paid_model_requested"):
                result["model_continuity"] = {
                    "paid_rounds": paid_count, "free_rounds_after_paid": free_count,
                    "mixed_models": True, "estimated_budget_exhausted": False,
                    "accounting": "ollama-provider-credits-no-local-budget",
                }
    if int(counters.get("paid_model_requested") or 0):
        paid_used = any(
            isinstance(item, dict)
            and (
                str(item.get("provider") or "") == "anthropic"
                or str(item.get("model") or "").casefold().startswith(
                    ("deepseek-v4", "glm-5.3")
                )
            )
            for item in rounds
        )
        guard = metrics.get("paid_guard") if isinstance(metrics.get("paid_guard"), dict) else {}
        status = str(guard.get("status") or "")
        guard_reasons = {
            "disabled": "disabled_in_homebrain",
            "zero_budget": "local_budget_zero",
            "round_exceeds_budget": "estimated_round_exceeds_local_budget",
            "invalid_ledger": "local_reservation_ledger_invalid",
            "storage_unavailable": "local_reservation_ledger_unavailable",
            "unknown_model": "unsupported_paid_model",
            "reserved": "reserved_but_not_used",
        }
        reason = "used" if paid_used else (
            guard_reasons.get(status) or
            ("disabled_in_homebrain" if counters.get("paid_routing_disabled") else
             "local_budget_zero" if counters.get("paid_routing_budget_disabled") else
             "local_budget_or_ledger_blocked" if counters.get("paid_routing_reservation_blocked") else
             "no_paid_round")
        )
        paid_rounds = [
            index for index, item in enumerate(rounds)
            if isinstance(item, dict) and str(item.get("model") or "").casefold().startswith(
                ("deepseek-v4", "glm-5.3")
            )
        ]
        fallback_count = (
            sum(1 for item in rounds[paid_rounds[-1] + 1:]
                if isinstance(item, dict)
                and str(item.get("provider") or "") == "ollama-cloud"
                and not str(item.get("model") or "").casefold().startswith(
                    ("deepseek-v4", "glm-5.3")
                ))
            if paid_rounds else 0
        )
        budget_exhausted = (
            status == "round_exceeds_budget"
            and int(counters.get("paid_routing_reservation_blocked") or 0) > 0
        )
        # Keep the established paid_routing response contract stable. Only
        # add the new supplemental field when more than one model family was
        # actually used, so older clients still see the original object.
        result["paid_routing"] = {"requested": True, "used": paid_used, "reason": reason}
        if guard:
            result["paid_routing"]["local_guard"] = deepcopy(guard)
        if paid_rounds and fallback_count:
            result["model_continuity"] = {
                "paid_rounds": len(paid_rounds),
                "free_rounds_after_paid": fallback_count,
                "mixed_models": True,
                "estimated_budget_exhausted": budget_exhausted,
                "accounting": "cumulative-conservative-reservations-not-provider-charges",
            }
        if budget_exhausted and paid_rounds and fallback_count:
            result["message"] = (
                result["message"].rstrip()
                + "\n\n**Model continuity:** "
                  "HomeBrain used the paid model for "
                + str(len(paid_rounds)) + " recorded round(s), then completed "
                + str(fallback_count) + " round(s) on the free model after its "
                  "local estimated reservation limit prevented further paid "
                  "rounds. The reservation total is not an Ollama invoice."
            )
        if not paid_used:
            result["message"] = (
                result["message"].rstrip()
                + "\n\n**Paid model not used:** This answer was not verified as a "
                  "selected paid-provider response. HomeBrain routing status: "
                + reason.replace("_", " ")
                + ". The Ollama account credit balance alone cannot authorise a paid request."
            )
    coverage = getattr(outcome, "investigation_coverage", None)
    if isinstance(coverage, dict):
        result["investigation_coverage"] = deepcopy(coverage)
        if (
            coverage.get("domain") == "source_code"
            and coverage.get("analysisAnswerVerified") is False
        ):
            # A complete Groovy read and a syntactically successful HTTP call
            # must not be presented as a completed source investigation.
            # Only this explicit synthesis failure changes API success.
            result["success"] = False
    return result


__all__ = ["build_agent_response"]
