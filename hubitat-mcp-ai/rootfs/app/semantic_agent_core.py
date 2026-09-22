from __future__ import annotations

import json
import re
from typing import Any

from request_classification import routine_control_arguments
from request_metrics import increment_active_metric
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
        default_temperature_step: float = 1.0,
    ) -> None:
        self.planner = planner
        self.default_brightness_step = max(
            1, min(100, int(default_brightness_step))
        )
        self.default_temperature_step = max(
            0.1, min(10.0, float(default_temperature_step))
        )

    @staticmethod
    def _phrase_tokens(value: Any) -> list[str]:
        return re.findall(r"[a-z0-9]+", str(value or "").casefold())

    @classmethod
    def _explicit_entities(
        cls,
        prompt: str,
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return unique canonical entities explicitly named without overlap.

        Prefer the longest phrase when one canonical name is contained inside
        another (for example room "Hallway" versus device "Hallway Light 1").
        Duplicate canonical labels are deliberately excluded because a spoken
        label that maps to two real devices is not a safe explicit identity.
        """

        prompt_tokens = cls._phrase_tokens(prompt)
        if not prompt_tokens:
            return []

        token_counts: dict[tuple[str, ...], int] = {}
        prepared: list[tuple[dict[str, Any], tuple[str, ...]]] = []
        for entity in entities:
            tokens = tuple(cls._phrase_tokens(entity.get("name")))
            if not tokens:
                continue
            prepared.append((entity, tokens))
            token_counts[tokens] = token_counts.get(tokens, 0) + 1

        matches: list[tuple[int, int, int, dict[str, Any]]] = []
        for entity, tokens in prepared:
            if token_counts.get(tokens) != 1 or len(tokens) > len(prompt_tokens):
                continue
            width = len(tokens)
            for start in range(len(prompt_tokens) - width + 1):
                if tuple(prompt_tokens[start:start + width]) == tokens:
                    matches.append((start, start + width, width, entity))

        selected: list[tuple[int, int, dict[str, Any]]] = []
        occupied: set[int] = set()
        for start, end, width, entity in sorted(
            matches,
            key=lambda item: (-item[2], item[0], str(item[3].get("name") or "").casefold()),
        ):
            span = set(range(start, end))
            if occupied.intersection(span):
                continue
            selected.append((start, end, entity))
            occupied.update(span)

        selected.sort(key=lambda item: item[0])
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _start, _end, entity in selected:
            key = str(entity.get("name") or "").strip().casefold()
            if key and key not in seen:
                result.append(entity)
                seen.add(key)
        return result

    @staticmethod
    def _required_ability(plan: SemanticPlan) -> str:
        action = plan.action
        if action is None:
            return ""
        if action.operation in {"set_level", "adjust_level"}:
            return "brightness"
        if action.operation in {"set_temperature", "adjust_temperature"}:
            return "heating_setpoint"
        if action.operation in {"turn_on", "turn_off", "toggle"}:
            return "switch"
        return ""

    @classmethod
    def ground_plan_target(
        cls,
        prompt: str,
        plan: SemanticPlan,
        world_context: str | dict[str, Any],
    ) -> SemanticPlan:
        """Validate model entity choice against the capability world.

        A model may select a plausible device label when the user actually named
        a room. Example: "increase hallway brightness" was mapped to a controller
        called "Hallway dimmer" even though the real Hallway room contains the
        controllable lights. The host owns entity grounding: when exactly one real
        room is explicitly named, no full device label is explicitly named, and
        that room advertises the required ability, prefer room scope regardless
        of the model's guessed device label.
        """

        if (
            plan.target is None
            or plan.action is None
            or plan.needs_clarification
        ):
            return plan
        if isinstance(world_context, dict):
            world = world_context
        else:
            if not str(world_context or "").strip():
                return plan
            try:
                world = json.loads(str(world_context))
            except (TypeError, ValueError, json.JSONDecodeError):
                return plan
        if not isinstance(world, dict):
            return plan

        rooms = [
            item for item in (world.get("rooms") or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        devices = [
            item for item in (world.get("devices") or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        explicit_rooms = cls._explicit_entities(prompt, rooms)
        explicit_devices = cls._explicit_entities(prompt, devices)
        required_ability = cls._required_ability(plan)

        if len(explicit_devices) >= 2:
            compatible = [
                item
                for item in explicit_devices
                if (
                    not required_ability
                    or required_ability
                    in {str(value) for value in (item.get("abilities") or [])}
                )
            ]
            if len(compatible) == len(explicit_devices):
                grounded_target = plan.target.model_copy(
                    update={
                        "scope": "selection",
                        "name": "",
                        "names": [
                            str(item.get("name") or "").strip()
                            for item in explicit_devices
                        ],
                    }
                )
                increment_active_metric("semantic_target_grounded")
                return plan.model_copy(update={"target": grounded_target})

        if len(explicit_rooms) == 1 and not explicit_devices:
            room = explicit_rooms[0]
            room_abilities = {
                str(value) for value in (room.get("abilities") or [])
            }
            if not required_ability or required_ability in room_abilities:
                grounded_target = plan.target.model_copy(
                    update={
                        "scope": "room",
                        "name": str(room.get("name") or "").strip(),
                        "names": [],
                    }
                )
                increment_active_metric("semantic_target_grounded")
                return plan.model_copy(update={"target": grounded_target})

        # Canonicalize an explicitly named device rather than preserving model
        # spelling/casing. This does not invent a target; it only binds a full
        # user-mentioned label to the corresponding world entity.
        if len(explicit_devices) == 1:
            device = explicit_devices[0]
            abilities = {str(value) for value in (device.get("abilities") or [])}
            if not required_ability or required_ability in abilities:
                grounded_target = plan.target.model_copy(
                    update={
                        "scope": "device",
                        "name": str(device.get("name") or "").strip(),
                        "names": [],
                    }
                )
                increment_active_metric("semantic_target_grounded")
                return plan.model_copy(update={"target": grounded_target})

        return plan

    async def plan_control(
        self,
        prompt: str,
        *,
        history: Any = None,
        selected_device: str = "",
        world_context: str = "",
        grounding_world: dict[str, Any] | None = None,
    ) -> SemanticPlan | None:
        fast_arguments = routine_control_arguments(prompt)
        if fast_arguments is not None:
            fast_plan = semantic_plan_from_control_arguments(fast_arguments)
            if fast_plan is not None:
                grounding_context: str | dict[str, Any] = (
                    grounding_world
                    if grounding_world is not None
                    else world_context
                )
                if grounding_context:
                    return self.ground_plan_target(
                        prompt,
                        fast_plan,
                        grounding_context,
                    )
                return fast_plan

        if not is_semantic_control_candidate(prompt):
            return None

        plan = await self.planner.plan(
            prompt,
            history=history,
            selected_device=selected_device,
            world_context=world_context,
        )
        if plan.domain != "device_control":
            return None
        return self.ground_plan_target(
            prompt,
            plan,
            grounding_world if grounding_world is not None else world_context,
        )

    def _relative_delta(self, plan: SemanticPlan) -> float:
        action = plan.action
        if action is None or action.operation not in {
            "adjust_level",
            "adjust_temperature",
        }:
            raise ValueError("plan is not a relative adjustment")
        if action.delta is not None:
            return float(action.delta)

        if action.operation == "adjust_level":
            step: float = float(self.default_brightness_step)
            if action.magnitude == "small":
                step = max(1.0, round(step / 2))
            elif action.magnitude == "large":
                step = min(100.0, step * 2)
        else:
            step = float(self.default_temperature_step)
            if action.magnitude == "small":
                step = max(0.1, step / 2)
            elif action.magnitude == "large":
                step = min(10.0, step * 2)

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
        elif target.scope == "selection":
            arguments["device_names"] = list(target.names)
        else:
            arguments["device_names"] = [target.name]

        operation_map = {
            "turn_on": "on",
            "turn_off": "off",
            "toggle": "toggle",
            "set_level": "set_level",
            "adjust_level": "adjust_level",
            "set_temperature": "set_temperature",
            "adjust_temperature": "adjust_temperature",
        }
        arguments["command"] = operation_map[action.operation]

        if action.operation in {"set_level", "adjust_level"}:
            # Brightness semantics are intrinsically light-only even when the
            # planner had only enough language to emit kind=auto.
            arguments["device_kind"] = "light"
        elif action.operation in {"set_temperature", "adjust_temperature"}:
            arguments["device_kind"] = "thermostat"
        else:
            arguments["device_kind"] = target.kind

        if action.operation == "set_level":
            arguments["level"] = int(action.value)
        elif action.operation == "adjust_level":
            arguments["delta"] = int(round(self._relative_delta(plan)))
        elif action.operation == "set_temperature":
            arguments["setpoint"] = float(action.value)
        elif action.operation == "adjust_temperature":
            arguments["delta"] = float(self._relative_delta(plan))

        return arguments


__all__ = ["SemanticAgentCore"]
