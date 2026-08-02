"""Execute consumed confirmation groups and verify sensitive outcomes.

The confirmation store owns pending lifecycle and ConfirmationPolicy owns
approval decisions. This coordinator begins only after the host has consumed
a valid same-session confirmation. It revalidates queued Rule Machine
payloads, injects upstream approval, executes sequentially, fails closed after
an unverified rule write, and renders deterministic rule completion reports.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from confirmation_policy import ConfirmationPolicy
from confirmation_store import PendingConfirmation
from mcp_client import MCPTool
from request_metrics import add_active_metric_ms, increment_active_metric
from tool_discovery_catalog import ToolDiscoveryCatalog
from tool_executor import ToolExecution, ToolExecutor
from tool_registry import rule_machine_proposal_error


ChatCallback = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    Awaitable[dict[str, Any]],
]
MutationObserver = Callable[[], None]
Clock = Callable[[], float]


class ConfirmedActionCoordinator:
    """Resume one immutable, already-confirmed structured action group."""

    RULE_GATEWAY = "hub_manage_rule_machine"

    def __init__(
        self,
        confirmation_policy: ConfirmationPolicy,
        executor: ToolExecutor,
        chat: ChatCallback,
        mark_mutation: MutationObserver,
        *,
        clock: Clock = time.monotonic,
    ) -> None:
        self.confirmation_policy = confirmation_policy
        self.executor = executor
        self._chat = chat
        self._mark_mutation = mark_mutation
        self._clock = clock

    @staticmethod
    def rule_result_data(execution: ToolExecution | Any) -> dict[str, Any]:
        result = getattr(execution, "result", None)
        data = result.data if result is not None else None
        while isinstance(data, dict):
            if any(
                key in data
                for key in (
                    "success",
                    "appId",
                    "ruleId",
                    "error",
                    "partial",
                    "health",
                )
            ):
                break
            nested = next(
                (
                    data[key]
                    for key in ("result", "data", "output")
                    if isinstance(data.get(key), dict)
                ),
                None,
            )
            if nested is None:
                break
            data = nested
        return data if isinstance(data, dict) else {}

    @classmethod
    def verified_rule_execution(cls, execution: ToolExecution | Any) -> bool:
        data = cls.rule_result_data(execution)
        health = data.get("health") if isinstance(data.get("health"), dict) else {}
        return (
            bool(getattr(execution, "success", False))
            and data.get("success") is True
            and (data.get("appId") or data.get("ruleId")) not in {None, ""}
            and data.get("partial") is not True
            and health.get("ok") is True
        )

    def _record_rule_verification(self, execution: ToolExecution | Any) -> bool:
        started = self._clock()
        verified = self.verified_rule_execution(execution)
        add_active_metric_ms("verification", (self._clock() - started) * 1000)
        if not verified:
            increment_active_metric("mutation_verification_failures")
        return verified

    @staticmethod
    def queued_rule_name(arguments: dict[str, Any]) -> str:
        payload = arguments.get("args")
        if not isinstance(payload, dict):
            return "Rule Machine rule"
        envelope = payload.get("args")
        source = envelope if isinstance(envelope, dict) else payload
        return str(source.get("name") or "Rule Machine rule")

    @classmethod
    def confirmed_rule_report(
        cls,
        outcomes: list[tuple[str, dict[str, Any], ToolExecution | Any]],
        *,
        queued_count: int,
    ) -> str | None:
        if not outcomes or any(
            name != cls.RULE_GATEWAY for name, _, _ in outcomes
        ):
            return None
        lines: list[str] = []
        failed = False
        for _, arguments, execution in outcomes:
            name = cls.queued_rule_name(arguments)
            data = cls.rule_result_data(execution)
            app_id = data.get("appId") or data.get("ruleId")
            if cls.verified_rule_execution(execution):
                lines.append(
                    f"- Created **{name}** (appId: {app_id}) and the hub "
                    "reported it healthy."
                )
                continue
            failed = True
            error = getattr(execution, "error", None)
            detail = (
                data.get("error")
                or data.get("note")
                or (
                    str(error)
                    if error is not None
                    else "the hub did not return a verified rule ID and healthy result"
                )
            )
            lines.append(f"- **{name} was not verified:** {detail}.")
        skipped = max(0, queued_count - len(outcomes))
        if skipped:
            failed = True
            lines.append(
                f"- {skipped} remaining confirmed action"
                f"{' was' if skipped == 1 else 's were'} not attempted after "
                "the first unverified write."
            )
        heading = (
            "The confirmed Rule Machine write was not fully completed."
            if failed
            else "Confirmed Rule Machine actions completed:"
        )
        return heading + "\n\n" + "\n".join(lines)

    async def resume(
        self,
        pending: PendingConfirmation,
        catalog: ToolDiscoveryCatalog,
    ) -> str:
        messages = [*pending.messages, pending.assistant_message]
        outcomes: list[tuple[str, dict[str, Any], ToolExecution]] = []
        for tool_name, arguments in pending.actions:
            self._mark_mutation()
            proposal_error = rule_machine_proposal_error(tool_name, arguments)
            if proposal_error is not None:
                return (
                    "The queued Rule Machine action was cancelled because its "
                    f"payload is incomplete. {proposal_error}"
                )
            tool = catalog.available_tool(tool_name)
            approved_arguments = self.confirmation_policy.approved_arguments(
                tool_name,
                arguments,
                tool_schema=tool.input_schema if tool is not None else None,
            )
            execution = await self.executor.execute(
                tool_name,
                approved_arguments,
                tool=tool or MCPTool(tool_name, tool_name, {}),
                mutates=True,
            )
            outcomes.append((tool_name, approved_arguments, execution))
            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": execution.content,
            })
            if tool_name == self.RULE_GATEWAY:
                verified = self._record_rule_verification(execution)
                if not verified:
                    break
        deterministic_report = self.confirmed_rule_report(
            outcomes,
            queued_count=len(pending.actions),
        )
        if deterministic_report is not None:
            return deterministic_report
        response = await self._chat(messages, catalog.schemas())
        return str(response.get("content") or "Confirmed command completed.")


__all__ = ["ConfirmedActionCoordinator"]
