from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_IDENTITY_FIELDS = ("id", "name", "label", "room")


@dataclass(frozen=True, slots=True)
class DeviceReadPlan:
    """One explicit hub_list_devices projection contract.

    Hubitat MCP has two different state representations:

    * summary mode exposes compact live state as ``currentStates``;
    * detailed mode exposes reported live state as ``attributes``.

    Requesting capabilities/commands promotes the server to detailed mode, even
    when ``format`` was otherwise summary.  Keeping that distinction here stops
    callers from asking for ``currentStates`` in a detailed projection and then
    treating the resulting records as if state had been returned.
    """

    detailed: bool
    fields: tuple[str, ...]
    state_field: str | None

    def arguments(
        self,
        *,
        limit: int,
        offset: int = 0,
        capability_filter: str | None = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {
            "detailed": self.detailed,
            "fields": list(self.fields),
            "limit": int(limit),
            "offset": int(offset),
        }
        if capability_filter:
            args["capabilityFilter"] = str(capability_filter)
        return args

    def has_state_container(self, device: dict[str, Any]) -> bool:
        """Return whether a projected record contains the promised state field.

        Presence of the field is the contract check.  An empty dict/list can be
        legitimate for a device that has not reported a state; a completely
        missing field means the projection shape is not the one the caller asked
        for and must not be interpreted as an authoritative empty state.
        """

        return self.state_field is None or self.state_field in device


def device_read_plan(
    *,
    include_states: bool,
    include_capabilities: bool = False,
    include_commands: bool = False,
) -> DeviceReadPlan:
    """Build the correct field projection for the Hubitat MCP list contract.

    The upstream server treats capabilities, attributes and commands as
    detail-only fields.  Therefore a read that needs capabilities plus live state
    must request ``attributes`` (the detailed representation), while a compact
    state-only read must request ``currentStates``.
    """

    detailed = bool(include_capabilities or include_commands)
    fields = list(_IDENTITY_FIELDS)
    if include_capabilities:
        fields.append("capabilities")
    state_field: str | None = None
    if include_states:
        state_field = "attributes" if detailed else "currentStates"
        fields.append(state_field)
    if include_commands:
        fields.append("commands")
    return DeviceReadPlan(
        detailed=detailed,
        fields=tuple(fields),
        state_field=state_field,
    )


__all__ = ["DeviceReadPlan", "device_read_plan"]
