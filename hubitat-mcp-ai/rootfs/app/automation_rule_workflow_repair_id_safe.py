from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from automation_rule_workflow import PendingRule, _first, _result_mapping, _session_id, _tool_rows
from automation_rule_workflow_native_rm import LiveRuleTool, NativeRuleMachineAutomationWorkflow, _NATIVE_PAUSE_NAMES, _nested_value, _positive_int
from device_intelligence_catalogue import _rows
from device_intelligence_index import _attributes, _device_id, _label, _normalise, _room_name
from presenter import display_payload, safe_debug
import asyncio
import json
from automation_rule_workflow import PendingRule, _session_id
from automation_rule_workflow_native_rm import _BACKUP_NAMES, _GUIDE_NAMES, _best_practice_key, _nested_value
from datetime import date, datetime
from automation_rule_workflow import _session_id
from mcp_client import MCPToolResult
import hashlib
import html
from automation_rule_workflow import PendingRule, _normalise, _result_mapping, _session_id
from automation_rule_workflow_native_rm import _NATIVE_PAUSE_NAMES, _positive_int
from contextvars import ContextVar
from automation_rule_workflow_native_rm import _positive_int


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


_NO_NOTIFICATION = "No selected Notification-capable device was found."


_MULTIPLE_NOTIFICATION = "More than one Notification-capable device is selected."


_NOTIFICATION_RULE_TYPES = {"cold-storage-door", "washing-complete"}


_GENERIC_COMPILE_ERRORS = (
    "Automatic rule compilation is not implemented yet for candidate type",
    "No valid MCP rule trigger was compiled.",
    "No valid MCP rule action was compiled.",
)


_BACKUP_MAX_AGE_MS = 24 * 60 * 60 * 1000


_WASHING_TYPE = "washing-complete"


_CYCLE_LOCAL = "cycleArmed"


def _candidate_label(item: dict[str, Any]) -> str:
    label = _label(item) or "Unnamed device"
    device_id = _device_id(item)
    room = _room_name(item)
    details: list[str] = []
    if device_id:
        details.append(f"ID {device_id}")
    if room:
        details.append(room)
    return f"{label} ({', '.join(details)})" if details else label


def _without_notification_errors(values: list[Any]) -> list[str]:
    return [
        str(value)
        for value in values
        if not str(value).startswith((_NO_NOTIFICATION, _MULTIPLE_NOTIFICATION))
    ]


def _without_generic_compile_errors(values: list[Any]) -> list[str]:
    return [
        str(value)
        for value in values
        if not str(value).startswith(_GENERIC_COMPILE_ERRORS)
    ]


def _multiple_message(items: list[dict[str, Any]]) -> str:
    names = ", ".join(_candidate_label(item) for item in items[:8])
    return (
        _MULTIPLE_NOTIFICATION
        + " HomeBrain will not guess the recipient. Keep only the intended phone/push device in the MCP selected-device list. Candidates: "
        + names
    )


class NotificationSafeNativeRuleMachineWorkflow(NativeRuleMachineAutomationWorkflow):
    """Native RM workflow with authoritative notification-device discovery.

    The general detailed-device catalogue may be incomplete on some MCP gateway
    combinations even though the selected mobile-app device is present in the
    compact list. Notification rules therefore query the server's exact
    Notification capability filter and intersect it with the current selected IDs.
    """

    @staticmethod
    def _prepare_washing_draft(draft: dict[str, Any]) -> None:
        unresolved = _without_generic_compile_errors(list(draft.get("unresolved") or []))
        devices = [item for item in (draft.get("devices") or []) if isinstance(item, dict)]
        power_device = next(
            (
                item
                for item in devices
                if item.get("id")
                and "power" in {_normalise(name) for name in _attributes(item)}
            ),
            None,
        )
        if power_device is None:
            power_device = next(
                (
                    item
                    for item in devices
                    if item.get("id")
                    and any(
                        token in _normalise(item.get("label"))
                        for token in ("washing", "washer", "laundry")
                    )
                ),
                None,
            )
        if power_device is None:
            unresolved.append(
                "The washing-machine power meter could not be resolved to one selected MCP device ID."
            )
        else:
            draft["washing_power_device"] = dict(power_device)
            # These compact review shapes are not sent to Rule Machine. The native
            # compiler converts them into the guarded two-threshold RM plan.
            draft["triggers"] = [
                {
                    "type": "power_above",
                    "deviceId": str(power_device["id"]),
                    "watts": 10,
                },
                {
                    "type": "power_below_stable",
                    "deviceId": str(power_device["id"]),
                    "watts": 5,
                    "duration": 180,
                },
            ]
            draft["actions"] = [
                {"type": "arm_cycle"},
                {"type": "notify_when_finished"},
                {"type": "reset_cycle_arm"},
            ]
        draft["unresolved"] = list(dict.fromkeys(unresolved))

    async def _draft(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        draft = await super()._draft(recommendation)
        kind = str(draft.get("type") or "")
        if kind not in _NOTIFICATION_RULE_TYPES:
            return draft

        if kind == "washing-complete":
            self._prepare_washing_draft(draft)

        existing = list(draft.get("notification_candidates") or [])
        if len(existing) == 1:
            unresolved = _without_notification_errors(list(draft.get("unresolved") or []))
            draft["devices"] = self._dedupe_refs(
                list(draft.get("devices") or []) + existing
            )
            draft["unresolved"] = list(dict.fromkeys(unresolved))
            return draft
        if len(existing) > 1:
            unresolved = _without_notification_errors(list(draft.get("unresolved") or []))
            unresolved.append(_multiple_message(existing))
            draft["unresolved"] = list(dict.fromkeys(unresolved))
            return draft

        try:
            selected = await self.device_index.summary_devices(force=True)
        except Exception:
            selected = []
        selected_ids = {
            _device_id(item)
            for item in selected
            if _device_id(item) and item.get("disabled") is not True
        }

        candidates: list[dict[str, Any]] = []
        probe_error: str | None = None
        try:
            result = await self.client.call_tool(
                "hub_list_devices",
                {
                    "detailed": True,
                    "format": "detailed",
                    "capabilityFilter": "Notification",
                    "fields": [
                        "id",
                        "name",
                        "label",
                        "room",
                        "capabilities",
                        "commands",
                        "attributes",
                        "disabled",
                    ],
                },
            )
            if result.is_error:
                probe_error = result.text or "Notification capability lookup failed"
            else:
                by_id: dict[str, dict[str, Any]] = {}
                for item in _rows(result.data):
                    device_id = _device_id(item)
                    if not device_id or device_id not in selected_ids:
                        continue
                    if item.get("disabled") is True:
                        continue
                    by_id[device_id] = item
                candidates = list(by_id.values())
        except Exception as exc:
            probe_error = str(exc)

        unresolved = _without_notification_errors(list(draft.get("unresolved") or []))
        draft["notification_probe"] = {
            "selected_ids": sorted(selected_ids),
            "matched_ids": sorted(_device_id(item) for item in candidates),
            "error": probe_error,
        }

        refs = [self._device_ref(item) for item in candidates]
        refs = self._dedupe_refs(refs)
        draft["notification_candidates"] = refs

        if len(refs) == 1:
            draft["devices"] = self._dedupe_refs(list(draft.get("devices") or []) + refs)
            draft["unresolved"] = unresolved
            return draft

        if len(refs) > 1:
            unresolved.append(_multiple_message(candidates))
        else:
            unresolved.append(
                _NO_NOTIFICATION
                + " Add one Hubitat mobile/push notification device to the MCP selected-device list, refresh the cache, and build again."
            )
            if probe_error:
                unresolved.append("Notification capability probe error: " + probe_error)

        draft["unresolved"] = list(dict.fromkeys(unresolved))
        return draft


def install_notification_safe_native_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> NotificationSafeNativeRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = NotificationSafeNativeRuleMachineWorkflow(
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


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            rows.extend(_mapping_rows(item))
        return rows
    if not isinstance(value, dict):
        return rows

    keys = {str(key).lower() for key in value}
    identifying = {
        "filename",
        "file_name",
        "name",
        "location",
        "scope",
        "created",
        "createdat",
        "created_at",
        "createdepoch",
        "timestamp",
        "date",
        "backuptime",
        "agehours",
        "agems",
    }
    if keys.intersection(identifying):
        rows.append(value)
    for item in value.values():
        rows.extend(_mapping_rows(item))
    return rows


def _number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _epoch_ms(value: Any) -> int | None:
    number = _number(value)
    if number is not None:
        if number > 10_000_000_000:
            return int(number)
        if number > 1_000_000_000:
            return int(number * 1000)

    text = str(value or "").strip()
    if not text:
        return None
    normalised = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)

    # Hubitat backup filenames commonly include at least YYYY-MM-DD. Accept a
    # date-only filename only when it is today's date; that proves age <24h
    # without guessing the backup time.
    match = re.search(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        today = datetime.now().astimezone().date()
        try:
            backup_date = datetime(year, month, day).date()
        except ValueError:
            return None
        if backup_date == today:
            return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return None


def _backup_timestamp_ms(item: dict[str, Any], now_ms: int) -> int | None:
    lowered = {str(key).lower(): value for key, value in item.items()}

    for key in ("agems", "age_ms", "agemillis", "agemilliseconds"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24 * 60 * 60 * 1000:
            return int(now_ms - age)
    for key in ("agehours", "age_hours"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24:
            return int(now_ms - age * 60 * 60 * 1000)
    for key in ("ageseconds", "age_seconds"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24 * 60 * 60:
            return int(now_ms - age * 1000)

    for key in (
        "createdepoch",
        "created_epoch",
        "timestamp",
        "epoch",
        "createdat",
        "created_at",
        "created",
        "backuptime",
        "backup_time",
        "date",
        "time",
        "modified",
        "lastmodified",
        "last_modified",
        "filename",
        "file_name",
        "name",
    ):
        if key in lowered:
            parsed = _epoch_ms(lowered[key])
            if parsed is not None:
                return parsed
    return None


def _looks_like_local_hub_backup(item: dict[str, Any]) -> bool:
    values = " ".join(
        str(item.get(key) or "")
        for key in ("location", "scope", "storage", "type", "source", "kind")
    ).lower()
    if "cloud" in values or "source" in values or "code" in values:
        return False
    if any(token in values for token in ("local", "hub_local", "hub", "database")):
        return True
    # The server was explicitly queried with scope=hub_local, so rows that omit
    # a location discriminator are still local whole-hub backups.
    return True


class FinalWashingRuleMachineWorkflow(WashingRuleMachineWorkflow):
    """Final washing workflow with verified backups and clear confirmations."""

    async def _find_tool(
        self,
        names: set[str],
        *,
        refresh: bool = False,
    ) -> LiveRuleTool | None:
        """Find direct, mapped or catalogue-only MCP tools.

        Some MCP gateway descriptions are deliberately compact and therefore do not
        enumerate every hidden child tool. Probe live gateway catalogues only after
        the normal direct/mapped lookup has failed.
        """

        found = await super()._find_tool(names, refresh=refresh)
        if found is not None:
            return found

        requested = {str(name).lower() for name in names}
        try:
            visible = await self.client.list_tools(refresh=refresh)
        except Exception:
            return None

        gateways: list[tuple[int, str]] = []
        for tool in visible:
            name = str(getattr(tool, "name", "") or "")
            schema = dict(getattr(tool, "input_schema", {}) or {})
            properties = (
                schema.get("properties")
                if isinstance(schema.get("properties"), dict)
                else {}
            )
            description = str(getattr(tool, "description", "") or "")
            text = f"{name} {description}".lower()
            is_gateway = bool(
                {"tool", "args"}.issubset(properties)
                or name.startswith(("hub_manage_", "manage_", "hub_read_"))
            )
            if not is_gateway:
                continue

            tokens = {
                token
                for requested_name in requested
                for token in requested_name.removeprefix("hub_").split("_")
                if len(token) >= 4
            }
            priority = 0 if any(token in text for token in tokens) else 1
            gateways.append((priority, name))

        for _, gateway in sorted(set(gateways)):
            try:
                catalogue = await self.client.call_tool(gateway, {})
            except Exception:
                continue
            if catalogue.is_error:
                continue
            for row in _tool_rows(catalogue.data):
                row_name = str(row.get("name") or "")
                if row_name.lower() not in requested:
                    continue
                return LiveRuleTool(
                    name=row_name,
                    description=str(row.get("description") or ""),
                    schema=dict(row.get("schema") or {}),
                    gateway=gateway,
                )
        return None

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
        }
        tool = await self._find_tool({"hub_list_backups", "list_backups"}, refresh=True)
        if tool is None:
            details["error"] = "hub_list_backups was not advertised"
            return False, details

        args = {self._argument_name(tool, "scope", "scope"): "hub_local"}
        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if "limit" in properties:
            args["limit"] = 10

        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            details["error"] = str(exc)
            return False, details

        details.update(
            {
                "checked": True,
                "tool": tool.name,
                "gateway": tool.gateway,
                "arguments": args,
            }
        )
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        candidates: list[dict[str, Any]] = []
        for item in _mapping_rows(result.data):
            if not _looks_like_local_hub_backup(item):
                continue
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            if timestamp_ms is None:
                continue
            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": item.get("fileName")
                    or item.get("filename")
                    or item.get("name")
                    or item.get("id"),
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["candidate_count"] = len(candidates)
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details
        details["error"] = "No verifiable local hub backup from the last 24 hours was listed"
        return False, details

    async def _ensure_backup(self, key: str | None) -> tuple[bool, dict[str, Any]]:
        listed_ok, listed = await self._recent_listed_backup()
        if listed_ok:
            return True, {
                "created": False,
                "recent": True,
                "verified_by": "hub_list_backups",
                "listed": listed,
            }

        created_ok, created = await super()._ensure_backup(key)
        if created_ok:
            created["listed_before_create"] = listed
            return True, created

        error = str(created.get("error") or "")
        if "not advertised" in error.lower():
            created["error"] = (
                "hub_create_backup is not present in MCP tools/list. It is a separate core tool, "
                "not part of hub_manage_backup. In Apps > MCP Rule Server > Settings > Advanced: "
                "Per-tool Overrides, remove hub_create_backup from Disabled tools or use Reset all "
                "overrides, then save and refresh MCP tools."
            )
        created["listed_backup_check"] = listed
        return False, created

    async def _call_operation(
        self,
        pending: PendingRule,
        operation: str,
    ) -> dict[str, Any]:
        answer = await super()._call_operation(pending, operation)
        is_washing = str((pending.draft or {}).get("type") or "") == "washing-complete"
        if is_washing and operation == "enable" and answer.get("success") is True:
            title = str((pending.created_rule or {}).get("name") or "Washing machine rule")
            answer["message"] = (
                f"Enabled **{title}**. It can now monitor washing-machine power and notify "
                "the selected phone after a genuine cycle finishes."
            )
        return answer

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checked for an existing local hub backup from the last 24 hours, "
                    "then tried the separate hub_create_backup core tool. If it is absent, open "
                    "MCP Rule Server > Settings > Advanced: Per-tool Overrides and reset or "
                    "re-enable hub_create_backup, refresh MCP tools, then press Create again."
                )
        return answer


def install_final_washing_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> FinalWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = FinalWashingRuleMachineWorkflow(
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


def _acknowledgment_key(value: Any) -> str | None:
    """Read the MCP best-practice key from current and older guide wording."""

    key = _best_practice_key(value)
    if key:
        return key

    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value or "")

    patterns = (
        r"acknowledg(?:e)?ment\s+key\s*(?:is|=|:)\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
        r"acknowledg(?:e)?ment\s+token\s*(?:is|=|:)\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
        r"bestPracticeKey\s*[=:]\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _plain_backup_rows(value: Any) -> list[dict[str, Any]]:
    """Recover backup filenames when a server returns strings instead of objects."""

    rows: list[dict[str, Any]] = []
    if isinstance(value, str):
        text = value.strip()
        if text.lower().endswith((".lzf", ".zip")):
            rows.append({"fileName": text, "location": "local"})
        return rows
    if isinstance(value, list):
        for item in value:
            rows.extend(_plain_backup_rows(item))
        return rows
    if isinstance(value, dict):
        for item in value.values():
            rows.extend(_plain_backup_rows(item))
    return rows


class ConfirmedBackupWashingRuleMachineWorkflow(FinalWashingRuleMachineWorkflow):
    """Backup-safe Rule Machine workflow with strict gateway verification.

    Hubitat backup creation can exceed the normal 25-second MCP request timeout.
    A blank timeout exception does not prove the backup failed, so the workflow
    polls the local backup list and prevents duplicate backup creation attempts
    while the first confirmed request may still be running.

    Backup listing deliberately bypasses generic catalogue probing. A source-code
    gateway can mention ``hub_list_backups`` in app text and must never be accepted
    as the owning gateway. Only the direct core tool or ``hub_manage_backup`` is
    permitted for backup verification.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._backup_pending_until = 0.0

    async def _read_best_practice_key(self) -> str | None:
        now = time.monotonic()
        if self._best_practice_cache and now - self._best_practice_cache[0] < 600:
            return self._best_practice_cache[1]

        tool = await self._find_tool(_GUIDE_NAMES, refresh=True)
        if tool is None:
            self._best_practice_cache = (now, None)
            return None

        section_field = self._argument_name(tool, "section", "section")
        key: str | None = None
        for section in ("best_practice_reference", "backup"):
            try:
                result = await self._call_rule_tool(tool, {section_field: section})
            except Exception:
                continue
            if result.is_error:
                continue
            key = _acknowledgment_key(result.data) or _acknowledgment_key(result.text)
            if key:
                break

        self._best_practice_cache = (now, key)
        return key

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
            "strict_gateway": True,
        }
        try:
            tools = await self.client.list_tools(refresh=True)
        except Exception as exc:
            details["error"] = f"Could not refresh MCP tools: {type(exc).__name__}: {str(exc).strip()}"
            return False, details

        visible = {str(getattr(tool, "name", "") or ""): tool for tool in tools}
        list_args: dict[str, Any] = {"scope": "hub_local", "limit": 10}
        gateway: str | None = None
        request_name: str
        request_args: dict[str, Any]

        if "hub_list_backups" in visible:
            request_name = "hub_list_backups"
            schema = dict(getattr(visible[request_name], "input_schema", {}) or {})
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            if properties:
                list_args = {key: value for key, value in list_args.items() if key in properties}
            request_args = list_args
        elif "hub_manage_backup" in visible:
            request_name = "hub_manage_backup"
            gateway = request_name
            request_args = {"tool": "hub_list_backups", "args": list_args}
        else:
            details["error"] = (
                "Neither the direct hub_list_backups tool nor the hub_manage_backup gateway "
                "was advertised. HomeBrain will not use an unrelated gateway for backup verification."
            )
            details["visible_backup_tools"] = sorted(
                name for name in visible if "backup" in name.lower()
            )
            return False, details

        details.update(
            {
                "checked": True,
                "tool": "hub_list_backups",
                "gateway": gateway,
                "request_tool": request_name,
                "arguments": list_args,
            }
        )
        try:
            result = await self.client.call_tool(request_name, request_args)
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = str(exc).strip() or f"{type(exc).__name__} while listing backups"
            return False, details

        details["result_is_error"] = bool(result.is_error)
        details["response_type"] = type(result.data).__name__
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        raw_rows = _mapping_rows(result.data) + _plain_backup_rows(result.data)
        unique_rows: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw_rows):
            if not isinstance(item, dict) or not _looks_like_local_hub_backup(item):
                continue
            key = str(
                item.get("id")
                or item.get("fileName")
                or item.get("filename")
                or item.get("name")
                or index
            )
            existing = unique_rows.get(key, {})
            unique_rows[key] = {**existing, **item}

        candidates: list[dict[str, Any]] = []
        unparseable_names: list[str] = []
        for item in unique_rows.values():
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            name = item.get("fileName") or item.get("filename") or item.get("name") or item.get("id")
            if timestamp_ms is None:
                if name:
                    unparseable_names.append(str(name))
                continue
            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": name,
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["row_count"] = len(unique_rows)
        details["candidate_count"] = len(candidates)
        if unparseable_names:
            details["unparseable_names"] = unparseable_names[:5]
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details

        details["error"] = "No verifiable local hub backup from the last 24 hours was listed"
        return False, details

    async def _poll_recent_backup(
        self,
        delays: tuple[float, ...],
    ) -> tuple[bool, list[dict[str, Any]]]:
        checks: list[dict[str, Any]] = []
        for delay in delays:
            if delay > 0:
                await asyncio.sleep(delay)
            ok, details = await self._recent_listed_backup()
            checks.append(details)
            if ok:
                return True, checks
        return False, checks

    async def _ensure_backup(
        self,
        key: str | None,
        *,
        force: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        if time.monotonic() < self._backup_pending_until:
            listed_ok, listed = await self._recent_listed_backup()
            if listed_ok:
                self._backup_pending_until = 0.0
                return True, {
                    "created": True,
                    "recent": True,
                    "verified_by": "hub_list_backups_after_pending_create",
                    "listed": listed,
                    "best_practice_key_found": bool(key),
                }
            return False, {
                "created": False,
                "recent": False,
                "started": True,
                "pending": True,
                "listed_backup_check": listed,
                "best_practice_key_found": bool(key),
                "error": (
                    "The confirmed backup request may still be running on Hubitat. "
                    "Wait about 30 seconds, then press Create this rule again. "
                    "HomeBrain will verify the completed backup before writing the rule."
                ),
            }

        listed: dict[str, Any] = {"checked": False, "skipped_for_explicit_create": force}
        if not force:
            listed_ok, listed = await self._recent_listed_backup()
            if listed_ok:
                return True, {
                    "created": False,
                    "recent": True,
                    "verified_by": "hub_list_backups",
                    "listed": listed,
                    "best_practice_key_found": bool(key),
                }

        details: dict[str, Any] = {
            "created": False,
            "recent": False,
            "listed_backup_check": listed,
            "best_practice_key_found": bool(key),
        }
        tool = await self._find_tool(_BACKUP_NAMES, refresh=True)
        if tool is None:
            details["error"] = (
                "hub_create_backup is not present in MCP tools/list. In Apps > MCP Rule Server > "
                "Settings > Advanced: Per-tool Overrides, remove hub_create_backup from Disabled "
                "tools or reset the overrides, save, then refresh MCP tools."
            )
            return False, details

        args: dict[str, Any] = {
            self._argument_name(tool, "confirm", "confirm"): True,
        }
        args = self._add_best_practice_key(tool, args, key)
        properties = tool.schema.get("properties") if isinstance(tool.schema, dict) else None
        supports_op_token = not properties or any(
            re.sub(r"[^a-z0-9]", "", str(name).lower()) == "optoken"
            for name in properties
        )
        if supports_op_token:
            args[self._argument_name(tool, "optoken", "opToken")] = (
                "homebrain-backup-" + uuid.uuid4().hex[:20]
            )
        details.update(
            {
                "tool": tool.name,
                "gateway": tool.gateway,
                "confirm_sent": True,
                "arguments": {
                    name: ("<present>" if "key" in name.lower() else value)
                    for name, value in args.items()
                },
            }
        )

        result = None
        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = str(exc).strip()

        if result is not None:
            details["result"] = result.data
            details["result_is_error"] = bool(result.is_error)
            if result.is_error or _nested_value(result.data, "success") is False:
                details["error"] = result.text or str(
                    _nested_value(result.data, "error") or "Backup failed"
                )
            elif str(_nested_value(result.data, "status") or "").lower() == "in_progress":
                details["error"] = "The hub backup started successfully and is still in progress."
                details["started"] = True
            else:
                details["created"] = True
                details["recent"] = True
                self._backup_pending_until = 0.0
                return True, details

        error = str(details.get("error") or "").strip()
        timeout_type = str(details.get("exception_type") or "").lower()
        ambiguous_or_running = bool(
            details.get("started")
            or not error
            or "timeout" in timeout_type
            or "timed out" in error.lower()
        )
        if not ambiguous_or_running:
            return False, details

        self._backup_pending_until = time.monotonic() + 120.0
        verified, checks = await self._poll_recent_backup((2.0, 4.0, 6.0))
        details["post_create_checks"] = checks
        details["timeout_or_async_response"] = True
        details["pending"] = not verified

        if verified:
            self._backup_pending_until = 0.0
            details.update(
                {
                    "created": True,
                    "recent": True,
                    "verified_by": "hub_list_backups_after_create",
                    "error": None,
                }
            )
            return True, details

        details["created"] = False
        details["recent"] = False
        details["started"] = True
        details["error"] = (
            "The confirmed backup call did not return a completion result before the "
            "25-second MCP timeout. Hubitat may still be creating it. Wait about 30 "
            "seconds and press Create this rule again; HomeBrain will check for the "
            "new backup and will not write the rule until it is verified."
        )
        return False, details

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain verifies backups only through hub_list_backups or the "
                    "hub_manage_backup gateway, and polls after a long-running backup request."
                )
        return answer


def install_confirmed_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> ConfirmedBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = ConfirmedBackupWashingRuleMachineWorkflow(
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


_HUBITAT_BACKUP_DATE = re.compile(
    r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)"
)


def _hubitat_backup_filename_date(value: Any) -> date | None:
    """Extract the calendar date from Hubitat whole-hub backup filenames.

    Current Hubitat local backups can be named either
    ``2026-07-19~2.5.1.131.lzf`` or
    ``Hub_C8_Pro_2026-07-19~2.5.1.131~manual.lzf``.
    """

    text = str(value or "").strip()
    if not text.lower().endswith((".lzf", ".zip")):
        return None
    match = _HUBITAT_BACKUP_DATE.search(text)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _row_name(item: dict[str, Any]) -> str | None:
    value = (
        item.get("fileName")
        or item.get("filename")
        or item.get("file_name")
        or item.get("name")
        or item.get("id")
    )
    return str(value) if value not in (None, "") else None


def _find_backup_epoch(value: Any) -> Any:
    """Find Hubitat's last-backup epoch in nested MCP response shapes."""

    if isinstance(value, dict):
        for key, item in value.items():
            normal = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normal in {
                "lastbackupepoch",
                "lastbackup",
                "lastbackuptimestamp",
                "backupepoch",
            }:
                return item
        for item in value.values():
            found = _find_backup_epoch(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_backup_epoch(item)
            if found is not None:
                return found
    return None


def _normalise_epoch_ms(value: Any) -> int | None:
    try:
        number = float(str(value).strip())
    except Exception:
        return None
    if number > 10_000_000_000:
        return int(number)
    if number > 1_000_000_000:
        return int(number * 1000)
    return None


class FilenameSafeBackupWashingRuleMachineWorkflow(
    ConfirmedBackupWashingRuleMachineWorkflow
):
    """Verify current Hubitat local backups without depending on list ordering.

    Some MCP releases return local backups oldest-first. A limit of ten can omit a
    manual backup created moments earlier. Request a larger local set and treat a
    whole-hub filename carrying today's date as verified recent evidence. If the
    backup gateway still omits the newest file, use Hubitat's authoritative
    ``lastBackupEpoch`` before attempting another backup.
    """

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
            "strict_gateway": True,
            "requested_limit": 100,
        }
        try:
            tools = await self.client.list_tools(refresh=True)
        except Exception as exc:
            details["error"] = (
                f"Could not refresh MCP tools: {type(exc).__name__}: "
                f"{str(exc).strip()}"
            )
            return False, details

        visible = {str(getattr(tool, "name", "") or ""): tool for tool in tools}
        desired_args: dict[str, Any] = {"scope": "hub_local", "limit": 100}
        gateway: str | None = None
        request_name: str
        request_args: dict[str, Any]
        effective_args = dict(desired_args)

        if "hub_list_backups" in visible:
            request_name = "hub_list_backups"
            schema = dict(getattr(visible[request_name], "input_schema", {}) or {})
            properties = (
                schema.get("properties")
                if isinstance(schema.get("properties"), dict)
                else {}
            )
            if properties:
                effective_args = {
                    key: value for key, value in desired_args.items() if key in properties
                }
            request_args = effective_args
        elif "hub_manage_backup" in visible:
            request_name = "hub_manage_backup"
            gateway = request_name
            request_args = {"tool": "hub_list_backups", "args": effective_args}
        else:
            details["error"] = (
                "Neither the direct hub_list_backups tool nor the "
                "hub_manage_backup gateway was advertised. HomeBrain will not use "
                "an unrelated gateway for backup verification."
            )
            details["visible_backup_tools"] = sorted(
                name for name in visible if "backup" in name.lower()
            )
            return False, details

        details.update(
            {
                "checked": True,
                "tool": "hub_list_backups",
                "gateway": gateway,
                "request_tool": request_name,
                "arguments": effective_args,
            }
        )
        try:
            result = await self.client.call_tool(request_name, request_args)
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = (
                str(exc).strip() or f"{type(exc).__name__} while listing backups"
            )
            return False, details

        details["result_is_error"] = bool(result.is_error)
        details["response_type"] = type(result.data).__name__
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        today = datetime.now().astimezone().date()
        raw_rows = _mapping_rows(result.data) + _plain_backup_rows(result.data)
        unique_rows: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw_rows):
            if not isinstance(item, dict) or not _looks_like_local_hub_backup(item):
                continue
            key = str(
                item.get("id")
                or item.get("fileName")
                or item.get("filename")
                or item.get("file_name")
                or item.get("name")
                or index
            )
            existing = unique_rows.get(key, {})
            unique_rows[key] = {**existing, **item}

        candidates: list[dict[str, Any]] = []
        dated_but_not_recent: list[str] = []
        unparseable_names: list[str] = []
        filename_today_matches: list[str] = []

        for item in unique_rows.values():
            name = _row_name(item)
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            source = "metadata"

            filename_date = _hubitat_backup_filename_date(name)
            if filename_date == today:
                # A whole-hub local filename carrying today's date is enough to
                # establish that it is less than 24 hours old without guessing its
                # exact creation time.
                timestamp_ms = now_ms
                source = "filename_today"
                if name:
                    filename_today_matches.append(name)
            elif timestamp_ms is None and filename_date is not None:
                if name:
                    dated_but_not_recent.append(name)
                continue

            if timestamp_ms is None:
                if name:
                    unparseable_names.append(name)
                continue

            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": name,
                    "timestamp_source": source,
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["row_count"] = len(unique_rows)
        details["candidate_count"] = len(candidates)
        if filename_today_matches:
            details["filename_today_matches"] = filename_today_matches[:5]
        if dated_but_not_recent:
            details["dated_older_names"] = dated_but_not_recent[:5]
        if unparseable_names:
            details["unparseable_names"] = unparseable_names[:5]
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details

        details["error"] = (
            "No verifiable local hub backup from the last 24 hours was listed"
        )
        return False, details

    async def _recent_hub_info_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_get_info.lastBackupEpoch",
        }
        try:
            result = await self.client.call_tool("hub_get_info", {})
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = str(exc).strip() or f"{type(exc).__name__} reading hub info"
            return False, details

        details["checked"] = True
        details["result_is_error"] = bool(result.is_error)
        if result.is_error:
            details["error"] = result.text or "hub_get_info failed"
            return False, details

        raw_epoch = _find_backup_epoch(result.data)
        epoch_ms = _normalise_epoch_ms(raw_epoch)
        details["epoch_found"] = raw_epoch is not None
        if epoch_ms is None:
            details["error"] = "hub_get_info did not return a usable lastBackupEpoch"
            return False, details

        now_ms = int(time.time() * 1000)
        age_ms = now_ms - epoch_ms
        details.update({"last_backup_epoch": epoch_ms, "age_ms": age_ms})
        if 0 <= age_ms < _BACKUP_MAX_AGE_MS:
            details["recent"] = True
            return True, details

        details["error"] = "Hubitat lastBackupEpoch is older than 24 hours"
        return False, details

    async def _ensure_backup(
        self,
        key: str | None,
        *,
        force: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        listed: dict[str, Any] = {
            "checked": False,
            "skipped_for_explicit_create": force,
        }
        hub_info: dict[str, Any] = {
            "checked": False,
            "skipped_for_explicit_create": force,
        }
        if not force:
            listed_ok, listed = await self._recent_listed_backup()
            if listed_ok:
                return True, {
                    "created": False,
                    "recent": True,
                    "verified_by": "hub_list_backups_filename_safe",
                    "listed": listed,
                    "best_practice_key_found": bool(key),
                }

            info_ok, hub_info = await self._recent_hub_info_backup()
            if info_ok:
                return True, {
                    "created": False,
                    "recent": True,
                    "verified_by": "hub_get_info_lastBackupEpoch",
                    "listed_backup_check": listed,
                    "hub_info_backup_check": hub_info,
                    "best_practice_key_found": bool(key),
                }

        ok, details = await super()._ensure_backup(key, force=force)
        details.setdefault("listed_backup_check", listed)
        details["hub_info_backup_check"] = hub_info
        return ok, details

    async def _create(self, pending: Any) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checks up to 100 local backups through "
                    "hub_list_backups or hub_manage_backup, recognises current "
                    "Hubitat manual filenames, and falls back to hub_get_info "
                    "lastBackupEpoch before requesting another backup."
                )
        return answer


def install_filename_safe_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> FilenameSafeBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = FilenameSafeBackupWashingRuleMachineWorkflow(
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


_NATIVE_WRITE_NAMES = {
    "hub_set_rule",
    "set_rule",
    "hub_set_rule_paused",
    "set_rule_paused",
}


_RULE_GATEWAY_NAMES = (
    "hub_manage_rule_machine",
    "hub_manage_native_rules_and_apps",
)


def _redacted(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): ("<present>" if "key" in str(key).lower() else value)
        for key, value in arguments.items()
    }


def _error_text(exc: Exception) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__


class WriteSafeBackupWashingRuleMachineWorkflow(
    FilenameSafeBackupWashingRuleMachineWorkflow
):
    """Keep native Rule Machine HTTP errors inside structured HomeBrain results.

    MCP Rule Server can expose native writes directly or through either native-RM
    category gateway. All create/update calls carry stable operation tokens, so the
    same arguments can be retried through another advertised route without creating
    a second mutation.
    """

    async def _call_rule_tool(self, tool: Any, arguments: dict[str, Any]):
        name = str(getattr(tool, "name", "") or "")
        if name not in _NATIVE_WRITE_NAMES:
            return await super()._call_rule_tool(tool, arguments)

        attempts: list[dict[str, Any]] = []
        primary_gateway = str(getattr(tool, "gateway", "") or "") or None
        try:
            return await super()._call_rule_tool(tool, arguments)
        except Exception as exc:
            attempts.append(
                {
                    "route": primary_gateway or "direct",
                    "exception_type": type(exc).__name__,
                    "error": _error_text(exc),
                }
            )

        visible_names: set[str] = set()
        try:
            visible_names = {
                str(getattr(item, "name", "") or "")
                for item in await self.client.list_tools(refresh=True)
            }
        except Exception as exc:
            attempts.append(
                {
                    "route": "tools/list",
                    "exception_type": type(exc).__name__,
                    "error": _error_text(exc),
                }
            )

        alternatives: list[tuple[str, dict[str, Any]]] = []
        if primary_gateway and name in visible_names:
            alternatives.append((name, dict(arguments)))
        for gateway in _RULE_GATEWAY_NAMES:
            if gateway in visible_names and gateway != primary_gateway:
                alternatives.append(
                    (gateway, {"tool": name, "args": dict(arguments)})
                )

        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[str, dict[str, Any]]] = []
        for request_name, request_args in alternatives:
            signature = (request_name, repr(request_args))
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append((request_name, request_args))

        for request_name, request_args in deduped:
            try:
                result = await self.client.call_tool(request_name, request_args)
                result.raw.setdefault(
                    "homebrain_write_route_recovery",
                    {
                        "primary": primary_gateway or "direct",
                        "recovered_via": request_name,
                    },
                )
                return result
            except Exception as exc:
                attempts.append(
                    {
                        "route": request_name,
                        "exception_type": type(exc).__name__,
                        "error": _error_text(exc),
                    }
                )

        summary = "; ".join(
            f"{item['route']}: {item['exception_type']}: {item['error']}"
            for item in attempts
        )
        message = (
            f"Native Rule Machine write '{name}' failed before Hubitat returned a "
            f"tool result. {summary}"
        )
        data = {
            "success": False,
            "error": message,
            "exceptionType": attempts[-1]["exception_type"] if attempts else "MCPError",
            "writeTool": name,
            "primaryGateway": primary_gateway,
            "alternateRouteAttempted": len(deduped) > 0,
            "attempts": attempts,
            "arguments": _redacted(dict(arguments)),
        }
        return MCPToolResult(
            name=name,
            arguments=dict(arguments),
            raw={"isError": True, "homebrain": data},
            text=message,
            data=data,
            is_error=True,
        )


def install_write_safe_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> WriteSafeBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = WriteSafeBackupWashingRuleMachineWorkflow(
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


_HEALTH_PROBE_LIMIT = 20


class RepairIdSafeWashingRuleMachineWorkflow(
    SplitRepairWashingRuleMachineWorkflow
):
    """Resolve paused RM duplicates by authoritative rule ID and rendered label.

    Some MCP Rule Server releases return ``name: Rule-5.1`` from
    ``hub_list_rules`` while the user-visible rule label is only available from
    ``hub_get_rule_health``. Exact-name duplicate detection and repair must not
    depend on the generic type name.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._repair_match_override: ContextVar[dict[str, Any] | None] = ContextVar(
            "homebrain_repair_match_override",
            default=None,
        )

    async def _health_verified_rule(
        self,
        app_id: int,
        expected_name: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        result, details = await self._call_hidden_read(
            "hub_get_rule_health",
            {"appId": app_id, "source": "auto"},
        )
        details["app_id"] = app_id
        if result is None:
            return None, details

        data = _result_mapping(result.data)
        details["health"] = data
        rule_format = str(data.get("ruleFormat") or "").strip().lower()
        if rule_format and rule_format != "rm":
            details["error"] = f"App {app_id} is not a Rule Machine rule"
            return None, details

        raw_label = data.get("label") or data.get("name")
        clean_label = _clean_rule_label(raw_label)
        details["raw_label"] = str(raw_label or "")
        details["clean_label"] = clean_label
        if _normalise(clean_label) != _normalise(_clean_rule_label(expected_name)):
            details["error"] = "Rendered Rule Machine label does not match the draft"
            return None, details

        paused = bool(
            data.get("paused") is True
            or "paused" in str(raw_label or "").lower()
            or _normalise(data.get("status")) in {"paused", "disabled", "inactive"}
        )
        details["paused"] = paused
        return (
            {
                "id": app_id,
                "name": clean_label,
                "label": raw_label,
                "raw_name": str(raw_label or ""),
                "paused": paused,
                "status": "Paused" if paused else str(data.get("status") or "Unknown"),
                "health": data,
            },
            details,
        )

    async def _matching_rules(
        self,
        name: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        override = self._repair_match_override.get()
        if override is not None:
            return [dict(override)], {
                "source": "health-verified-repair-target",
                "match_count": 1,
                "matches": [dict(override)],
            }

        matches, details = await super()._matching_rules(name)
        if matches:
            return matches, details

        listed, listed_details = await self._call_hidden_read("hub_list_rules", {})
        fallback: dict[str, Any] = {
            "source": "hub_get_rule_health-label-fallback",
            "list_request": listed_details,
            "probe_limit": _HEALTH_PROBE_LIMIT,
            "probes": [],
        }
        if listed is None:
            details["health_label_fallback"] = fallback
            return [], details

        rows = [
            dict(item)
            for item in self._rule_rows(listed.data)
            if _positive_int(item.get("id") or item.get("ruleId") or item.get("appId"))
            is not None
        ]
        rows.sort(
            key=lambda item: _positive_int(
                item.get("id") or item.get("ruleId") or item.get("appId")
            )
            or 0,
            reverse=True,
        )

        verified: list[dict[str, Any]] = []
        for item in rows[:_HEALTH_PROBE_LIMIT]:
            app_id = _positive_int(
                item.get("id") or item.get("ruleId") or item.get("appId")
            )
            if app_id is None:
                continue
            row, probe = await self._health_verified_rule(app_id, name)
            fallback["probes"].append(probe)
            if row is not None:
                verified.append({**item, **row})

        verified.sort(
            key=lambda item: _positive_int(item.get("id")) or 0,
            reverse=True,
        )
        fallback["match_count"] = len(verified)
        fallback["matches"] = verified
        details["health_label_fallback"] = fallback
        details["matches"] = verified
        details["match_count"] = len(verified)
        return verified, details

    async def _repair_rule(
        self,
        pending: PendingRule,
        requested_id: int | None,
    ) -> dict[str, Any]:
        if (
            requested_id is not None
            and pending.draft is not None
            and str(pending.draft.get("type") or "") == "washing-complete"
        ):
            verified, verification = await self._health_verified_rule(
                requested_id,
                str(pending.draft.get("name") or ""),
            )

            # A partial-create result already carries the exact shell ID. Preserve
            # that safe linkage if a transient health read is unavailable; the base
            # repair flow reasserts paused=true before every authoring write.
            known_id = _positive_int((pending.created_rule or {}).get("id"))
            known_paused = _normalise((pending.created_rule or {}).get("status")) == "paused"
            if verified is None and known_id == requested_id and known_paused:
                verified = {
                    "id": requested_id,
                    "name": str(pending.draft.get("name") or "Washing machine rule"),
                    "label": str(pending.draft.get("name") or "Washing machine rule"),
                    "paused": True,
                    "status": "Paused",
                    "verification_fallback": "pending.created_rule",
                }
                verification["fallback"] = "pending.created_rule"

            if verified is not None:
                if verified.get("paused") is not True:
                    return self._wrong_stage(
                        "HomeBrain found the requested Rule Machine rule but could not verify it is paused. Pause it in Hubitat before repairing it."
                    )
                token = self._repair_match_override.set(verified)
                try:
                    answer = await super()._repair_rule(pending, requested_id)
                finally:
                    self._repair_match_override.reset(token)
                technical = answer.get("technical")
                if isinstance(technical, dict):
                    technical.setdefault("repair_target_verification", verification)
                return answer

        return await super()._repair_rule(pending, requested_id)


def install_repair_id_safe_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> RepairIdSafeWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = RepairIdSafeWashingRuleMachineWorkflow(
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
            requested = (
                _positive_int(repair_match.group(1))
                if repair_match.group(1)
                else None
            )
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
    'FinalWashingRuleMachineWorkflow',
    'NotificationSafeNativeRuleMachineWorkflow',
    'WashingRuleMachineWorkflow',
    '_backup_timestamp_ms',
    '_washing_rule_plan',
    'install_final_washing_rule_machine_workflow',
    'install_notification_safe_native_rule_machine_workflow',
    'install_washing_rule_machine_workflow',
    'ConfirmedBackupWashingRuleMachineWorkflow',
    'install_confirmed_backup_rule_machine_workflow',
    'FilenameSafeBackupWashingRuleMachineWorkflow',
    '_find_backup_epoch',
    '_hubitat_backup_filename_date',
    '_normalise_epoch_ms',
    'install_filename_safe_backup_rule_machine_workflow',
    'WriteSafeBackupWashingRuleMachineWorkflow',
    'install_write_safe_backup_rule_machine_workflow',
    'SplitRepairWashingRuleMachineWorkflow',
    '_clean_rule_label',
    'install_split_repair_rule_machine_workflow',
    'RepairIdSafeWashingRuleMachineWorkflow',
    'install_repair_id_safe_rule_machine_workflow',
]
