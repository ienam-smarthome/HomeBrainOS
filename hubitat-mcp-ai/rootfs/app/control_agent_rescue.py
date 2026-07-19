from __future__ import annotations

import asyncio
from typing import Any

from control_agent import AskHandler, ControlPlan
from control_agent_intent import is_control_candidate
from control_agent_level_verified import FastVerifiedControlAgent
from presenter import safe_debug


class RescueControlAgent(FastVerifiedControlAgent):
    """Control Agent that retries one failed deterministic interpretation locally.

    The rescue model remains read-free and tool-free. It may only return a strict
    ``ControlIntent``. Python then resolves that intent against the capability-
    filtered selected-device graph and accepts it only when it improves the plan.
    """

    async def answer(self, request: Any, original_ask: AskHandler) -> dict[str, Any]:
        session_id = self.contexts.session_id(request)
        query = str(getattr(request, "query", "") or "").strip()

        pending = await self.pending.get(session_id)
        if pending is not None:
            handled = await self._handle_pending(request, pending)
            if handled is not None:
                return handled
            if is_control_candidate(query):
                await self.pending.clear(session_id)

        graph = await self._graph()
        alias_answer = await self._handle_alias_command(query, graph)
        if alias_answer is not None:
            return alias_answer

        if not is_control_candidate(query):
            return await original_ask(request)

        context = await self.contexts.get(session_id)
        history = [
            {
                "role": str(
                    getattr(item, "role", "")
                    or (item.get("role") if isinstance(item, dict) else "")
                ),
                "content": str(
                    getattr(item, "content", "")
                    or (item.get("content") if isinstance(item, dict) else "")
                ),
            }
            for item in list(getattr(request, "history", None) or [])[-4:]
        ]
        intent, diagnostics = await self.interpreter.interpret(
            query,
            history=history,
            context=context.public_dict(),
            inventory=graph.inventory_summary(),
        )
        if intent is None:
            return await original_ask(request)

        plan = self._resolve_plan(
            query,
            intent,
            diagnostics,
            graph,
            context.graph_context(),
        )
        rescue: dict[str, Any] | None = None
        unresolved = [item for item in plan.actions if not item.nodes]
        if unresolved and not intent.model:
            plan, rescue = await self._attempt_ai_rescue(
                query=query,
                history=history,
                context=context.public_dict(),
                graph=graph,
                graph_context=context.graph_context(),
                original_plan=plan,
            )
            unresolved = [item for item in plan.actions if not item.nodes]

        if unresolved:
            answer = await self._clarify_unresolved(session_id, plan, unresolved)
            return self._decorate_rescue(answer, rescue)

        policy = self._policy(plan)
        if policy["decision"] == "block":
            return self._decorate_rescue(self._blocked_response(plan, policy), rescue)
        if policy["decision"] == "confirm":
            await self.pending.put(session_id, kind="confirm-plan", plan=plan)
            return self._decorate_rescue(self._confirmation_response(plan, policy), rescue)
        answer = await self._execute_plan(session_id, plan, confirmed=False)
        return self._decorate_rescue(answer, rescue)

    async def _attempt_ai_rescue(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        graph: Any,
        graph_context: Any,
        original_plan: ControlPlan,
    ) -> tuple[ControlPlan, dict[str, Any]]:
        details: dict[str, Any] = {
            "attempted": False,
            "accepted": False,
            "reason": "AI rescue is disabled.",
            "original_intent": original_plan.intent.response_dict(),
            "original_plan_quality": self._plan_quality(original_plan),
        }
        if not self.application.option_bool("control_agent_ai_rescue_enabled", True):
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details
        if not self.application.option_bool("ollama_enabled", True):
            details["reason"] = "Local Ollama is disabled."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        rescue_context = dict(context)
        rescue_context["control_rescue"] = {
            "mode": "reinterpret_failed_deterministic_plan",
            "failed_intent": original_plan.intent.response_dict(),
            "failed_resolutions": [item.public_dict() for item in original_plan.actions],
            "instruction": (
                "Reinterpret the original user wording. Remove leftover command syntax from "
                "device names and express room, type, ordinal, level and references in their "
                "dedicated schema fields. Do not invent a device ID."
            ),
        }
        details["attempted"] = True

        try:
            rescued_intent, ai_details = await self.interpreter._interpret_with_ai(
                query,
                history=history,
                context=rescue_context,
                inventory=graph.inventory_summary(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            details["reason"] = str(exc).strip() or type(exc).__name__
            details["ai_error"] = details["reason"]
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        details["ai"] = dict(ai_details)
        if rescued_intent is None:
            details["reason"] = "The local model did not return a supported control intent."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details
        if rescued_intent.response_dict() == original_plan.intent.response_dict():
            details["reason"] = "The local model repeated the failed deterministic intent."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        rescued_plan = self._resolve_plan(
            query,
            rescued_intent,
            {**dict(ai_details), "rescue_mode": True},
            graph,
            graph_context,
        )
        original_quality = self._plan_quality(original_plan)
        rescued_quality = self._plan_quality(rescued_plan)
        details["rescued_intent"] = rescued_intent.response_dict()
        details["rescued_plan_quality"] = rescued_quality

        if not self._is_better_plan(original_quality, rescued_quality):
            details["reason"] = "The rescued interpretation did not improve safe device resolution."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        details["accepted"] = True
        details["reason"] = "Local AI produced a safer, better-resolved structured plan."
        rescued_plan.diagnostics["ai_rescue"] = details
        return rescued_plan, details

    @staticmethod
    def _plan_quality(plan: ControlPlan) -> dict[str, int]:
        unresolved = sum(1 for item in plan.actions if not item.nodes)
        resolved_actions = len(plan.actions) - unresolved
        resolved_devices = len(plan.nodes)
        candidates = sum(len(item.candidates) for item in plan.actions if not item.nodes)
        return {
            "unresolved_actions": unresolved,
            "resolved_actions": resolved_actions,
            "resolved_devices": resolved_devices,
            "unresolved_candidates": candidates,
        }

    @staticmethod
    def _is_better_plan(original: dict[str, int], rescued: dict[str, int]) -> bool:
        if rescued["unresolved_actions"] < original["unresolved_actions"]:
            return rescued["resolved_devices"] > 0
        if rescued["unresolved_actions"] > original["unresolved_actions"]:
            return False
        if rescued["resolved_actions"] > original["resolved_actions"]:
            return True
        if (
            rescued["unresolved_actions"] > 0
            and rescued["unresolved_candidates"] > 0
            and (
                original["unresolved_candidates"] == 0
                or rescued["unresolved_candidates"] < original["unresolved_candidates"]
            )
        ):
            return True
        return False

    @staticmethod
    def _decorate_rescue(
        answer: dict[str, Any],
        rescue: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not rescue:
            return answer
        enriched = dict(answer)
        enriched["control_ai_rescue"] = rescue
        if rescue.get("accepted"):
            enriched["control_rescue_used"] = True
        existing = str(enriched.get("technical") or "").strip()
        rescue_debug = safe_debug({"control_ai_rescue": rescue})
        enriched["technical"] = (
            f"{existing}\n\nAI rescue\n{rescue_debug}" if existing else rescue_debug
        )
        return enriched


def install_control_agent(
    application: Any,
    device_index: Any,
    fallback: Any,
    **kwargs: Any,
) -> RescueControlAgent:
    original_ask: AskHandler = application.ask
    agent = RescueControlAgent(application, device_index, fallback, **kwargs)

    async def ask_with_control_agent(request: Any) -> dict[str, Any]:
        if not application.option_bool("control_agent_enabled", True):
            return await original_ask(request)
        return await agent.answer(request, original_ask)

    application.ask = ask_with_control_agent
    return agent


__all__ = ["RescueControlAgent", "install_control_agent"]
