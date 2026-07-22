from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    RESOLVED_GROUP = "resolved_group"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    UNSUPPORTED_ACTION = "unsupported_action"


class VerificationOutcome(str, Enum):
    COMPLETED = "completed"
    SENT = "sent"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class RouteClass(str, Enum):
    FAST_CONTROL = "fast-control"
    FAST_READ = "fast-read"
    AGENT = "agent"


class ResolvedTarget(BaseModel):
    device_id: str
    label: str
    room: str = ""
    types: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match_reason: str = ""
    supports_action: bool | None = None


class EntityResolutionResult(BaseModel):
    status: ResolutionStatus
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: str
    reason: str
    targets: list[ResolvedTarget] = Field(default_factory=list)
    candidates: list[ResolvedTarget] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)


class ExecutionItem(BaseModel):
    device_id: str
    label: str
    action: str
    outcome: VerificationOutcome
    submitted: bool = False
    accepted_by_hub: bool = False
    verified: bool | None = None
    observed_state: str | None = None
    message: str = ""


class ExecutionResult(BaseModel):
    outcome: VerificationOutcome
    success: bool
    submitted: bool
    verified: bool | None
    targets: list[ExecutionItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "EntityResolutionResult",
    "ExecutionItem",
    "ExecutionResult",
    "ResolvedTarget",
    "ResolutionStatus",
    "RouteClass",
    "VerificationOutcome",
]
