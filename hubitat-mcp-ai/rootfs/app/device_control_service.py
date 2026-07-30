from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from device_state_summary import is_light_device, room_name
from device_target_resolver import normalized_name, resolve_device_candidate
from mcp_client import HubitatMCPClient, MCPToolResult


logger = logging.getLogger("HomeBrainOS.DeviceControl")
DEVICE_CONTROL_TOOL = "homebrain_control_devices"


class DeviceControlService:
    """Resolve and execute routine light/switch controls deterministically."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        if result.is_error:
            return False
        data = result.data
        if isinstance(data, dict):
            if data.get("success") is False or data.get("error"):
                return False
            for key in ("result", "data", "output"):
                nested = data.get(key)
                if isinstance(nested, dict) and (
                    nested.get("success") is False or nested.get("error")
                ):
                    return False
        return True

    @staticmethod
    def _is_switch_device(device: dict[str, Any]) -> bool:
        capabilities = device.get("capabilities") or []
        if isinstance(capabilities, dict):
            capabilities = list(capabilities)
        elif isinstance(capabilities, str):
            capabilities = [capabilities]
        capability_text = " ".join(
            str(item.get("name") if isinstance(item, dict) else item)
            for item in capabilities
        ).casefold()
        return "switch" in capability_text

    async def execute(
        self, arguments: dict[str, Any]
    ) -> MCPToolResult:
        room = str(arguments.get("room") or "").strip()
        names = arguments.get("device_names") or []
        kind = str(arguments.get("device_kind") or "").strip().lower()
        command = str(arguments.get("command") or "").strip()
        if (
            bool(room) == bool(names)
            or not isinstance(names, list)
            or kind not in {"light", "switch"}
            or command not in {"on", "off", "toggle"}
        ):
            return MCPToolResult(
                DEVICE_CONTROL_TOOL,
                arguments,
                {},
                "Invalid control arguments",
                {
                    "success": False,
                    "error": (
                        "Provide exactly one of room or device_names, plus a valid "
                        "device_kind and command."
                    ),
                },
                is_error=True,
            )

        identity_started = time.monotonic()
        identity_manifest: list[dict[str, Any]] = []
        try:
            identity_reader = getattr(
                self.mcp, "get_device_identities", self.mcp.get_cached_devices
            )
            identity_manifest = [
                device
                for device in (await identity_reader() or [])
                if isinstance(device, dict)
            ]
        except Exception as exc:
            logger.warning("Fast control identity lookup unavailable: %s", exc)
        identity_candidates = [
            device
            for device in identity_manifest
            if (
                is_light_device(device)
                if kind == "light"
                else self._is_switch_device(device) and not is_light_device(device)
            )
        ]
        fast_targets: list[dict[str, Any]] = []
        if room:
            wanted_room = normalized_name(room)
            fast_targets = [
                device
                for device in identity_candidates
                if normalized_name(room_name(device)) == wanted_room
            ]
            fast_resolution_complete = bool(fast_targets)
        else:
            fast_resolution_complete = True
            for requested in names:
                resolution = resolve_device_candidate(
                    str(requested), identity_candidates
                )
                if resolution.target is None:
                    fast_resolution_complete = False
                    fast_targets = []
                    break
                target = dict(resolution.target)
                target["_resolved_label"] = resolution.matched_name
                fast_targets.append(target)
        if fast_resolution_complete:
            self._record_evidence(
                "hub_read_devices",
                {
                    "tool": "hub_list_devices",
                    "source": "identity_cache",
                },
                success=True,
                elapsed_ms=round(
                    (time.monotonic() - identity_started) * 1000
                ),
                summary=f"{len(fast_targets)} cached target candidates",
                supports_live_claim=False,
                evidence_kind="control_target_resolution",
            )

        lookup_arguments = (
            []
            if fast_resolution_complete
            else (
                [{"tool": "hub_list_devices", "args": {}}]
                if room
                else [
                    {
                        "tool": "hub_list_devices",
                        "args": {"labelFilter": str(requested)},
                    }
                    for requested in names
                ]
            )
        )

        async def lookup(
            source_arguments: dict[str, Any]
        ) -> tuple[MCPToolResult, int]:
            started = time.monotonic()
            source = await self.mcp.call_tool(
                "hub_read_devices", source_arguments
            )
            return source, round((time.monotonic() - started) * 1000)

        sources = await asyncio.gather(
            *(lookup(source_arguments) for source_arguments in lookup_arguments)
        )
        devices: list[dict[str, Any]] = []
        source_groups: list[list[dict[str, Any]]] = []
        lookup_errors: list[str] = []
        seen_source_ids: set[str] = set()
        for source_arguments, (source, elapsed_ms) in zip(
            lookup_arguments, sources, strict=True
        ):
            source_devices = [
                item
                for item in (
                    HubitatMCPClient._find_device_list(source.data) or []
                )
                if isinstance(item, dict)
            ]
            source_groups.append(source_devices)
            succeeded = self._tool_succeeded(source)
            self._record_evidence(
                "hub_read_devices",
                source_arguments,
                success=succeeded,
                elapsed_ms=elapsed_ms,
                summary=f"{len(source_devices)} target candidates",
                supports_live_claim=False,
                evidence_kind="control_target_resolution",
            )
            if not succeeded:
                lookup_errors.append(
                    source.text or "Hubitat target lookup failed."
                )
                continue
            for device in source_devices:
                source_id = str(
                    device.get("id") or device.get("deviceId") or id(device)
                )
                if source_id not in seen_source_ids:
                    seen_source_ids.add(source_id)
                    devices.append(device)
        if lookup_errors:
            data = {
                "success": False,
                "error": " ".join(lookup_errors),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        candidates = [
            device for device in devices
            if (
                is_light_device(device)
                if kind == "light"
                else self._is_switch_device(device) and not is_light_device(device)
            )
        ]
        targets: list[dict[str, Any]] = list(fast_targets)
        resolution_errors: list[str] = []
        if not targets and room:
            wanted_room = normalized_name(room)
            targets = [
                device for device in candidates
                if normalized_name(room_name(device)) == wanted_room
            ]
            if not targets:
                started = time.monotonic()
                try:
                    manifest = await self.mcp.get_cached_devices()
                except Exception as exc:
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=False,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=f"Room identity manifest unavailable: {exc}",
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                else:
                    room_candidates = [
                        device
                        for device in (manifest or [])
                        if isinstance(device, dict)
                        and normalized_name(room_name(device)) == wanted_room
                        and (
                            is_light_device(device)
                            if kind == "light"
                            else (
                                self._is_switch_device(device)
                                and not is_light_device(device)
                            )
                        )
                    ]
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=True,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=(
                            f"{len(room_candidates)} {kind} candidates in "
                            f"normalized room {room!r}"
                        ),
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                    targets = room_candidates
                if not targets:
                    resolution_errors.append(
                        f"No {kind}s were found in room {room!r}."
                    )
        elif not targets:
            fallback_candidates: list[dict[str, Any]] | None = None
            for requested, source_devices in zip(
                names, source_groups, strict=True
            ):
                eligible = [
                    device for device in source_devices
                    if (
                        is_light_device(device)
                        if kind == "light"
                        else (
                            self._is_switch_device(device)
                            and not is_light_device(device)
                        )
                    )
                ]
                resolution = resolve_device_candidate(
                    str(requested), eligible
                )
                if resolution.target is None:
                    if fallback_candidates is None:
                        started = time.monotonic()
                        try:
                            manifest = await self.mcp.get_cached_devices()
                        except Exception as exc:
                            fallback_candidates = []
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=False,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=f"Identity manifest unavailable: {exc}",
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                        else:
                            fallback_candidates = [
                                device
                                for device in (manifest or [])
                                if isinstance(device, dict)
                                and (
                                    is_light_device(device)
                                    if kind == "light"
                                    else (
                                        self._is_switch_device(device)
                                        and not is_light_device(device)
                                    )
                                )
                            ]
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=True,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=(
                                    f"{len(fallback_candidates)} fallback "
                                    "target candidates"
                                ),
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                    resolution = resolve_device_candidate(
                        str(requested), fallback_candidates
                    )
                if resolution.target is not None:
                    target = dict(resolution.target)
                    target["_resolved_label"] = resolution.matched_name
                    targets.append(target)
                else:
                    resolution_errors.append(resolution.reason)

        unique_targets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for target in targets:
            device_id = str(target.get("id") or target.get("deviceId") or "")
            if not device_id:
                resolution_errors.append(
                    f"{target.get('label') or target.get('name')!r} has no device ID."
                )
            elif device_id not in seen_ids:
                seen_ids.add(device_id)
                unique_targets.append(target)
        if resolution_errors:
            data = {
                "success": False,
                "error": " ".join(resolution_errors),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        semaphore = asyncio.Semaphore(8)

        async def execute(target: dict[str, Any]) -> dict[str, Any]:
            device_id = str(target.get("id") or target.get("deviceId"))
            label = str(
                target.get("_resolved_label")
                or target.get("label")
                or target.get("name")
                or device_id
            )
            call_arguments = {
                "tool": "hub_call_device_command",
                "args": {
                    "deviceId": device_id,
                    "command": command,
                    **(
                        {
                            "waitFor": {
                                "attribute": "switch",
                                "expectedValue": command,
                                "timeoutMs": 5000,
                            }
                        }
                        if command in {"on", "off"}
                        else {}
                    ),
                },
            }
            started = time.monotonic()
            command_success = False
            verified: bool | None = None
            verification_message = ""
            try:
                async with semaphore:
                    result = await self.mcp.call_tool(
                        "hub_manage_devices", call_arguments
                    )
                command_success = self._tool_succeeded(result)
                message = result.text
                if command in {"on", "off"}:
                    wait_for = (
                        result.data.get("waitFor")
                        if isinstance(result.data, dict)
                        else None
                    )
                    verified = (
                        bool(wait_for.get("converged"))
                        if isinstance(wait_for, dict)
                        else False
                    )
                    verification_message = (
                        json.dumps(wait_for)
                        if isinstance(wait_for, dict)
                        else "Command response omitted waitFor confirmation."
                    )
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                logger.exception(
                    "High-level device command failed for %s", label
                )
            evidence_outcome = (
                "verified"
                if command_success and verified is True
                else "sent"
                if command_success
                else "failed"
            )
            self._record_evidence(
                "hub_manage_devices",
                call_arguments,
                success=command_success and verified is not False,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{command} {label}: {evidence_outcome}",
                supports_live_claim=True,
                evidence_kind="device_command_result",
            )
            success = command_success and verified is not False
            return {
                "id": device_id,
                "label": label,
                "room": room_name(target),
                "success": success,
                "command_sent": command_success,
                "verified": verified,
                "message": message,
                "verification_message": verification_message,
            }

        results = await asyncio.gather(*(execute(target) for target in unique_targets))
        succeeded = [item for item in results if item["success"]]
        failed = [item for item in results if not item["success"]]
        data = {
            "success": not failed and bool(succeeded),
            "command": command,
            "device_kind": kind,
            "matched": len(unique_targets),
            "executed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "complete": True,
        }
        return MCPToolResult(
            DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data
        )


__all__ = ["DEVICE_CONTROL_TOOL", "DeviceControlService"]
