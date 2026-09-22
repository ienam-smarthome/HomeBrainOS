from __future__ import annotations

import re
from typing import Any

from semantic_plan import SemanticAction, SemanticPlan, SemanticTarget


_POLITE_PREFIX = re.compile(
    r"^\s*(?:(?:please\s+)|(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?))",
    re.I,
)
_READ_QUESTION_PREFIX = re.compile(
    r"^\s*(?:why|what|which|where|who|when|how|is|are|was|were|did|does|do|"
    r"has|have|had|should)\b",
    re.I,
)
_FUTURE_OR_RECURRING = re.compile(
    r"\b(?:tomorrow|later|every|daily|weekday|weekend|tonight|"
    r"sunrise|sunset|at\s+\d{1,2}(?::\d{2})?|"
    r"in\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)|"
    r"after\s+\d+\s*(?:minutes?|mins?|hours?|hrs?))\b",
    re.I,
)
_TRAILING_PUNCTUATION = re.compile(r"[.!?]+\s*$")
_PRONOUN_TARGET = re.compile(
    r"^(?:it|this|that|them|these|those|this one|that one|the same one)$",
    re.I,
)
_AMOUNT = (
    r"(?P<amount>\d{1,3}(?:\.\d+)?)"
    r"(?:\s*(?:%|percent|percentage\s+points?|points?))?"
)
_TEMP_AMOUNT = (
    r"(?P<temp_amount>\d{1,2}(?:\.\d+)?)\s*(?:degrees?|°[cf]?)?"
    r"|(?P<half_amount>half\s+(?:a\s+)?degree)"
)
_MAGNITUDE = r"(?P<magnitude>a\s+little|slightly|a\s+lot|much)"


def _clean_prompt(prompt: str) -> str:
    value = " ".join(str(prompt or "").strip().split())
    value = _TRAILING_PUNCTUATION.sub("", value)
    value = _POLITE_PREFIX.sub("", value).strip()
    return value


def _clean_target(value: Any) -> str:
    target = " ".join(str(value or "").strip().split())
    target = re.sub(r"\s+please$", "", target, flags=re.I).strip()
    return target


def _magnitude(value: Any) -> str:
    text = str(value or "").casefold().strip()
    if text in {"a little", "slightly"}:
        return "small"
    if text in {"a lot", "much"}:
        return "large"
    return "default"


def _relative_plan(
    *,
    target: str,
    operation: str,
    direction: str,
    kind: str,
    amount: float | None = None,
    magnitude: str = "default",
) -> SemanticPlan | None:
    target = _clean_target(target)
    if not target or _PRONOUN_TARGET.fullmatch(target):
        return None

    delta: float | None = None
    if amount is not None:
        if amount <= 0:
            return None
        limit = 100.0 if operation == "adjust_level" else 10.0
        if amount > limit:
            return None
        delta = amount if direction == "increase" else -amount

    return SemanticPlan(
        domain="device_control",
        timing="now",
        target=SemanticTarget(scope="device", name=target, kind=kind),
        action=SemanticAction(
            operation=operation,
            delta=delta,
            direction=direction,
            magnitude=magnitude,
        ),
        confidence="high",
        source="fastpath",
    )


def semantic_fast_plan(prompt: str) -> SemanticPlan | None:
    """Parse clear semantic routine-control wording without a provider round.

    This deliberately covers only anchored, unambiguous brightness and heating
    forms. The host still grounds the raw target against authoritative device/
    room identity before deterministic execution. Anything outside this narrow
    grammar falls through to the semantic model planner.
    """

    raw = str(prompt or "")
    if _READ_QUESTION_PREFIX.search(raw) or _FUTURE_OR_RECURRING.search(raw):
        return None
    text = _clean_prompt(raw)
    if not text:
        return None

    match = re.fullmatch(
        rf"(?P<verb>increase|raise|boost|decrease|lower|reduce)\s+"
        rf"(?P<target>.+?)\s+(?:brightness|light\s+level|level)"
        rf"(?:\s+by\s+{_AMOUNT})?"
        rf"(?:\s+{_MAGNITUDE})?",
        text,
        flags=re.I,
    )
    if match:
        verb = match.group("verb").casefold()
        direction = "increase" if verb in {"increase", "raise", "boost"} else "decrease"
        amount = float(match.group("amount")) if match.group("amount") else None
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_level",
            direction=direction,
            kind="light",
            amount=amount,
            magnitude=_magnitude(match.group("magnitude")),
        )

    match = re.fullmatch(
        rf"make\s+(?P<target>.+?)\s+(?:{_MAGNITUDE}\s+)?"
        r"(?P<quality>brighter|dimmer)",
        text,
        flags=re.I,
    )
    if match:
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_level",
            direction=(
                "increase"
                if match.group("quality").casefold() == "brighter"
                else "decrease"
            ),
            kind="light",
            magnitude=_magnitude(match.group("magnitude")),
        )

    match = re.fullmatch(
        rf"(?P<verb>brighten|dim)\s+(?P<target>.+?)"
        rf"(?:\s+by\s+{_AMOUNT})?",
        text,
        flags=re.I,
    )
    if match:
        amount = float(match.group("amount")) if match.group("amount") else None
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_level",
            direction=(
                "increase"
                if match.group("verb").casefold() == "brighten"
                else "decrease"
            ),
            kind="light",
            amount=amount,
        )

    match = re.fullmatch(
        rf"turn\s+(?P<target>.+?\blights?)\s+(?P<direction>up|down)"
        rf"(?:\s+by\s+{_AMOUNT})?",
        text,
        flags=re.I,
    )
    if match:
        amount = float(match.group("amount")) if match.group("amount") else None
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_level",
            direction=(
                "increase"
                if match.group("direction").casefold() == "up"
                else "decrease"
            ),
            kind="light",
            amount=amount,
        )

    match = re.fullmatch(
        rf"make\s+(?P<target>.+?)\s+(?:{_MAGNITUDE}\s+)?"
        r"(?P<quality>warmer|cooler)",
        text,
        flags=re.I,
    )
    if match:
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_temperature",
            direction=(
                "increase"
                if match.group("quality").casefold() == "warmer"
                else "decrease"
            ),
            kind="thermostat",
            magnitude=_magnitude(match.group("magnitude")),
        )

    match = re.fullmatch(
        rf"(?P<verb>increase|raise|decrease|lower|reduce)\s+"
        rf"(?P<target>.+?)\s+(?:temperature|heating)"
        rf"(?:\s+by\s+(?:{_TEMP_AMOUNT}))?"
        rf"(?:\s+{_MAGNITUDE})?",
        text,
        flags=re.I,
    )
    if match:
        verb = match.group("verb").casefold()
        direction = "increase" if verb in {"increase", "raise"} else "decrease"
        amount: float | None = None
        if match.group("temp_amount"):
            amount = float(match.group("temp_amount"))
        elif match.group("half_amount"):
            amount = 0.5
        return _relative_plan(
            target=match.group("target"),
            operation="adjust_temperature",
            direction=direction,
            kind="thermostat",
            amount=amount,
            magnitude=_magnitude(match.group("magnitude")),
        )

    match = re.fullmatch(
        r"set\s+(?P<target>.+?)(?:\s+(?:temperature|thermostat|heating))?"
        r"\s+to\s+(?P<value>\d{1,2}(?:\.\d+)?)\s*(?:degrees?|°[cf]?)",
        text,
        flags=re.I,
    )
    if match:
        target = _clean_target(match.group("target"))
        value = float(match.group("value"))
        if target and 5.0 <= value <= 35.0:
            return SemanticPlan(
                domain="device_control",
                timing="now",
                target=SemanticTarget(
                    scope="device",
                    name=target,
                    kind="thermostat",
                ),
                action=SemanticAction(
                    operation="set_temperature",
                    value=value,
                ),
                confidence="high",
                source="fastpath",
            )

    return None


__all__ = ["semantic_fast_plan"]
