from __future__ import annotations

from typing import Any, Awaitable, Callable

from automation_rule_workflow import _session_id
from automation_rule_workflow_native_rm import NativeRuleMachineAutomationWorkflow
from device_intelligence_catalogue import _rows
from device_intelligence_index import _device_id, _label, _room_name


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_NO_NOTIFICATION = "No selected Notification-capable device was found."
_MULTIPLE_NOTIFICATION = "More than one Notification-capable device is selected."


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


def _multiple_message(items: list[dict[str, Any]]) -> str:
    names = ", ".join(_candidate_label(item) for item in items[:8])
    return (
        _MULTIPLE_NOTIFICATION
        + " HomeBrain will not guess the recipient. Keep only the intended phone/push device in the MCP selected-device list. Candidates: "
        + names
    )


class NotificationSafeNativeRuleMachineWorkflow(NativeRuleMachineAutomationWorkflow):
    """Native RM workflow with an authoritative Notification capability probe.

    The general detailed-device catalogue may be incomplete on some MCP gateway
    combinations even though the selected mobile-app device is present in the
    compact list. For notification rules, query the server's exact Notification
    capability filter and intersect it with the current selected-device IDs.
    """

    async def _draft(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        draft = await super()._draft(recommendation)
        if str(draft.get("type") or "") != "cold-storage-door":
            return draft

        existing = list(draft.get("notification_candidates") or [])
        if len(existing) == 1:
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


__all__ = [
    "NotificationSafeNativeRuleMachineWorkflow",
    "install_notification_safe_native_rule_machine_workflow",
]
