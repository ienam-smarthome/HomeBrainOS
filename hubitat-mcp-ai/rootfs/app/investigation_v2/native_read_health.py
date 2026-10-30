"""Per-investigation bounded READ health and timeout circuit breaker.

Transport health is separate from historical evidence completeness. A timed
out MCP READ is not a negative response and may not be used to establish a
missing device state, missing log, or rule absence.

The model always selects tools. This module only limits the cost of executing
model-selected reads and detects a failing source connection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Discovery/inventory reads are expensive and frequently not needed for
# already grounded target investigation. No operation is selected here.
_BROAD = frozenset({
    "hub_list_devices", "hub_list_apps", "hub_search_tools",
})


def read_timeout_cap(
    operation: str,
    caller_timeout: float,
    remaining_seconds: float,
) -> float:
    """Cap a single model-selected READ while retaining caller tightening."""
    cap = 5.0 if operation in _BROAD else 10.0
    return min(
        max(0.1, float(remaining_seconds)),
        max(0.1, min(float(caller_timeout), cap)),
    )


@dataclass
class ReadHealth:
    max_consecutive_timeouts: int = 2
    consecutive_timeouts: int = 0
    total_timeouts: int = 0
    successful_reads_after_timeout: int = 0
    stopped: bool = False
    timed_out_operations: list[str] = field(default_factory=list)

    def completed(self, operation: str, error: str | None) -> None:
        if error == "read_timeout":
            self.total_timeouts += 1
            self.consecutive_timeouts += 1
            self.timed_out_operations.append(operation[:90])
            if self.consecutive_timeouts >= self.max_consecutive_timeouts:
                self.stopped = True
        elif error is None:
            if self.consecutive_timeouts:
                self.successful_reads_after_timeout += 1
            self.consecutive_timeouts = 0
        # Other errors are not proof of healthy transport or a recovery.
        # They do not by themselves trip the timeout circuit.

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": "open" if self.stopped else
                     "degraded" if self.total_timeouts else "normal",
            "timeout_count": self.total_timeouts,
            "consecutive_timeouts": self.consecutive_timeouts,
            "stopped_after_timeout_threshold": self.stopped,
            "timeout_threshold": self.max_consecutive_timeouts,
            "timed_out_operations": self.timed_out_operations[-8:],
            "interpretation": (
                "Multiple model-selected MCP operations timed out in this "
                "investigation. This is a transport/source-access failure, "
                "not proof of missing historical events."
                if self.stopped else
                "No timeout circuit opened."),
        }


__all__=["ReadHealth", "read_timeout_cap"]
