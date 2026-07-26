from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class RouteKind(str, Enum):
    """The three authoritative HomeBrain execution lanes."""

    FAST_CONTROL = "fast-control"
    FAST_READ = "fast-read"
    AGENT = "agent"


class VerificationState(str, Enum):
    """How strongly an execution result is verified."""

    NOT_APPLICABLE = "not-applicable"
    NOT_ATTEMPTED = "not-attempted"
    ACCEPTED = "accepted"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Normalised request shared by deterministic and agent routes."""

    query: str
    session_id: str | None = None
    requested_route: RouteKind | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        query = str(self.query or "").strip()
        if not query:
            raise ValueError("ExecutionRequest.query must not be empty")
        object.__setattr__(self, "query", query)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Typed internal result before conversion to the current response dictionary."""

    success: bool
    route: RouteKind
    intent: str
    message: str
    verification: VerificationState = VerificationState.NOT_APPLICABLE
    data: Mapping[str, Any] = field(default_factory=dict)
    technical: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        intent = str(self.intent or "").strip()
        message = str(self.message or "").strip()
        if not intent:
            raise ValueError("ExecutionResult.intent must not be empty")
        if not message:
            raise ValueError("ExecutionResult.message must not be empty")
        object.__setattr__(self, "intent", intent)
        object.__setattr__(self, "message", message)

    def to_response(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "success": self.success,
            "route": self.route.value,
            "intent": self.intent,
            "message": self.message,
            "verification": self.verification.value,
        }
        if self.data:
            response.update(dict(self.data))
        if self.technical:
            response["technical"] = dict(self.technical)
        return response


_ROUTE_ALIASES: dict[str, RouteKind] = {
    "mcp-fast": RouteKind.FAST_READ,
    "mcp-rule-control": RouteKind.FAST_CONTROL,
    "mcp-app-control": RouteKind.FAST_CONTROL,
    "ollama+mcp": RouteKind.AGENT,
    "ai-evidence": RouteKind.AGENT,
}


def classify_legacy_route(route: Any, *, success: bool = True) -> RouteKind:
    """Map existing response route names onto the three-route architecture."""

    normalised = str(route or "").strip().lower()
    if normalised in _ROUTE_ALIASES:
        return _ROUTE_ALIASES[normalised]
    if "control" in normalised or "write" in normalised:
        return RouteKind.FAST_CONTROL
    if "agent" in normalised or "ollama" in normalised or "evidence" in normalised:
        return RouteKind.AGENT
    if normalised.startswith("mcp") or "read" in normalised or "status" in normalised:
        return RouteKind.FAST_READ
    return RouteKind.FAST_READ if success else RouteKind.AGENT


def infer_verification_state(response: Mapping[str, Any]) -> VerificationState:
    """Infer the current verification strength without changing existing routes."""

    if response.get("post_state_verified") is True:
        return VerificationState.VERIFIED
    technical = response.get("technical")
    if isinstance(technical, Mapping):
        if technical.get("post_state_verified") is True or technical.get("command_verified") is True:
            return VerificationState.VERIFIED
        if technical.get("command_sent") is False:
            return VerificationState.NOT_ATTEMPTED
    intent = str(response.get("intent") or "").lower()
    if "verified" in intent:
        return VerificationState.VERIFIED
    if "accepted" in intent or response.get("success") is True and "control" in str(response.get("route") or ""):
        return VerificationState.ACCEPTED
    if response.get("success") is False:
        return VerificationState.FAILED
    return VerificationState.NOT_APPLICABLE


__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "RouteKind",
    "VerificationState",
    "classify_legacy_route",
    "infer_verification_state",
]
