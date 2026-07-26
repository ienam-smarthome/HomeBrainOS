from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from automation_rule_workflow import (
    PendingRule,
    _first,
    _result_mapping,
    _session_id,
    _tool_rows,
)
from automation_rule_workflow_native_rm import (
    LiveRuleTool,
    NativeRuleMachineAutomationWorkflow,
    _NATIVE_PAUSE_NAMES,
    _nested_value,
    _positive_int,
)
from device_intelligence_catalogue import _rows
from device_intelligence_index import (
    _attributes,
    _device_id,
    _label,
    _normalise,
    _room_name,
)
from presenter import display_payload, safe_debug


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


__all__ = [
    "FinalWashingRuleMachineWorkflow",
    "NotificationSafeNativeRuleMachineWorkflow",
    "WashingRuleMachineWorkflow",
    "_backup_timestamp_ms",
    "_washing_rule_plan",
    "install_final_washing_rule_machine_workflow",
    "install_notification_safe_native_rule_machine_workflow",
    "install_washing_rule_machine_workflow",
]
