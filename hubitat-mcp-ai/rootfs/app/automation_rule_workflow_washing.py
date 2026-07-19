from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _first, _result_mapping, _session_id
from automation_rule_workflow_native_rm import (
    _NATIVE_PAUSE_NAMES,
    _nested_value,
    _positive_int,
)
from automation_rule_workflow_notification_safe import (
    NotificationSafeNativeRuleMachineWorkflow,
)
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_WASHING_TYPE = "washing-complete"
_CYCLE_LOCAL = "cycleArmed"


def _washing_rule_plan(
    draft: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if str(draft.get("type") or "") != _WASHING_TYPE:
        return None, "Not a washing-machine completion draft."

    unresolved = [str(item) for item in (draft.get("unresolved") or []) if str(item)]
    if unresolved:
        return None, " ".join(unresolved)

    power_device = draft.get("washing_power_device")
    if not isinstance(power_device, dict):
        power_device = next(
            (
                item
                for item in (draft.get("devices") or [])
                if isinstance(item, dict)
                and "power" in (item.get("attributes") or {})
            ),
            None,
        )
    notifiers = list(draft.get("notification_candidates") or [])
    notifier = notifiers[0] if len(notifiers) == 1 else None

    power_id = _positive_int((power_device or {}).get("id"))
    notifier_id = _positive_int((notifier or {}).get("id"))
    if power_id is None:
        return None, "The washing-machine power meter could not be resolved to one positive Hubitat device ID."
    if notifier_id is None:
        return None, "Exactly one selected Notification-capable device is required."

    power_label = str((power_device or {}).get("label") or "Washing machine")
    running_condition = {
        "capability": "Power meter",
        "deviceIds": [power_id],
        "comparator": ">",
        "value": 10,
    }
    finished_conditions = [
        {
            "capability": "Power meter",
            "deviceIds": [power_id],
            "comparator": "<",
            "value": 5,
        },
        {
            "capability": "Variable",
            "variable": _CYCLE_LOCAL,
            "comparator": "=",
            "value": 1,
        },
    ]

    return {
        "local_variables": [
            {"name": _CYCLE_LOCAL, "type": "Number", "value": 0}
        ],
        "triggers": [
            {
                "capability": "Power meter",
                "deviceIds": [power_id],
                "comparator": ">",
                "value": 10,
            },
            {
                "capability": "Power meter",
                "deviceIds": [power_id],
                "comparator": "<",
                "value": 5,
                "andStays": {"seconds": 180},
            },
        ],
        "actions": [
            {
                "capability": "ifThen",
                "expression": {
                    "conditions": [running_condition],
                    "operator": "AND",
                },
            },
            {
                "capability": "setLocalVariable",
                "variable": _CYCLE_LOCAL,
                "value": 1,
            },
            {
                "capability": "elseIf",
                "expression": {
                    "conditions": finished_conditions,
                    "operator": "AND",
                },
            },
            {
                "capability": "notification",
                "deviceIds": [notifier_id],
                "message": f"{power_label} has finished its cycle.",
            },
            {
                "capability": "setLocalVariable",
                "variable": _CYCLE_LOCAL,
                "value": 0,
            },
            {"capability": "endIf"},
        ],
        "power_device_id": power_id,
        "notification_device_id": notifier_id,
        "running_threshold_w": 10,
        "finished_threshold_w": 5,
        "finished_stable_seconds": 180,
    }, None


class WashingRuleMachineWorkflow(NotificationSafeNativeRuleMachineWorkflow):
    """Adds guarded native Rule Machine compilation for washing completion."""

    def _choose_create_tool(self, tools, draft):
        if str(draft.get("type") or "") != _WASHING_TYPE:
            return super()._choose_create_tool(tools, draft)

        plan, plan_error = _washing_rule_plan(draft)
        native = [tool for tool in tools.values() if self._is_native_set_rule(tool)]
        native.sort(key=lambda tool: (0 if tool.name == "hub_set_rule" else 1, tool.name))
        if native and plan is not None:
            token = "homebrain-" + uuid.uuid4().hex[:20]
            draft["native_rule_machine_plan"] = plan
            draft["native_rule_machine_op_token"] = token
            return native[0], {"name": draft["name"], "confirm": True, "opToken": token}, None
        if native and plan_error:
            return None, None, plan_error
        return super()._choose_create_tool(tools, draft)

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        is_washing = str((pending.draft or {}).get("type") or "") == _WASHING_TYPE
        if not is_washing or pending.create_tool is None or not self._is_native_set_rule(pending.create_tool):
            return await super()._create(pending)
        if pending.stage != "draft" or pending.draft is None:
            return self._wrong_stage("Build this rule first, then review the draft before creating it.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")
        if pending.create_args is None:
            return self._wrong_stage("The washing-machine Rule Machine draft did not compile safely.")

        existing = await self._existing_rule(pending.draft["name"])
        if existing is not None:
            pending.created_rule = existing
            pending.stage = "created"
            return self._duplicate(existing)

        plan = pending.draft.get("native_rule_machine_plan") or {}
        started = time.perf_counter()
        key = await self._read_best_practice_key()
        backup_ok, backup = await self._ensure_backup(key)
        if not backup_ok:
            return {
                "success": False,
                "route": "mcp-rule-preflight-blocked",
                "intent": "automation-rule-backup-required",
                "message": (
                    "The rule was not created because HomeBrain could not verify or create the "
                    f"required recent hub backup. {backup.get('error') or ''}"
                ).strip(),
                "answered_by": "HomeBrain rule safety",
                "display": display_payload(
                    "automation-rule-preflight",
                    str(pending.draft.get("name") or "Automation rule"),
                    subtitle="Creation blocked safely",
                    metrics=[
                        {"label": "Backup", "value": "Required", "icon": "💾"},
                        {"label": "Rule written", "value": "No", "icon": "🛡️"},
                    ],
                    note="Keep Enable Write Tools on and make hub_create_backup available through MCP, then press Create again.",
                ),
                "technical": safe_debug({"backup": backup, "best_practice_key_found": bool(key)}),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }

        shell_args = self._add_best_practice_key(
            pending.create_tool,
            dict(pending.create_args),
            key,
        )
        shell = await self._call_rule_tool(pending.create_tool, shell_args)
        shell_data = _result_mapping(shell.data)
        if shell.is_error or shell_data.get("success") is False:
            return self._tool_error(
                "create",
                shell.text or str(shell_data.get("error") or "Hubitat rejected the Rule Machine shell"),
            )
        if str(shell_data.get("status") or "").lower() == "in_progress":
            return self._wrong_stage(
                "Hubitat is still creating the Rule Machine shell. Press Create this rule again; the same idempotency token will poll/replay rather than duplicate it."
            )

        rule_id = _positive_int(_first(shell_data, "ruleId", "appId", "id"))
        if rule_id is None:
            resolved = await self._existing_rule(pending.draft["name"])
            rule_id = _positive_int((resolved or {}).get("id"))
        if rule_id is None:
            return self._tool_error(
                "create",
                "Hubitat created or accepted the Rule Machine shell but did not return a verifiable rule ID. Review Rule Machine before retrying.",
            )

        created = {
            "id": str(rule_id),
            "name": pending.draft["name"],
            "status": "Empty shell",
            "tool": pending.create_tool.name,
            "native_rule_machine": True,
        }
        pending.created_rule = created
        pending.stage = "created"
        pending.expires_at = time.time() + self.store.ttl_seconds

        pause_tool = await self._find_tool(_NATIVE_PAUSE_NAMES, refresh=True)
        if pause_tool is None:
            created["warning"] = "The empty rule shell was created, but hub_set_rule_paused was not advertised. No variables, triggers or actions were added."
            return self._native_partial_failure(pending, created["warning"], backup, shell_data)
        pause_args = {
            self._argument_name(pause_tool, "ruleid", "ruleId"): rule_id,
            self._argument_name(pause_tool, "paused", "paused"): True,
        }
        pause_args = self._add_best_practice_key(pause_tool, pause_args, key)
        paused = await self._call_rule_tool(pause_tool, pause_args)
        if paused.is_error or _nested_value(paused.data, "success") is False:
            created["warning"] = "The empty rule shell was created, but HomeBrain could not verify it was paused. No variables, triggers or actions were added."
            return self._native_partial_failure(pending, created["warning"], backup, paused.data)

        created["status"] = "Paused"
        pending.stage = "created-paused"

        local_results: list[dict[str, Any]] = []
        for index, spec in enumerate(plan.get("local_variables") or [], start=1):
            local_args = {
                "appId": rule_id,
                "addLocalVariable": dict(spec),
                "confirm": True,
                "opToken": str(pending.draft.get("native_rule_machine_op_token") or "homebrain")
                + f"-local-{index}",
            }
            local_args = self._add_best_practice_key(pending.create_tool, local_args, key)
            local_result = await self._call_rule_tool(pending.create_tool, local_args)
            local_data = _result_mapping(local_result.data)
            local_results.append(local_data)
            if (
                local_result.is_error
                or local_data.get("success") is False
                or local_data.get("partial") is True
                or local_data.get("variableNotLive") is True
            ):
                created["warning"] = "The Rule Machine shell remains paused, but its cycle-arm variable was not written and verified. No triggers or actions were added."
                return self._native_partial_failure(
                    pending,
                    created["warning"]
                    + " "
                    + (local_result.text or str(local_data.get("error") or "")),
                    backup,
                    {"local_variables": local_results},
                )

        # A local-variable edit calls updateRule. Reassert pause before adding any
        # trigger/action rows so the partially-authored rule cannot subscribe live.
        re_paused = await self._call_rule_tool(pause_tool, pause_args)
        if re_paused.is_error or _nested_value(re_paused.data, "success") is False:
            created["warning"] = "The cycle-arm variable was added, but HomeBrain could not re-verify the rule was paused. No triggers or actions were added."
            return self._native_partial_failure(
                pending,
                created["warning"],
                backup,
                {"local_variables": local_results, "pause": re_paused.data},
            )

        populate_token = str(pending.draft.get("native_rule_machine_op_token") or "homebrain") + "-populate"
        populate_args = {
            "appId": rule_id,
            "addTriggers": list(plan.get("triggers") or []),
            "addActions": list(plan.get("actions") or []),
            "confirm": True,
            "opToken": populate_token,
        }
        populate_args = self._add_best_practice_key(pending.create_tool, populate_args, key)
        populated = await self._call_rule_tool(pending.create_tool, populate_args)
        populated_data = _result_mapping(populated.data)
        if populated.is_error or populated_data.get("success") is False:
            created["warning"] = "The Rule Machine shell remains paused, but its trigger/actions were not fully written."
            return self._native_partial_failure(
                pending,
                created["warning"] + " " + (populated.text or str(populated_data.get("error") or "")),
                backup,
                {"local_variables": local_results, "populate": populated_data},
            )
        if populated_data.get("partial") is True or populated_data.get("partialTriggers") or populated_data.get("partialActions"):
            created["warning"] = "Hubitat reported a partial washing-machine Rule Machine build. The rule remains paused for review."
            return self._native_partial_failure(
                pending,
                created["warning"],
                backup,
                {"local_variables": local_results, "populate": populated_data},
            )

        await self._call_rule_tool(pause_tool, pause_args)
        created.update(
            {
                "status": "Paused",
                "trigger_count": len(plan.get("triggers") or []),
                "action_count": len(plan.get("actions") or []),
                "local_variable_count": len(plan.get("local_variables") or []),
            }
        )
        pending.stage = "created-paused"
        return {
            "success": True,
            "route": "mcp-native-washing-rule-created",
            "intent": "automation-rule-created",
            "message": (
                f"Created **{created['name']}** as a native Rule Machine rule and left it paused. "
                "Review the two power thresholds, three-minute stability period and notification device in Hubitat Rule Machine, then press Enable rule when ready."
            ),
            "answered_by": "Hubitat MCP native Rule Machine",
            "display": self._created_display(pending),
            "created_rule": created,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "create_tool": pending.create_tool.name,
                    "create_gateway": pending.create_tool.gateway,
                    "rule_id": rule_id,
                    "backup": backup,
                    "best_practice_key_found": bool(key),
                    "shell": shell_data,
                    "local_variables": local_results,
                    "populate": populated_data,
                }
            ),
        }

    async def _call_operation(self, pending: PendingRule, operation: str) -> dict[str, Any]:
        if operation == "run" and str((pending.draft or {}).get("type") or "") == _WASHING_TYPE:
            return self._wrong_stage(
                "The native Rule Machine API does not expose a genuine non-executing dry-run. Review the paused rule, enable it, then validate it with a real washing cycle."
            )
        return await super()._call_operation(pending, operation)


def install_washing_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> WashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = WashingRuleMachineWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service


__all__ = [
    "WashingRuleMachineWorkflow",
    "_washing_rule_plan",
    "install_washing_rule_machine_workflow",
]
