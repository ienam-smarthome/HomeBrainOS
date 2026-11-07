"""Correct universal controller-coverage claims against the observed graph.

This is not a Bedroom/light-name template. Coverage is derived from the
normalized evidence graph's distinct observed ON boundaries and aligned
controller starts. The guard only corrects unqualified universals about the
controller's association with the *whole* examined history, preserving bounded
phrases such as "all three recent button-aligned events".
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph

_ALL_OBSERVED_ON = re.compile(
    r"\b(?:every|all)\s+"
    r"(?:(?:recorded|observed)\s+)?"
    r"(?:light[- ]on|turn[- ]on|ON)\s+"
    r"(?:intervals?|events?|transitions?)\b",
    re.I,
)
_CONTROLLER_CONTEXT = re.compile(
    r"\b(?:button|dimmer|controller|button[- ]press|pushed)\b", re.I
)


def guard_causal_controller_history_coverage(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
) -> tuple[str, bool]:
    if not original_user:
        # API serialization has no original user message. Recover the focal
        # event only from the host-verified requested boundary receipt, never
        # from arbitrary model prose that could mention many times.
        candidates = []
        for item in evidence:
            if (
                isinstance(item, dict)
                and item.get("success") is True
                and item.get("tool") == "homebrain_causal_secondary_correlation"
            ):
                details = item.get("details") or {}
                date_text = str(details.get("requestedBoundary") or "")
                subject = str(details.get("subject") or "")
                if date_text and subject:
                    try:
                        moment = datetime.fromisoformat(
                            date_text.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                    candidates.append(
                        f"Why did {subject} turn on at "
                        f"{moment:%H:%M:%S} on {moment.day} {moment:%B %Y}?"
                    )
        if len(set(candidates)) == 1:
            original_user = candidates[0]
    graph = build_causal_evidence_graph(evidence, original_user)
    coverage = graph.get("controllerCoverage") or {}
    observed = coverage.get("observedStartCount")
    aligned = coverage.get("alignedObservedStartCount")
    if (
        not isinstance(observed, int)
        or not isinstance(aligned, int)
        or not (0 < aligned < observed)
    ):
        return str(message or ""), False

    changed = False
    out = []
    for raw in str(message or "").splitlines(keepends=True):
        # Never transform a historical statement without an explicit
        # controller claim, or rewrite a correctly scoped "three recent" claim.
        if (
            _ALL_OBSERVED_ON.search(raw)
            and _CONTROLLER_CONTEXT.search(raw)
            and not re.search(r"\b(?:recent|last|latest)\b", raw, re.I)
        ):
            updated, count = _ALL_OBSERVED_ON.subn(
                f"{aligned} of {observed} observed ON intervals", raw
            )
            out.append(updated)
            changed = changed or bool(count)
        else:
            out.append(raw)
    return "".join(out), changed


def guard_focal_log_coverage_claims(
    message: str, evidence: list[dict[str, Any]], original_user: str = "",
) -> tuple[str, bool]:
    """Require attested focal request scope for historical log absence claims.

    A successful read, its requested window and the returned event population
    are different facts. Even a correctly bounded request cannot prove global
    event absence. Preserve explicitly scoped returned-sample observations.
    """
    from claim_evidence_adapter import packet_from_evidence
    packet = packet_from_evidence(evidence, original_question=original_user)
    original = str(message or "")
    if not packet.focal_time:
        return original, False
    scope = packet.log_request_coverage
    bounded = scope.get("bounded_log_requests_covering_focal", 0)
    apps = scope.get("bounded_app_log_requests_covering_focal", 0)
    changed = False
    pieces = re.split(r"(\n|(?<=[.!?])[ \t]+)", original)
    # Work by line/sentence without deleting valid timeline rows or positives.
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if sentence.lstrip().startswith("|") or not re.search(r"\blogs?\b", sentence, re.I):
            continue
        negative = re.search(
            r"\b(?:no|zero)\b.{0,100}\b(?:events?|entries|messages?|records?|commands?|execution)\b"
            r"|\blogs?\b.{0,80}\b(?:empty|no|zero)\b"
            r"|\b(?:not|never)\s+(?:captured|recorded|found)\b", sentence, re.I)
        if not negative:
            continue
        # A limitation is not an assertion of absence.
        if re.search(r"\b(?:cannot|can't|does\s+not|do\s+not)\s+(?:prove|establish|rule\s+out)\b"
                     r"|\bnot\s+(?:proof|evidence)\s+(?:of|that)\b", sentence, re.I):
            continue
        returned_scope = re.search(r"\b(?:returned|retrieved|sample|query|queries)\b", sentence, re.I)
        focal_scope = re.search(
            r"\b(?:focal|corresponding|surrounding|around|at\s+(?:the|this)\s+(?:event|timestamp)|"
            r"for\s+(?:that|this|the\s+event)\s+window)\b", sentence, re.I)
        app_scope = re.search(r"\b(?:apps?|rules?|automation)\b", sentence, re.I)
        checked_focal = apps if app_scope else bounded
        if returned_scope and (not focal_scope or checked_focal):
            continue
        prefix = re.match(r"\s*(?:[-*+]\s+)?", sentence).group(0)
        if bounded and not checked_focal:
            correction = (
                "A bounded general log request included the focal time. "
                "App-specific execution coverage and historical completeness remain "
                "unverified; the general query cannot exclude automation execution."
            )
        elif not checked_focal:
            correction = (
                "The returned log reads do not establish event absence at the focal time. "
                + (
                    "Open-ended samples and queries for other times cannot exclude "
                    "automation execution during this transition."
                    if scope.get("unbounded_or_invalid_window_requests", 0) else
                    "No bounded request covering this focal time was verified; "
                    "automation execution remains unverified."
                )
            )
        else:
            correction = (
                "A bounded log request included the focal time, but only its returned "
                "records were checked; historical completeness and automation "
                "non-execution remain unverified."
            )
        pieces[index] = prefix + correction
        changed = True
    return "".join(pieces), changed


__all__ = ["guard_causal_controller_history_coverage", "guard_focal_log_coverage_claims"]
