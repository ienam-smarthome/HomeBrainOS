"""Canonical Hubitat device command receipt adjudication.

A successful MCP call only establishes dispatch acceptance. A typed waitFor
acknowledgement establishes reported attribute convergence, not physical
electrical/network effects. Never treat strings like "false" as true; never
resend a command automatically after an ambiguous transport result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _same_wire_value(observed: Any, expected: Any) -> bool:
    if isinstance(observed, bool) or isinstance(expected, bool):
        return str(observed).casefold() == str(expected).casefold()
    a = str(observed).strip()
    b = str(expected).strip()
    try:
        return float(a) == float(b)
    except (ValueError, OverflowError):
        return a.casefold() == b.casefold()


@dataclass(frozen=True)
class CommandReceipt:
    status: str
    command_accepted: bool
    state_verified: bool | None
    observed_value: str | None

    @property
    def change_verified(self) -> bool:
        return self.command_accepted and self.state_verified is True


def adjudicate_command_receipt(
    *, accepted: bool, expected: Any | None, wait_for: Any,
) -> CommandReceipt:
    if not accepted:
        return CommandReceipt("dispatch_failed", False, None, None)
    if expected is None:
        return CommandReceipt("accepted_unverified", True, None, None)
    if not isinstance(wait_for, Mapping):
        return CommandReceipt("confirmation_missing", True, False, None)
    converged = wait_for.get("converged")
    value = wait_for.get("value")
    observed = str(value)[:80] if type(value) in (str, int, float) else None
    if converged is True:
        # The gateway may omit its observedValue; then the explicit typed
        # convergence report is the best available *Hubitat* state evidence.
        if observed is not None and not _same_wire_value(observed, expected):
            return CommandReceipt("confirmation_mismatch", True, False, observed)
        return CommandReceipt("reported_state_converged", True, True, observed)
    if converged is False:
        return CommandReceipt("not_converged", True, False, observed)
    return CommandReceipt("confirmation_invalid", True, False, observed)


__all__ = ["CommandReceipt", "adjudicate_command_receipt"]
