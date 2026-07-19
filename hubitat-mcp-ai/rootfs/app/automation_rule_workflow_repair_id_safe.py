from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _normalise, _result_mapping, _session_id
from automation_rule_workflow_native_rm import _positive_int
from automation_rule_workflow_split_repair import (
    SplitRepairWashingRuleMachineWorkflow,
    _clean_rule_label,
)


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
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
    "RepairIdSafeWashingRuleMachineWorkflow",
    "install_repair_id_safe_rule_machine_workflow",
]
