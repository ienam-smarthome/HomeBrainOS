from __future__ import annotations

import contextvars
import functools
import inspect
import re
import weakref
from collections import Counter
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Awaitable, Callable, Literal, TypeVar


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
AskLayerFactory = Callable[[AskHandler], AskHandler]
InstallerResult = TypeVar("InstallerResult")
AskLayerTier = Literal[
    "safety-critical-write",
    "deterministic-fast-read",
    "semantic-evidence",
    "ai-synthesis",
    "answer-guard",
    "terminal-route",
    "request-observability",
]


@dataclass(frozen=True)
class AskLayerRecord:
    """One runtime-observed assignment in the maintained request pipeline."""

    name: str
    tier: AskLayerTier
    source_module: str
    source_function: str
    order: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier,
            "source_module": self.source_module,
            "source_function": self.source_function,
            "order": self.order,
        }


@dataclass
class _AskExecution:
    traversed: list[AskLayerRecord]
    answering: AskLayerRecord | None = None


_ACTIVE_ASK_EXECUTION: contextvars.ContextVar[_AskExecution | None] = (
    contextvars.ContextVar("homebrain_active_ask_execution", default=None)
)


def classify_ask_layer(
    source_module: str,
    source_function: str,
) -> AskLayerTier:
    """Classify a request layer into the documented safety-preserving tiers."""

    module = source_module.rsplit(".", 1)[-1]
    function = source_function.lower()
    if "terminal" in function or module in {
        "device_health_fast_route",
        "named_rule_status_route",
        "control_focus_octopus_energy",
    }:
        return "terminal-route"
    if module in {
        "home_summary_consistency_guard",
        "thermostat_summary_guard",
        "execution_contract_bridge",
        "hub_health_display_bridge",
        "climate_metric_extrema_route",
    } or "guard" in function:
        return "answer-guard"
    if module in {
        "request_tracing",
        "cancellable_requests",
        "conversation_context",
    }:
        return "request-observability"
    if module.startswith(("semantic_", "ai_evidence_")) or module in {
        "hybrid_assistant_mode",
    }:
        return "semantic-evidence"
    if (
        module.startswith(("ollama_", "mcp_agent_"))
        or module in {
            "fastpath_ai_handoff",
        }
        or "unified_agent" in function
        or (module == "entrypoint_core" and function == "<module>")
    ):
        return "ai-synthesis"
    if module.startswith(
        (
            "automation_rule_",
            "control_",
            "hub_backup_",
            "hub_firmware_",
            "hub_restart_",
            "named_app_",
            "named_rule_",
        )
    ) or module == "app_management_capability":
        return "safety-critical-write"
    return "deterministic-fast-read"


class AskLayerRegistry:
    """Capture every runtime assignment and instrument request traversal."""

    def __init__(self, application: ModuleType) -> None:
        self.application = application
        self._records: list[AskLayerRecord] = []
        self._names: Counter[str] = Counter()
        self._observed_handlers: weakref.WeakSet[AskHandler] = weakref.WeakSet()

    def _unique_name(self, source_module: str, source_function: str) -> str:
        module = source_module.rsplit(".", 1)[-1]
        function = re.sub(r"^install_", "", source_function)
        stem = re.sub(r"[^a-z0-9]+", "-", f"{module}:{function}".lower()).strip("-")
        self._names[stem] += 1
        suffix = self._names[stem]
        return stem if suffix == 1 else f"{stem}-{suffix}"

    def wrap(
        self,
        handler: AskHandler,
        *,
        source_module: str,
        source_function: str,
        name: str | None = None,
        tier: AskLayerTier | None = None,
    ) -> AskHandler:
        if not callable(handler):
            raise TypeError("application.ask must remain callable")
        if handler in self._observed_handlers:
            return handler

        effective_function = source_function
        if source_function == "<module>":
            effective_function = str(
                getattr(handler, "__name__", source_function)
            )
        record = AskLayerRecord(
            name=name or self._unique_name(source_module, effective_function),
            tier=tier or classify_ask_layer(source_module, effective_function),
            source_module=source_module,
            source_function=effective_function,
            order=len(self._records),
        )
        self._records.append(record)
        previous = self.application.__dict__.get("ask")
        previous_layers = tuple(
            getattr(previous, "__homebrain_ask_layers__", ())
        )

        @functools.wraps(handler)
        async def observed(request: Any) -> dict[str, Any]:
            execution = _ACTIVE_ASK_EXECUTION.get()
            token: contextvars.Token[_AskExecution | None] | None = None
            if execution is None:
                execution = _AskExecution(traversed=[])
                token = _ACTIVE_ASK_EXECUTION.set(execution)
            execution.traversed.append(record)
            execution.answering = record
            try:
                answer = await handler(request)
                if isinstance(answer, dict):
                    answering = execution.answering or record
                    answer["answering_layer"] = answering.name
                    answer["answering_layer_tier"] = answering.tier
                    answer["ask_layers_traversed"] = [
                        item.name for item in execution.traversed
                    ]
                return answer
            finally:
                if token is not None:
                    _ACTIVE_ASK_EXECUTION.reset(token)

        self._observed_handlers.add(observed)
        setattr(observed, "__homebrain_ask_layer__", record)
        setattr(
            observed,
            "__homebrain_ask_layers__",
            (record.name, *previous_layers),
        )
        return observed

    def records(self) -> list[AskLayerRecord]:
        return list(self._records)

    def response(self) -> dict[str, Any]:
        records = self.records()
        by_tier = Counter(record.tier for record in records)
        return {
            "success": True,
            "count": len(records),
            "tiers": dict(sorted(by_tier.items())),
            "layers": [record.as_dict() for record in records],
        }


class _AskTrackedModule(ModuleType):
    """Module subtype that observes assignments to the public ask handler."""

    def __setattr__(self, name: str, value: Any) -> None:
        registry = self.__dict__.get("_homebrain_ask_layer_registry")
        if name == "ask" and isinstance(registry, AskLayerRegistry):
            caller = inspect.currentframe()
            caller = caller.f_back if caller is not None else None
            value = registry.wrap(
                value,
                source_module=str(
                    (caller.f_globals if caller is not None else {}).get(
                        "__name__",
                        "unknown",
                    )
                ),
                source_function=(
                    caller.f_code.co_name if caller is not None else "unknown"
                ),
            )
        super().__setattr__(name, value)


def install_ask_layer_tracking(application: Any) -> AskLayerRegistry:
    """Observe all maintained ``application.ask`` assignments without reordering."""

    if not isinstance(application, ModuleType):
        raise TypeError("Ask-layer assignment tracking requires an application module")
    existing = application.__dict__.get("_homebrain_ask_layer_registry")
    if isinstance(existing, AskLayerRegistry):
        return existing

    registry = AskLayerRegistry(application)
    application.__class__ = _AskTrackedModule
    ModuleType.__setattr__(
        application,
        "_homebrain_ask_layer_registry",
        registry,
    )
    base_handler = registry.wrap(
        application.ask,
        source_module=str(getattr(application, "__name__", "app")),
        source_function="base_ask",
        name="base-application-route",
        tier="deterministic-fast-read",
    )
    ModuleType.__setattr__(application, "ask", base_handler)
    return registry


@dataclass(frozen=True)
class AskLayer:
    """Named request layer that wraps the next handler in the pipeline."""

    name: str
    factory: AskLayerFactory

    def wrap(self, next_handler: AskHandler) -> AskHandler:
        handler = self.factory(next_handler)
        if not callable(handler):
            raise TypeError(f"Ask layer {self.name!r} did not return a callable handler")
        return handler


def compose_ask_layers(
    base_handler: AskHandler,
    *layers: AskLayer,
    base_name: str = "legacy-route-stack",
) -> AskHandler:
    """Build one immutable request pipeline from inner to outer layers."""

    if not callable(base_handler):
        raise TypeError("The base ask handler must be callable")

    handler = base_handler
    order = [base_name]
    for layer in layers:
        handler = layer.wrap(handler)
        order.insert(0, layer.name)

    setattr(handler, "__homebrain_ask_layers__", tuple(order))
    return handler


class AskCompositionBuilder:
    """Capture compatibility installers behind one typed startup composition."""

    def __init__(
        self,
        application: Any,
        *,
        base_name: str = "core-request-stack",
    ) -> None:
        self.application = application
        self.base_handler: AskHandler = application.ask
        self.current_handler: AskHandler = application.ask
        self.base_name = base_name
        self.layers: list[AskLayer] = []
        self._layer_names: set[str] = set()
        self._finalized = False

    def capture(
        self,
        name: str,
        installer: Callable[[], InstallerResult],
    ) -> InstallerResult:
        """Run one compatibility installer and record its exact wrapper."""

        if self._finalized:
            raise RuntimeError("Cannot capture an ask layer after finalization")
        if not name or name in self._layer_names:
            raise ValueError(f"Ask layer name must be non-empty and unique: {name!r}")
        if self.application.ask is not self.current_handler:
            raise RuntimeError(
                f"Untracked application.ask mutation before layer {name!r}"
            )

        previous_handler = self.current_handler
        result = installer()
        installed_handler = self.application.ask
        if installed_handler is previous_handler:
            raise RuntimeError(f"Installer for ask layer {name!r} did not wrap application.ask")
        if not callable(installed_handler):
            raise TypeError(f"Installer for ask layer {name!r} produced a non-callable handler")

        def captured_factory(
            next_handler: AskHandler,
            *,
            expected: AskHandler = previous_handler,
            captured: AskHandler = installed_handler,
            layer_name: str = name,
        ) -> AskHandler:
            if next_handler is not expected:
                raise RuntimeError(
                    f"Ask layer {layer_name!r} was composed above an unexpected handler"
                )
            return captured

        self.layers.append(AskLayer(name, captured_factory))
        self._layer_names.add(name)
        self.current_handler = installed_handler
        return result

    def finalize(self) -> AskHandler:
        """Verify and publish the declared auxiliary request stack."""

        if self._finalized:
            return self.current_handler
        if self.application.ask is not self.current_handler:
            raise RuntimeError("Untracked application.ask mutation before finalization")

        composed = compose_ask_layers(
            self.base_handler,
            *self.layers,
            base_name=self.base_name,
        )
        if composed is not self.current_handler:
            raise RuntimeError("Captured ask composition did not reproduce the live handler")

        self.application.ask = composed
        self.current_handler = composed
        self._finalized = True
        return composed


__all__ = [
    "AskCompositionBuilder",
    "AskHandler",
    "AskLayer",
    "AskLayerFactory",
    "AskLayerRecord",
    "AskLayerRegistry",
    "AskLayerTier",
    "classify_ask_layer",
    "compose_ask_layers",
    "install_ask_layer_tracking",
]
