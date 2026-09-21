from __future__ import annotations

from typing import Any

from request_classification import routine_control_arguments
from semantic_plan import (
    SemanticPlan,
    semantic_plan_from_control_arguments,
)
from semantic_planner import SemanticPlanner, is_semantic_control_candidate


class SemanticAgentCore:
    """Meaning-first front end for routine device control.

    Fast, unambiguous legacy grammar is translated into the same semantic IR
    without a provider call. Everything else that looks like a possible routine
    control request is interpreted by the model, then compiled into the existing
    deterministic DeviceControlService contract. No model-authored Hubitat wire
    payload crosses this boundary.
    """

    def __init__(
        self,
        planner: SemanticPlanner,
        *,
        default_brightness_step: int = 20,
    ) -> None:
        self.planner = planner
        self.default_brightness_step = max(
            1, min(100, int(default_brightness_step))
        )

    async def plan_control(
        self,
        prompt: str,
        *,
        history: Any = None,
        selected_device: str = "",
    ) -> SemanticPlan | None:
        fast_arguments = routine_control_arguments(prompt)
        if fast_arguments is not None:
            fast_plan = semantic_plan_from_control_arguments(fast_arguments)
            if fast_plan is not None:
                return fast_plan

        if not is_semantic_control_candidate(prompt):
            return None

        plan = await self.planner.plan(
            prompt,
            history=history,
            selected_device=selected_device,
        )
        if plan.domain != "device_control":
            return None
        return plan

    def _relative_delta(self, plan: SemanticPlan) -> int:
        action = plan.action
        if action is None or action.operation != "adjust_level":
            raise ValueError("plan is not a relative level adjustment")
        if action.delta is not None:
            return int(action.delta)

        step = self.default_brightness_step
        if action.magnitude == "small":
            step = max(1, round(step / 2))
        elif action.magnitude == "large":
            step = min(100, step * 2)

        return step if action.direction == "increase" else -step

    def compile_control(self, plan: SemanticPlan) -> dict[str, Any]:
        """Compile a safe semantic plan to the deterministic control adapter."""

        if not plan.executable_routine_control:
            raise ValueError("semantic plan is not an executable routine control")
        assert plan.target is not None
        assert plan.action is not None

        target = plan.target
        action = plan.action
        arguments: dict[str, Any] = {}

        if target.scope == "room":
            arguments["room"] = target.name
        else:
            arguments["device_names"] = [target.name]

        operation_map = {
            "turn_on": "on",
            "turn_off": "off",
            "toggle": "toggle",
            "set_level": "set_level",
            "adjust_level": "adjust_level",
        }
        arguments["command"] = operation_map[action.operation]

        if action.operation in {"set_level", "adjust_level"}:
            # Brightness semantics are intrinsically light-only even when the
            # planner had only enough language to emit kind=auto.
            arguments["device_kind"] = "light"
        else:
            arguments["device_kind"] = target.kind

        if action.operation == "set_level":
            arguments["level"] = int(action.value)
        elif action.operation == "adjust_level":
            arguments["delta"] = self._relative_delta(plan)

        return arguments


__all__ = ["SemanticAgentCore"]
