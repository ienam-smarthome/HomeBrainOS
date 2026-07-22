from __future__ import annotations

from typing import Any, Iterable

from assistant_contracts import EntityResolutionResult, ResolvedTarget, ResolutionStatus
from control_agent_graph import ControlDeviceGraph, DeviceNode, DeviceResolution, GraphContext
from control_agent_intent import ControlTargetIntent


class EntityResolver(ControlDeviceGraph):
    """Single public device-resolution service for selected Hubitat devices.

    The existing graph remains the matching engine so current aliases, rooms,
    ordinals and speech normalisation retain identical behaviour.  This facade
    adds a stable typed contract, action-capability validation and an explicit
    trace that other assistant paths can adopt incrementally.
    """

    def __init__(
        self,
        devices: Iterable[dict[str, Any]],
        *,
        learned_aliases: dict[str, str] | None = None,
    ) -> None:
        super().__init__(devices, learned_aliases=learned_aliases)

    def resolve_for_action(
        self,
        target: ControlTargetIntent,
        *,
        action: str | None = None,
        context: GraphContext | None = None,
    ) -> tuple[DeviceResolution, EntityResolutionResult]:
        resolution = super().resolve(target, context=context)
        unsupported: list[DeviceNode] = []
        if action and resolution.nodes:
            unsupported = [node for node in resolution.nodes if not self.supports_action(node, action)]
            if unsupported:
                labels = ", ".join(node.label for node in unsupported)
                resolution = DeviceResolution(
                    nodes=[],
                    candidates=unsupported,
                    confidence=0.0,
                    method="unsupported-action",
                    reason=f"The resolved device does not support {action}: {labels}.",
                )
        elif action and resolution.candidates:
            supported_candidates = [
                node for node in resolution.candidates if self.supports_action(node, action)
            ]
            if supported_candidates:
                resolution.candidates = supported_candidates
            else:
                labels = ", ".join(node.label for node in resolution.candidates)
                resolution = DeviceResolution(
                    nodes=[],
                    candidates=list(resolution.candidates),
                    confidence=0.0,
                    method="unsupported-action",
                    reason=f"The candidate devices do not support {action}: {labels}.",
                )
        return resolution, self.contract(resolution, action=action)

    @staticmethod
    def supports_action(node: DeviceNode, action: str) -> bool:
        command = str(action or "").strip().lower()
        states = node.current_states
        metadata_parts: list[str] = []
        for key in ("capabilities", "commands"):
            value = node.raw.get(key)
            entries = value if isinstance(value, list) else [value]
            for entry in entries:
                if isinstance(entry, dict):
                    metadata_parts.extend(str(item) for item in entry.values())
                elif entry not in (None, ""):
                    metadata_parts.append(str(entry))
        metadata = " ".join(metadata_parts).lower().replace("_", " ")
        if command in {"on", "off"}:
            return "switch" in states or "switch" in node.types or "switch" in metadata
        if command == "set_level":
            return (
                "level" in states
                or "switch level" in metadata
                or "switchlevel" in metadata
                or "setlevel" in metadata.replace(" ", "")
            )
        return False

    def contract(
        self,
        resolution: DeviceResolution,
        *,
        action: str | None = None,
    ) -> EntityResolutionResult:
        if resolution.method == "unsupported-action":
            status = ResolutionStatus.UNSUPPORTED_ACTION
        elif resolution.nodes:
            status = (
                ResolutionStatus.RESOLVED_GROUP
                if len(resolution.nodes) > 1
                else ResolutionStatus.RESOLVED
            )
        elif resolution.ambiguous or len(resolution.candidates) > 1:
            status = ResolutionStatus.AMBIGUOUS
        else:
            status = ResolutionStatus.NOT_FOUND

        def target(node: DeviceNode) -> ResolvedTarget:
            supported = self.supports_action(node, action) if action else None
            return ResolvedTarget(
                device_id=node.id,
                label=node.label,
                room=node.room,
                types=sorted(node.types),
                confidence=resolution.confidence,
                match_reason=resolution.reason,
                supports_action=supported,
            )

        trace = [
            f"method={resolution.method}",
            f"confidence={resolution.confidence:.3f}",
            f"resolved={len(resolution.nodes)}",
            f"candidates={len(resolution.candidates)}",
        ]
        if action:
            trace.append(f"action={action}")
        return EntityResolutionResult(
            status=status,
            confidence=resolution.confidence,
            method=resolution.method,
            reason=resolution.reason,
            targets=[target(node) for node in resolution.nodes],
            candidates=[target(node) for node in resolution.candidates],
            trace=trace,
        )


__all__ = ["EntityResolver"]
