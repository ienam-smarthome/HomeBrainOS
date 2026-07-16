from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_attention import FastFallbackRouter as AttentionFastFallbackRouter
from fast_fallback_live import _looks_like_light, live_attributes
from presenter import display_payload


_GROUP_WORDS = {
    "light",
    "lights",
    "lamp",
    "lamps",
    "bulb",
    "bulbs",
    "switch",
    "switches",
}
_FILLER_WORDS = {"all", "the", "my", "our", "room"}


class FastFallbackRouter(AttentionFastFallbackRouter):
    """Attention-aware fallback with verified plural/group device controls."""

    @staticmethod
    def _group_request(requested_name: str) -> tuple[str, list[str]] | None:
        target = _normalise(requested_name)
        words = re.findall(r"[a-z0-9]+", target)
        if not words:
            return None

        plural_kind = None
        if any(word in {"lights", "lamps", "bulbs"} for word in words):
            plural_kind = "light"
        elif "switches" in words:
            plural_kind = "switch"
        elif words[0] == "all" and any(word in _GROUP_WORDS for word in words):
            plural_kind = "light" if any(
                word in {"light", "lights", "lamp", "lamps", "bulb", "bulbs"}
                for word in words
            ) else "switch"

        if plural_kind is None:
            return None

        qualifiers = [
            word
            for word in words
            if word not in _GROUP_WORDS and word not in _FILLER_WORDS
        ]
        return plural_kind, qualifiers

    @staticmethod
    def _group_candidates(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parsed = FastFallbackRouter._group_request(requested_name)
        if parsed is None:
            return []
        kind, qualifiers = parsed

        matches: list[dict[str, Any]] = []
        for item in candidates:
            is_light = _looks_like_light(item)
            if kind == "light" and not is_light:
                continue
            if kind == "switch" and is_light:
                continue

            searchable = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in (
                        "label",
                        "name",
                        "displayName",
                        "room",
                        "category",
                        "type",
                        "deviceType",
                    )
                )
            )
            searchable_words = set(re.findall(r"[a-z0-9]+", searchable))
            if qualifiers and not all(word in searchable_words for word in qualifiers):
                continue
            matches.append(item)

        return sorted(matches, key=lambda item: _label(item).lower())

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        live_result = await self._live_devices("Switch")
        candidates = self._device_rows(live_result.data)
        group = self._group_candidates(requested_name, candidates)
        if group:
            return await self._control_group(
                requested_name,
                action,
                group,
                live_result,
            )
        return await super()._control_device(requested_name, action)

    async def _control_group(
        self,
        requested_name: str,
        action: str,
        devices: list[dict[str, Any]],
        initial_result: Any,
    ) -> dict[str, Any]:
        desired_state = _normalise(action)
        tool = await self.client.get_tool("hub_call_device_command")
        properties = (
            (tool.input_schema or {}).get("properties", {})
            if tool
            else {}
        )

        rows: dict[str, dict[str, Any]] = {}
        command_details: list[dict[str, Any]] = []

        for device in devices:
            device_id = _device_id(device)
            label = _label(device) or f"Device {device_id}"
            initial_state = _normalise(live_attributes(device).get("switch")) or "unknown"
            key = str(device_id)
            rows[key] = {
                "id": device_id,
                "label": label,
                "initial": initial_state,
                "verified": initial_state,
                "command_sent": False,
                "command_error": None,
            }

            if initial_state == desired_state:
                continue
            if device_id is None:
                rows[key]["command_error"] = "Device ID missing"
                continue

            args: dict[str, Any] = {}
            for id_key in ("deviceId", "id", "device_id"):
                if not properties or id_key in properties:
                    args[id_key] = device_id
                    break
            args["command"] = desired_state
            if not properties or "params" in properties:
                args["params"] = []

            result = await self._execute_catalog_tool(
                "hub_call_device_command",
                "hub_manage_devices",
                args,
            )
            rows[key]["command_sent"] = True
            if result.is_error:
                rows[key]["command_error"] = result.text or "Command failed"
            command_details.append(
                {
                    "device_id": device_id,
                    "label": label,
                    "arguments": args,
                    "success": not result.is_error,
                    "result": result.data,
                    "error": result.text if result.is_error else None,
                }
            )

        pending = [
            row
            for row in rows.values()
            if row["initial"] != desired_state
            and row["command_sent"]
            and not row["command_error"]
        ]

        verification_result = initial_result
        if pending:
            for delay in (0.35, 0.75, 1.1):
                await asyncio.sleep(delay)
                verification_result = await self._live_devices("Switch")
                current_by_id = {
                    str(_device_id(item)): item
                    for item in self._device_rows(verification_result.data)
                }
                for row in pending:
                    current = current_by_id.get(str(row["id"]))
                    if current:
                        row["verified"] = (
                            _normalise(live_attributes(current).get("switch"))
                            or "unknown"
                        )
                if all(row["verified"] == desired_state for row in pending):
                    break

        confirmed = 0
        already = 0
        failed = 0
        display_items: list[dict[str, Any]] = []
        lines: list[str] = []

        for row in rows.values():
            if row["initial"] == desired_state:
                already += 1
                state_text = f"Already {desired_state}"
                tone = "success"
                icon = "✅"
            elif row["verified"] == desired_state and not row["command_error"]:
                confirmed += 1
                state_text = f"Confirmed {desired_state}"
                tone = "success"
                icon = "✅"
            else:
                failed += 1
                if row["command_error"]:
                    state_text = f"Command failed: {row['command_error']}"
                elif row["verified"] in {"on", "off"}:
                    state_text = f"Not confirmed · still {row['verified']}"
                else:
                    state_text = "State could not be verified"
                tone = "warning"
                icon = "⚠️"

            lines.append(f"- {row['label']}: {state_text}")
            display_items.append(
                {
                    "icon": icon,
                    "title": row["label"],
                    "subtitle": state_text,
                    "value": row["verified"].title(),
                    "tone": tone,
                }
            )

        total = len(rows)
        successful = confirmed + already
        group_title = requested_name.strip().title()
        if failed == 0:
            message = (
                f"{group_title}: all {total} devices are confirmed {desired_state}.\n"
                + "\n".join(lines)
            )
            intent = "fallback-device-group-control-confirmed"
        else:
            message = (
                f"{group_title}: {successful} of {total} devices are confirmed {desired_state}; "
                f"{failed} could not be confirmed.\n"
                + "\n".join(lines)
            )
            intent = "fallback-device-group-control-partial"

        display = display_payload(
            "device-group-control",
            group_title,
            subtitle=f"{successful} of {total} confirmed {desired_state}",
            metrics=[
                {"label": "Matched", "value": str(total), "icon": "💡"},
                {"label": "Confirmed", "value": str(confirmed), "icon": "✅"},
                {"label": "Already set", "value": str(already), "icon": "↩️"},
                {"label": "Issues", "value": str(failed), "icon": "⚠️"},
            ],
            items=display_items,
            note="Plural light commands are matched by device label/room and verified from Hubitat currentStates.",
        )
        response = self._response(
            message,
            intent,
            failed == 0,
            verification_result,
        )
        response.update(
            {
                "display": display,
                "requested_state": desired_state,
                "matched_devices": total,
                "confirmed_devices": successful,
                "failed_devices": failed,
                "technical": json.dumps(
                    {
                        "requested_name": requested_name,
                        "requested_state": desired_state,
                        "devices": list(rows.values()),
                        "commands": command_details,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            }
        )
        return response
