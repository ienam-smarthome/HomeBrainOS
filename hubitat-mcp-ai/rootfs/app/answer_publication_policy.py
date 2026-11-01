"""Evidence-bound answer publication decision; never a causal claim verifier.

The source-typed answer is authoritative when no independently attested
model-claim contract exists. Ordinary questions get a concise source-derived
answer; an explicit request for the full incident ledger gets the established
long-form rendering. Do not confuse synthesis-validation success with
source-level verification of arbitrary natural-language model claims.

This policy does not route tools, mutate devices, call models or change
technical evidence coverage. It can be used across evidence domains.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_PUBLICATION_SCHEMA = "homebrain-answer-publication-decision.v1"

# Detailed formatting is a direct user instruction, not an inference about
# which evidence should be collected. Avoid keyword-driven cause attribution.
_EXPLICIT_DETAIL = re.compile(
    r"(?i)\b(?:full|complete|exhaustive|unabridged|step[- ]by[- ]step)\s+"
    r"(?:technical\s+)?(?:report|event\s+(?:list|history|timeline)|"
    r"evidence\s+(?:ledger|report)|investigation\s+report|diagnostic\s+report)"
    r"\b|\b(?:show|include|list)\s+(?:all|every)\s+"
    r"(?:reported\s+)?(?:event|log|command)\s+(?:row|entry|record)s?\b"
)


def publish_source_typed_answer(
    request: str,
    *,
    concise: Callable[[], str],
    detailed: Callable[[], str],
    normalized: dict[str, Any] | None,
    evidence_coverage: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Choose a bounded presentation without treating model prose as proof.

    Both candidate writers work only from normalized source receipts; this
    function never transforms arbitrary model text or grants attestation.
    The same technical normalized evidence remains in API coverage.
    """
    if not isinstance(normalized, dict) or not normalized.get("deviceId"):
        raise ValueError("source-typed publication requires a resolved target")
    if not isinstance(evidence_coverage, dict):
        raise ValueError("source-typed publication requires coverage metadata")
    full_requested = bool(_EXPLICIT_DETAIL.search(str(request or "")))
    # A complex/partial source graph can require exact issuer, clock and
    # boundary qualifications even when the question asks for a short answer.
    # Do not summarize away verified commands, truncated history or a
    # source-correlated watchdog reference. This evidence-driven override is
    # independent of room, device name or request keyword.
    command_count = normalized.get("commandCount")
    evidence_requires_detail = bool(
        normalized.get("truncated") is True
        or (type(command_count) is int and command_count > 0)
        or evidence_coverage.get("watchdogEventTimingCorrelation") is not None
    )
    full = full_requested or evidence_requires_detail
    message = detailed() if full else concise()
    if not isinstance(message, str) or not message.strip():
        raise ValueError("source-backed answer cannot be empty")
    mode = (
        "requested-detail" if full_requested else
        "evidence-depth-required" if evidence_requires_detail else "concise"
    )
    decision = {
        "schema": _PUBLICATION_SCHEMA,
        "strategy": "source-typed-evidence",
        "mode": mode,
        "modelProseCertified": False,
        "claimSourceVerification": "normalized-targeted-receipts",
        "physicalCauseCertified": False,
        "coverageReplaced": False,
    }
    return message, decision


__all__ = ["publish_source_typed_answer"]
