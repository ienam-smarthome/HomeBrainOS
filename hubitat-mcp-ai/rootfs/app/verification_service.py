from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from assistant_contracts import VerificationOutcome


_TRUE_VALUES = {"true", "1", "yes", "on", "active", "enabled", "disabled", "paused"}
_FALSE_VALUES = {"false", "0", "no", "off", "inactive"}


@dataclass(frozen=True, slots=True)
class StateVerification:
    """Authoritative result of checking one requested post-write state."""

    outcome: VerificationOutcome
    expected: bool
    observed: bool | None
    verified: bool
    source: str | None = None

    @property
    def accepted_only(self) -> bool:
        return self.outcome is VerificationOutcome.SENT and not self.verified


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return None


def deep_field(value: Any, names: Iterable[str]) -> Any:
    wanted = {str(name).lower() for name in names}
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            for key, nested in current.items():
                if str(key).lower() in wanted and nested not in (None, ""):
                    return nested
                stack.append(nested)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return None


def verify_boolean_state(
    *,
    expected: bool,
    field_names: Iterable[str],
    write_payload: Any = None,
    readback_payload: Any = None,
    write_source: str = "write response",
    readback_source: str = "inventory read-back",
    command_failed: bool = False,
) -> StateVerification:
    """Verify a boolean post-state using write evidence before independent read-back."""

    if command_failed:
        return StateVerification(
            outcome=VerificationOutcome.FAILED,
            expected=expected,
            observed=None,
            verified=False,
            source=None,
        )

    write_value = coerce_bool(deep_field(write_payload, field_names))
    if write_value is expected:
        return StateVerification(
            outcome=VerificationOutcome.COMPLETED,
            expected=expected,
            observed=write_value,
            verified=True,
            source=write_source,
        )

    readback_value = coerce_bool(deep_field(readback_payload, field_names))
    if readback_value is expected:
        return StateVerification(
            outcome=VerificationOutcome.COMPLETED,
            expected=expected,
            observed=readback_value,
            verified=True,
            source=readback_source,
        )

    observed = readback_value if readback_value is not None else write_value
    return StateVerification(
        outcome=VerificationOutcome.SENT,
        expected=expected,
        observed=observed,
        verified=False,
        source=readback_source if readback_value is not None else write_source if write_value is not None else None,
    )


__all__ = [
    "StateVerification",
    "coerce_bool",
    "deep_field",
    "verify_boolean_state",
]
