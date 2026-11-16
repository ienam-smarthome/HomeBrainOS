"""Receipt-grounded publication boundary for read-only causal V2 answers.

A final model audit is still model text, not evidence. This module detects a
small class of *definite* event-wide denials and event-specific causal verdicts
when the original current-request receipts cannot support their scope.
It never selects a device, tool, model, action, or purported causal source.
"""
from __future__ import annotations

import re
from typing import Any

from causal_decision_frontier import causal_controller_frontier
from read_only_receipt_fallback import source_only_partial_answer

# High-precision definitive assertions, not a generic sentiment classifier.
# Stay general across heating, lights, locks, switches, fans and other actuators.
_ASSERTIONS = (
    ("historical_absence", re.compile(
        r"\b(?:did\s+not|didn't|never)\s+(?:actually\s+)?"
        r"(?:turn\s+(?:on|off)|start|stop|activate|deactivate|operate|happen|occur)\b",
        re.I)),
    ("exclusive_event", re.compile(
        r"\b(?:only\s+(?:verifiable|recorded|observed|actual)|"
        r"no\s+(?:record|evidence)\s+of\s+any)\b"
        r"[^\n.!?]{0,130}\b(?:heating|activation|transition|"
        r"event|change|command|start|stop|turn|operation)\b",
        re.I)),
    ("causal_verdict", re.compile(
        r"\b(?:turned\s+(?:on|off)|switched\s+(?:on|off)|"
        r"started|stopped|activated|deactivated)\b"
        r"[^\n.!?]{0,125}\bbecause\b|"
        r"\b(?:strongly\s+)?(?:indicates|proves|demonstrates|establishes)"
        r"\s+causation\b|"
        r"\b(?:the\s+)?(?:verifiable|confirmed|actual)\s+initiator\b|"
        r"\b(?:directly\s+caused|the\s+direct\s+cause\s+of)\b",
        re.I)),
)
# Explicit uncertainty or quotation is not a positive causal verdict. Avoid
# treating "we cannot establish causation" as a claimed establishment.
_QUALIFIER = re.compile(
    r"\b(?:not|cannot|can't|unverified|unsupported|uncertain|"
    r"insufficient|do\s+not|does\s+not|would\s+not)\b", re.I
)


def _unsupported_verdicts(answer: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in _ASSERTIONS:
        for match in pattern.finditer(answer[:18000]):
            # Scope a local qualifier to the assertion's immediate clause.
            # A caveat in a later paragraph does not undo a definite headline.
            start = max(0, match.start() - 45)
            segment = answer[start:match.end()]
            segment = segment.split("\n")[-1]
            if label == "causal_verdict" and _QUALIFIER.search(segment):
                continue
            hits.append(label)
            break
    return hits


def review_causal_publication(
    question: str, answer: str, receipts: list[dict[str, Any]], *,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Conservatively withhold unsupported definite causal/absence claims.

    Only the original current-request successful device event rows may appear
    in the replacement. A strong denial needs complete focal-output history
    and an exclusion-worthy source; bounded sibling histories cannot do that.
    A definite controller *reason* needs event-time controller decision data,
    not merely an attribute producedBy or nearby setpoint timestamp.
    A successful app log read alone is NOT evidence of a specific decision.
    """
    result: dict[str, Any] = {
        "status": "unchanged", "reason_categories": [], "answer": answer,
        "scope": "read_only_causal_original_receipts",
    }
    if not isinstance(answer, str) or not answer.strip():
        return result
    categories = _unsupported_verdicts(answer)
    if not categories:
        return result
    decision = causal_controller_frontier(receipts)
    # The mere existence of an app log does not prove its contents. Unless a
    # stronger verified causal decision contract exists, avoid elevating model
    # narration into an event-specific causal certificate.
    partial = source_only_partial_answer(
        question, receipts, timezone_name=timezone_name
    )
    if partial:
        result["answer"] = (
            partial + "\n\n**Publication check:** A definite historical "
            "absence, exclusive event or event-specific cause in the model "
            "draft was not supported at the claimed scope by this request's "
            "original source receipts. Those claims were withheld. "
            "A setpoint/command report, a later state report, or a listener "
            "notification alone does not establish the controller's "
            "internal reason or independent physical operation."
        )
    else:
        result["answer"] = (
            "**Investigation incomplete — cause unverified.** "
            "The available current-request evidence did not establish the "
            "requested historical outcome and its event-specific initiating "
            "decision. The model's definite denial or causal attribution "
            "was withheld rather than treating missing observations as proof. "
            "Original read attempts and errors remain in Technical JSON."
        )
    result["status"] = "withheld_unsupported_definite_claims"
    result["reason_categories"] = categories
    result["observed_original_command_rows"] = decision[
        "original_device_command_rows_indexed"
    ]
    result["app_execution_read_success_count"] = decision[
        "app_scoped_execution_log_successes_for_recorded_issuers"
    ]
    return result
