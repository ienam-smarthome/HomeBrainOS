"""Calibrate unsupported mechanisms in installed-Groovy-app load diagnoses.

A Hubitat LimitExceededException described as "generates excessive hub load"
cannot by itself identify a Zigbee/Z-Wave packet limit, character buffer or
driver transport failure. This is a limited, evidence-scoped guard against
positive attribution, not a catalog of all possible overload causes.

Do not suppress legitimate observations, app/driver call-site analysis, or
explicitly qualified questions about payload size. It also does not assert
that a size problem is impossible.
"""
from __future__ import annotations

import re
from typing import Any

_LIMIT_EXCEPTION = re.compile(r"\bLimitExceededException\b", re.I)
_SPECULATIVE_MECHANISM = (
    re.compile(
        r"(?i)\b(?:LimitExceededException|exception)\b.{0,180}"
        r"\b(?:typically occurs|occurs when|is caused by|caused by|triggered by)"
        r".{0,210}\b(?:payload|packet|buffer|character|transport|Zigbee|Z-Wave)"
    ),
    re.compile(
        r"(?i)\b(?:likely cause|high.confidence hypothesis|mechanism|"
        r"exception cause)\b.{0,200}"
        r"\b(?:reportText|payload|packet|transport|buffer|character|string)"
        r".{0,140}\b(?:exceed|limit|length|size|grow)"
    ),
    re.compile(
        r"(?i)\b(?:once|when|if)\b.{0,130}"
        r"\b(?:reportText|string|payload|packet)\b.{0,120}"
        r"\b(?:exceeds?|limit|buffer|too long)\b.{0,140}"
        r"\b(?:throws?|exception|fails?)\b"
    ),
    re.compile(
        r"(?i)\bexception cause\b.{0,130}"
        r"\b(?:reportText|payload|packet|string)\b.{0,130}"
        r"\b(?:exceed|limit|transport|buffer)"
    ),
)
_UNPROVEN_WAIT = re.compile(
    r"(?i)\b(?:high|long|slow|extreme)\s+(?:average\s+)?"
    r"(?:execution\s+)?times?\b.{0,160}"
    r"\b(?:often indicate|indicate|proves?|demonstrate)"
    r".{0,140}\b(?:waiting|timeout|timing out|payload)"
)
_UNCERTAINTY = re.compile(
    r"(?i)\b(?:cannot|can't|not|never|without)\b.{0,80}"
    r"\b(?:establish(?:ed)?|prove(?:n)?|verify|evidence|demonstrate|infer)\b"
    r"|\b(?:unproven|unverified|unconfirmed|unknown|not established)\b"
)
_DRIVER_READ_OPS = {"hub_get_source", "hub_read_source"}


def _has_verified_driver_source(evidence: list[dict[str, Any]]) -> bool:
    """Return true only for a successful *explicit driver* implementation read."""
    for receipt in evidence:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        arguments = receipt.get("arguments") or {}
        if not isinstance(arguments, dict):
            continue
        leaf = arguments.get("tool") or receipt.get("sub_tool")
        args = arguments.get("args") or arguments
        if (leaf in _DRIVER_READ_OPS and isinstance(args, dict)
                and str(args.get("type") or "").casefold() == "driver"):
            return True
    return False


def guard_unverified_source_exception_mechanism(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, tuple[str, ...]]:
    """Keep grounded source analysis; replace only unsupported causal lines.

    A bounded query returning no recent ERRORs does not retroactively disprove
    an older logged LimitExceededException, and app source retrieval does not
    establish the driver source's transport semantics.
    """
    text = str(message or "")
    if not _LIMIT_EXCEPTION.search(text) or _has_verified_driver_source(evidence):
        return text, ()
    lines = text.splitlines(keepends=True)
    updated: list[str] = []
    repaired: set[str] = set()
    for line in lines:
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        if _UNCERTAINTY.search(body):
            updated.append(line)
            continue
        if any(pattern.search(body) for pattern in _SPECULATIVE_MECHANISM):
            repaired.add("source_unsupported_payload_limit_cause")
            updated.append(
                "Payload or transport limits are **not established** by "
                "the available app-source and log evidence. A "
                "LimitExceededException must be interpreted using its exact "
                "hub-load message, the relevant method/driver implementation "
                "and execution-frequency evidence, rather than assuming "
                "a Zigbee/Z-Wave or character-buffer limit." + newline
            )
        elif _UNPROVEN_WAIT.search(body):
            repaired.add("source_unverified_wait_causality")
            updated.append(
                "Long average execution time is an observation, **not proof** "
                "that a device response timed out or a large payload caused "
                "the delay; investigate the actual execution path." + newline
            )
        else:
            updated.append(line)
    # Do not invent a positive root-cause verdict even after a repair.
    return "".join(updated), tuple(sorted(repaired))


__all__ = ["guard_unverified_source_exception_mechanism"]
