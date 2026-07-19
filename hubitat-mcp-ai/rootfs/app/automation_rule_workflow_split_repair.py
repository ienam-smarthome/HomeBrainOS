from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import time
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _normalise, _result_mapping, _session_id
from automation_rule_workflow_native_rm import (
    _NATIVE_PAUSE_NAMES,
    _positive_int,
)
from automation_rule_workflow_write_safe import (
    WriteSafeBackupWashingRuleMachineWorkflow,
)
from mcp_client import MCPToolResult
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_SET_RULE_NAMES = {"hub_set_rule", "set_rule"}
_RULE_READ_GATEWAYS = (
    "hub_read_rules",
    "hub_manage_rule_machine",
    "hub_manage_native_rules_and_apps",
)
_REPAIR_RE = re.compile(
    r"^repair(?:\s+(?:this|newest|existing|paused))?\s+rule(?:\s+(\d+))?$",
    flags=re.IGNORECASE,
)


def _clean_rule_label(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\(\s*paused\s*\)\s*$", "", text, flags=re.IGNORECASE)
    return " ".join(text.split()).strip()


def _timeout_result(result: MCPToolResult) -> bool:
    if not result.is_error:
        return False
    mapping = _result_mapping(result.data)
    text = " ".join(
        str(value or "")
        for value in (
            result.text,
            mapping.get("error"),
            mapping.get("exceptionType"),
            mapping.get("exception_type"),
        )
    ).lower()
    return "readtimeout" in text or "timeout" in text or "timed out" in text


def _failed(result: MCPToolResult) -> bool:
    mapping = _result_mapping(result.data)
    return bool(
        result.is_error
        or mapping.get("success") is False
        or mapping.get("partial") is True
        or mapping.get("partialTriggers")
        or mapping.get("partialActions")
        or mapping.get("subscriptionsNotLive") is True
        or mapping.get("actionsNotLive") is True
    )


def _digest_plan(plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _population_signature(plan: dict[str, Any]) -> str:
    return _digest_plan(
        {
            "triggers": list(plan.get("triggers") or []),
            "actions": list(plan.get("actions") or []),
        }
    )


def _merge_results(
    name: str,
    arguments: dict[str, Any],
    *,
    phase: str,
    results: list[MCPToolResult],
) -> MCPToolResult:
    failed = next((item for item in results if _failed(item)), None)
    data = {
        "success": failed is None,
        "partial": failed is not None,
        "splitPopulation": True,
        "phase": phase,
        "steps": [
            {
                "name": item.name,
                "is_error": item.is_error,
                "data": item.data,
                "text": item.text,
            }
            for item in results
        ],
    }
    if failed is not None:
        mapping = _result_mapping(failed.data)
        data["error"] = failed.text or str(mapping.get("error") or f"{phase} failed")
    return MCPToolResult(
        name=name,
        arguments=dict(arguments),
        raw={"isError": failed is not None, "homebrain": data},
        text=str(data.get("error") or ""),
        data=data,
        is_error=failed is not None,
    )


class SplitRepairWashingRuleMachineWorkflow(
    WriteSafeBackupWashingRuleMachineWorkflow
):
    """Use short retry-safe RM writes and repair a known paused partial rule."""

    async def _idempotent_write(
        self,
        tool: Any,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        result = await super()._call_rule_tool(tool, arguments)
        can_replay = bool(arguments.get("opToken")) or str(
            getattr(tool, "name", "") or ""
        ) in _NATIVE_PAUSE_NAMES
        if not (_timeout_result(result) and can_replay):
            return result

        await asyncio.sleep(2.0)
        replay = await super()._call_rule_tool(tool, arguments)
        if isinstance(replay.raw, dict):
            replay.raw.setdefault(
                "homebrain_timeout_replay",
                {
                    "attempted": True,
                    "same_op_token": bool(arguments.get("opToken")),
                    "first_error": result.text or _result_mapping(result.data).get("error"),
                },
            )
        return replay

    async def _call_rule_tool(self, tool: Any, arguments: dict[str, Any]):
        name = str(getattr(tool, "name", "") or "")
        if name not in _SET_RULE_NAMES:
            return await self._idempotent_write(tool, arguments)

        triggers = arguments.get("addTriggers")
        actions = arguments.get("addActions")
        if not (isinstance(triggers, list) and isinstance(actions, list)):
            return await self._idempotent_write(tool, arguments)

        common = {
            key: value
            for key, value in arguments.items()
            if key not in {"addTriggers", "addActions", "opToken"}
        }
        app_id = _positive_int(arguments.get("appId")) or 0
        signature = _digest_plan({"triggers": triggers, "actions": actions})
        root_token = f"homebrain-rule-{app_id}-{signature}"
        results: list[MCPToolResult] = []

        trigger_args = {
            **common,
            "addTriggers": list(triggers),
            "opToken": root_token + "-triggers",
        }
        trigger_result = await self._idempotent_write(tool, trigger_args)
        results.append(trigger_result)
        if _failed(trigger_result):
            return _merge_results(
                name,
                arguments,
                phase="triggers",
                results=results,
            )

        for index, action in enumerate(actions, start=1):
            action_args = {
                **common,
                "addAction": dict(action),
                "opToken": root_token + f"-create-action-{index}",
            }
            action_result = await self._idempotent_write(tool, action_args)
            results.append(action_result)
            if _failed(action_result):
                return _merge_results(
                    name,
                    arguments,
                    phase=f"action-{index}",
                    results=results,
                )

        return _merge_results(
            name,
            arguments,
            phase="complete",
            results=results,
        )

    async def _call_hidden_read(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[MCPToolResult | None, dict[str, Any]]:
        details: dict[str, Any] = {"tool": tool_name, "arguments": dict(arguments)}
        try:
            visible = {
                str(getattr(item, "name", "") or "")
                for item in await self.client.list_tools(refresh=True)
            }
        except Exception as exc:
            details["error"] = f"{type(exc).__name__}: {str(exc).strip()}"
            return None, details

        requests: list[tuple[str, dict[str, Any]]] = []
        if tool_name in visible:
            requests.append((tool_name, dict(arguments)))
        for gateway in _RULE_READ_GATEWAYS:
            if gateway in visible:
                requests.append(
                    (gateway, {"tool": tool_name, "args": dict(arguments)})
                )

        errors: list[str] = []
        for request_name, request_args in requests:
            try:
                result = await self.client.call_tool(request_name, request_args)
            except Exception as exc:
                errors.append(f"{request_name}: {type(exc).__name__}: {str(exc).strip()}")
                continue
            if result.is_error:
                errors.append(f"{request_name}: {result.text or 'tool error'}")
                continue
            details["request_tool"] = request_name
            details["gateway"] = request_name if request_name != tool_name else None
            return result, details

        details["error"] = "; ".join(errors) or f"{tool_name} was not advertised"
        return None, details

    async def _matching_rules(self, name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        result, details = await self._call_hidden_read("hub_list_rules", {})
        if result is None:
            return [], details

        target = _normalise(_clean_rule_label(name))
        matches: list[dict[str, Any]] = []
        for item in self._rule_rows(result.data):
            raw_name = item.get("label") or item.get("name")
            clean_name = _clean_rule_label(raw_name)
            if _normalise(clean_name) != target:
                continue
            row = dict(item)
            row["name"] = clean_name
            row["raw_name"] = str(raw_name or "")
            row["paused"] = bool(
                row.get("paused") is True
                or "paused" in str(raw_name or "").lower()
                or _normalise(row.get("status")) in {"paused", "disabled", "inactive"}
            )
            matches.append(row)

        matches.sort(
            key=lambda item: _positive_int(item.get("id")) or 0,
            reverse=True,
        )
        details["matches"] = matches
        details["match_count"] = len(matches)
        return matches, details

    async def _existing_rule(self, name: str) -> dict[str, Any] | None:
        matches, _ = await self._matching_rules(name)
        return matches[0] if matches else None

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        is_washing = str((pending.draft or {}).get("type") or "") == "washing-complete"
        if not is_washing or pending.draft is None:
            return await super()._create(pending)

        matches, discovery = await self._matching_rules(str(pending.draft.get("name") or ""))
        if not matches:
            return await super()._create(pending)

        newest = matches[0]
        newest_id = _positive_int(newest.get("id"))
        display = display_payload(
            "automation-rule-existing",
            str(pending.draft.get("name") or "Washing machine rule"),
            subtitle="Existing Rule Machine rule found",
            metrics=[
                {"label": "Matching rules", "value": str(len(matches)), "icon": "🧩"},
                {"label": "Newest rule ID", "value": str(newest_id or "—"), "icon": "🆔"},
                {"label": "New shell", "value": "Not created", "icon": "🛡️"},
            ],
            note=(
                "HomeBrain will not create another rule with this name. Repair the newest "
                "paused match, then review it in Rule Machine. Older duplicates remain paused "
                "and must be removed manually after the repaired rule is confirmed."
            ),
        )
        display["actions"] = [
            {
                "label": f"Repair rule {newest_id}",
                "query": f"Repair rule {newest_id}",
                "tone": "danger",
                "icon": "🛠️",
            },
            {"label": "Cancel", "query": "Cancel rule draft", "tone": "secondary", "icon": "✖️"},
        ]
        return {
            "success": False,
            "route": "mcp-native-rule-existing",
            "intent": "automation-rule-existing",
            "message": (
                f"Found {len(matches)} Rule Machine rule(s) named "
                f"**{pending.draft.get('name')}**. No new shell was created. "
                f"Use **Repair rule {newest_id}** to complete the newest paused one safely."
            ),
            "answered_by": "HomeBrain duplicate guard",
            "display": display,
            "technical": safe_debug(discovery),
        }

    async def _local_variables(self, app_id: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        result, details = await self._call_hidden_read(
            "hub_list_rule_local_variables",
            {"appId": app_id},
        )
        if result is None:
            return [], details

        variables: list[dict[str, Any]] = []

        def walk(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    walk(item)
                return
            if not isinstance(value, dict):
                return
            name = value.get("name")
            if name and any(key in value for key in ("type", "value")):
                variables.append(dict(value))
            for key, item in value.items():
                if key not in {"name", "type", "value"}:
                    walk(item)

        walk(result.data)
        details["variables"] = variables
        return variables, details

    async def _repair_rule(self, pending: PendingRule, requested_id: int | None) -> dict[str, Any]:
        if pending.draft is None or str(pending.draft.get("type") or "") != "washing-complete":
            return self._wrong_stage("Generate and build the washing-machine rule first.")
        if pending.create_tool is None or not self._is_native_set_rule(pending.create_tool):
            return self._wrong_stage("A compatible native hub_set_rule tool is not available.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")

        matches, discovery = await self._matching_rules(str(pending.draft.get("name") or ""))
        selected = next(
            (
                item
                for item in matches
                if requested_id is not None and _positive_int(item.get("id")) == requested_id
            ),
            matches[0] if requested_id is None and matches else None,
        )
        if selected is None:
            return self._wrong_stage(
                "The requested rule ID is not an exact-name match. Build again and use the Repair button shown by HomeBrain."
            )
        if selected.get("paused") is not True:
            return self._wrong_stage(
                "HomeBrain could not verify that the selected existing rule is paused. Pause it in Rule Machine, refresh MCP tools, then build again."
            )

        rule_id = _positive_int(selected.get("id"))
        if rule_id is None:
            return self._wrong_stage("The selected Rule Machine ID is invalid.")

        plan = pending.draft.get("native_rule_machine_plan") or {}
        pending.created_rule = {
            "id": str(rule_id),
            "name": str(pending.draft.get("name") or "Washing machine rule"),
            "status": "Paused",
            "native_rule_machine": True,
        }
        pending.stage = "created-paused"
        pending.expires_at = time.time() + self.store.ttl_seconds

        started = time.perf_counter()
        key = await self._read_best_practice_key()
        backup_ok, backup = await self._ensure_backup(key)
        if not backup_ok:
            return self._wrong_stage(
                "Repair was blocked because HomeBrain could not verify a recent hub backup."
            )

        pause_tool = await self._find_tool(_NATIVE_PAUSE_NAMES, refresh=True)
        if pause_tool is None:
            return self._wrong_stage("hub_set_rule_paused is not available through MCP.")
        pause_args = {
            self._argument_name(pause_tool, "ruleid", "ruleId"): rule_id,
            self._argument_name(pause_tool, "paused", "paused"): True,
        }
        pause_args = self._add_best_practice_key(pause_tool, pause_args, key)
        paused = await self._idempotent_write(pause_tool, pause_args)
        if _failed(paused):
            return self._tool_error("repair", paused.text or "Could not keep the existing rule paused")

        variables, variable_read = await self._local_variables(rule_id)
        local_results: list[dict[str, Any]] = []
        if not any(str(item.get("name") or "") == "cycleArmed" for item in variables):
            local_spec = list(plan.get("local_variables") or [])
            if not local_spec:
                return self._wrong_stage("The repair plan has no cycleArmed local variable definition.")
            local_args = {
                "appId": rule_id,
                "addLocalVariable": dict(local_spec[0]),
                "confirm": True,
                "opToken": f"homebrain-repair-{rule_id}-local",
            }
            local_args = self._add_best_practice_key(pending.create_tool, local_args, key)
            local_result = await self._idempotent_write(pending.create_tool, local_args)
            local_results.append(_result_mapping(local_result.data))
            if _failed(local_result):
                return self._native_partial_failure(
                    pending,
                    "The existing rule remains paused, but cycleArmed could not be verified.",
                    backup,
                    {"variable_read": variable_read, "local": local_results},
                )

        signature = _population_signature(plan)
        trigger_args = {
            "appId": rule_id,
            "addTriggers": list(plan.get("triggers") or []),
            "confirm": True,
            "opToken": f"homebrain-rule-{rule_id}-{signature}-triggers",
        }
        trigger_args = self._add_best_practice_key(pending.create_tool, trigger_args, key)
        trigger_result = await self._idempotent_write(pending.create_tool, trigger_args)
        if _failed(trigger_result):
            return self._native_partial_failure(
                pending,
                "The existing rule remains paused, but its two trigger events were not fully written.",
                backup,
                {"triggers": trigger_result.data},
            )

        clear_args = {
            "appId": rule_id,
            "clearActions": True,
            "confirm": True,
            "opToken": f"homebrain-repair-{rule_id}-{signature}-clear-actions",
        }
        clear_args = self._add_best_practice_key(pending.create_tool, clear_args, key)
        clear_result = await self._idempotent_write(pending.create_tool, clear_args)
        action_results: list[dict[str, Any]] = [_result_mapping(clear_result.data)]
        if _failed(clear_result):
            return self._native_partial_failure(
                pending,
                "The existing rule remains paused, but HomeBrain could not reset its action list safely.",
                backup,
                {"clear_actions": clear_result.data},
            )

        for index, action in enumerate(plan.get("actions") or [], start=1):
            action_args = {
                "appId": rule_id,
                "addAction": dict(action),
                "confirm": True,
                "opToken": f"homebrain-repair-{rule_id}-{signature}-action-{index}",
            }
            action_args = self._add_best_practice_key(pending.create_tool, action_args, key)
            action_result = await self._idempotent_write(pending.create_tool, action_args)
            action_results.append(_result_mapping(action_result.data))
            if _failed(action_result):
                return self._native_partial_failure(
                    pending,
                    f"The existing rule remains paused, but action {index} was not fully written.",
                    backup,
                    {
                        "triggers": trigger_result.data,
                        "actions": action_results,
                    },
                )

        final_pause = await self._idempotent_write(pause_tool, pause_args)
        if _failed(final_pause):
            return self._tool_error("repair", final_pause.text or "The repaired rule could not be re-paused")

        health_result, health_request = await self._call_hidden_read(
            "hub_get_rule_health",
            {"appId": rule_id, "source": "auto"},
        )
        health = health_result.data if health_result is not None else health_request
        health_map = _result_mapping(health)
        if (
            health_result is not None
            and health_map.get("ok") is False
            and health_map.get("unreadable") is not True
        ):
            return self._native_partial_failure(
                pending,
                "The repaired rule remains paused because Hubitat's post-write health check found an issue.",
                backup,
                {
                    "triggers": trigger_result.data,
                    "actions": action_results,
                    "health": health,
                },
            )

        pending.created_rule.update(
            {
                "trigger_count": len(plan.get("triggers") or []),
                "action_count": len(plan.get("actions") or []),
                "local_variable_count": len(plan.get("local_variables") or []),
            }
        )
        display = self._created_display(pending, operation="Repaired")
        display["note"] = (
            "The selected existing rule was repaired in short idempotent steps and remains paused. "
            "Confirm both trigger events in Hubitat before enabling it. Older same-name duplicates "
            "were not changed or deleted."
        )
        return {
            "success": True,
            "route": "mcp-native-washing-rule-repaired",
            "intent": "automation-rule-repaired",
            "message": (
                f"Repaired **{pending.created_rule['name']}** (Rule ID {rule_id}) and left it paused. "
                "The two power triggers and guarded notification actions were written separately."
            ),
            "answered_by": "Hubitat MCP native Rule Machine repair",
            "display": display,
            "created_rule": pending.created_rule,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "rule_discovery": discovery,
                    "selected_rule_id": rule_id,
                    "backup": backup,
                    "variable_read": variable_read,
                    "local_variables": local_results,
                    "triggers": trigger_result.data,
                    "actions": action_results,
                    "health": health,
                    "duplicate_rule_ids_left_paused": [
                        _positive_int(item.get("id"))
                        for item in matches[1:]
                        if _positive_int(item.get("id")) is not None
                    ],
                }
            ),
        }

    async def repair(self, request: Any, requested_id: int | None) -> dict[str, Any]:
        pending = await self.store.get(_session_id(request))
        if pending is None:
            return self._missing()
        return await self._repair_rule(pending, requested_id)

    def _native_partial_failure(
        self,
        pending: PendingRule,
        message: str,
        backup: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        answer = super()._native_partial_failure(pending, message, backup, result)
        rule_id = _positive_int((pending.created_rule or {}).get("id"))
        display = answer.get("display")
        if isinstance(display, dict) and rule_id is not None:
            display["actions"] = [
                {
                    "label": f"Repair rule {rule_id}",
                    "query": f"Repair rule {rule_id}",
                    "tone": "danger",
                    "icon": "🛠️",
                }
            ]
            display["note"] = (
                "The rule remains paused. Repair resumes the exact same rule ID with "
                "short idempotent trigger/action writes; it does not create another shell."
            )
        return answer


def install_split_repair_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> SplitRepairWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = SplitRepairWashingRuleMachineWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        repair_match = _REPAIR_RE.fullmatch(query)
        if repair_match:
            requested = _positive_int(repair_match.group(1)) if repair_match.group(1) else None
            answer = await service.repair(request, requested)
            answer.setdefault("version", application.VERSION)
            return answer

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
    "SplitRepairWashingRuleMachineWorkflow",
    "_clean_rule_label",
    "install_split_repair_rule_machine_workflow",
]
