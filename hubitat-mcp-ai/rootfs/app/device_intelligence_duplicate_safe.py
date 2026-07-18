from __future__ import annotations

from typing import Any

from device_intelligence_catalogue_safe import SafeCapabilityCatalogueDeviceIndex
from device_intelligence_index import (
    _device_id,
    _label,
    _normalise,
    _room_name,
)


def _descriptor(item: dict[str, Any]) -> str:
    label = _label(item) or "Unnamed device"
    device_id = _device_id(item)
    room = _room_name(item)
    details: list[str] = []
    if device_id:
        details.append(f"ID {device_id}")
    if room:
        details.append(room)
    return f"{label} ({', '.join(details)})" if details else label


class DuplicateAwareCapabilityCatalogueDeviceIndex(SafeCapabilityCatalogueDeviceIndex):
    """Safe selected-device index with actionable duplicate-name results.

    Hubitat can retain more than one mobile-app device with the same label after
    a phone/app reinstall. Exact-device matching must still refuse to guess, but
    returning the same label twice is not actionable. Ambiguous results include
    the Hubitat device ID and room so the user can identify the active record and
    remove the stale one from the MCP allowlist.
    """

    async def exact_device(
        self,
        requested_name: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        devices = await self.summary_devices()
        target = _normalise(requested_name)
        aliases = self._alias_map(devices)
        ids = aliases.get(target, set())

        if len(ids) == 1:
            wanted = next(iter(ids))
            return next(
                (item for item in devices if _device_id(item) == wanted),
                None,
            ), []

        if len(ids) > 1:
            matches = [item for item in devices if _device_id(item) in ids]
            matches.sort(key=lambda item: (_label(item).lower(), _device_id(item)))
            return None, [_descriptor(item) for item in matches]

        target_words = set(target.split())
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in devices:
            label = _label(item)
            normal = _normalise(label)
            if not normal:
                continue
            words = set(normal.split())
            overlap = len(target_words & words) / max(1, len(target_words | words))
            if target in normal or normal in target:
                overlap += 0.5
            if overlap > 0.15:
                scored.append((overlap, item))
        scored.sort(
            key=lambda entry: (
                -entry[0],
                _label(entry[1]).lower(),
                _device_id(entry[1]),
            )
        )
        return None, [_descriptor(item) for _, item in scored[:5]]


__all__ = ["DuplicateAwareCapabilityCatalogueDeviceIndex"]
