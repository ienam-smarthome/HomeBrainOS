from __future__ import annotations

from typing import Any


DETAILED_DEVICE_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "label",
    "room",
    "attributes",
    "disabled",
    "lastActivity",
)


def detailed_device_arguments() -> dict[str, Any]:
    """Return the canonical live detailed-device inventory request."""
    return {
        "detailed": True,
        "format": "detailed",
        "fields": list(DETAILED_DEVICE_FIELDS),
    }


__all__ = [
    "DETAILED_DEVICE_FIELDS",
    "detailed_device_arguments",
]
