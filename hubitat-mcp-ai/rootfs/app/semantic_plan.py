from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


TargetScope = Literal["room", "device", "home", "selection", "unknown"]
DeviceKind = Literal["light", "switch", "auto"]
ControlOperation = Literal[
    "turn_on",
    "turn_off",
    "toggle",
    "set_level",
    "adjust_level",
]
PlanDomain = Literal["device_control", "other"]
PlanTiming = Literal["now", "scheduled", "unknown"]
PlanConfidence = Literal["high", "medium", "low"]
PlanSource = Literal["fastpath", "model"]


class SemanticTarget(BaseModel):
    scope: TargetScope
    name: str = Field(default="", max_length=160)
    kind: DeviceKind = "auto"

    @model_validator(mode="after")
    def validate_target_name(self) -> "SemanticTarget":
        self.name = " ".join(self.name.strip().split())
        if self.scope in {"room", "device", "selection"} and not self.name:
            raise ValueError("named target scope requires name")
        return self


class SemanticAction(BaseModel):
    operation: ControlOperation
    value: int | None = Field(default=None, ge=0, le=100)
    delta: int | None = Field(default=None, ge=-100, le=100)
    direction: Literal["increase", "decrease"] | None = None
    magnitude: Literal["small", "default", "large"] = "default"

    @model_validator(mode="after")
    def validate_operation_payload(self) -> "SemanticAction":
        if self.operation == "set_level" and self.value is None:
            raise ValueError("set_level requires value")
        if self.operation != "set_level" and self.value is not None:
            raise ValueError("value is only valid for set_level")
        if self.operation != "adjust_level":
            if self.delta is not None:
                raise ValueError("delta is only valid for adjust_level")
            if self.direction is not None:
                raise ValueError("direction is only valid for adjust_level")
            return self
        if self.delta == 0:
            raise ValueError("adjust_level delta cannot be zero")
        if self.direction is None and self.delta is not None:
            self.direction = "increase" if self.delta > 0 else "decrease"
        if self.direction is None:
            raise ValueError("adjust_level requires direction")
        if self.delta is not None:
            if self.direction == "increase" and self.delta < 0:
                raise ValueError("increase direction conflicts with negative delta")
            if self.direction == "decrease" and self.delta > 0:
                raise ValueError("decrease direction conflicts with positive delta")
        return self


class SemanticPlan(BaseModel):
    version: Literal["1"] = "1"
    domain: PlanDomain
    timing: PlanTiming = "now"
    target: SemanticTarget | None = None
    action: SemanticAction | None = None
    needs_clarification: bool = False
    clarification_question: str = Field(default="", max_length=240)
    confidence: PlanConfidence = "medium"
    source: PlanSource = "model"

    @model_validator(mode="after")
    def validate_plan(self) -> "SemanticPlan":
        self.clarification_question = " ".join(
            self.clarification_question.strip().split()
        )
        if self.needs_clarification and not self.clarification_question:
            raise ValueError("clarification_question required when clarification is needed")
        if (
            self.domain == "device_control"
            and not self.needs_clarification
            and (self.target is None or self.action is None)
        ):
            raise ValueError("device_control plan requires target and action")
        return self

    @property
    def executable_routine_control(self) -> bool:
        return (
            self.domain == "device_control"
            and self.timing == "now"
            and not self.needs_clarification
            and self.target is not None
            and self.action is not None
            and self.target.scope in {"room", "device", "selection"}
            and self.target.kind in {"light", "switch", "auto"}
        )


def semantic_plan_from_model_text(text: str) -> SemanticPlan:
    """Parse the first JSON object in model text into the strict plan contract."""

    value = str(text or "").strip()
    if not value:
        raise ValueError("semantic planner returned empty content")

    decoder = json.JSONDecoder()
    last_error: Exception | None = None
    for index, char in enumerate(value):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(value[index:])
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(payload, dict):
            continue
        try:
            return SemanticPlan.model_validate(payload)
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise ValueError(f"invalid semantic plan: {last_error}") from last_error
    raise ValueError("semantic planner returned no JSON object")


def semantic_plan_from_control_arguments(
    arguments: dict[str, Any],
) -> SemanticPlan | None:
    """Convert the legacy zero-model routine grammar into the same semantic IR."""

    command = str(arguments.get("command") or "").strip()
    operation_map: dict[str, ControlOperation] = {
        "on": "turn_on",
        "off": "turn_off",
        "toggle": "toggle",
        "set_level": "set_level",
    }
    operation = operation_map.get(command)
    if operation is None:
        return None

    room = str(arguments.get("room") or "").strip()
    names = arguments.get("device_names")
    target: SemanticTarget | None = None
    if room:
        target = SemanticTarget(
            scope="room",
            name=room,
            kind=str(arguments.get("device_kind") or "auto"),
        )
    elif isinstance(names, list) and len(names) == 1 and str(names[0]).strip():
        target = SemanticTarget(
            scope="device",
            name=str(names[0]).strip(),
            kind=str(arguments.get("device_kind") or "auto"),
        )
    if target is None:
        return None

    action = SemanticAction(
        operation=operation,
        value=(int(arguments["level"]) if operation == "set_level" else None),
    )
    return SemanticPlan(
        domain="device_control",
        timing="now",
        target=target,
        action=action,
        confidence="high",
        source="fastpath",
    )


__all__ = [
    "SemanticAction",
    "SemanticPlan",
    "SemanticTarget",
    "semantic_plan_from_control_arguments",
    "semantic_plan_from_model_text",
]
