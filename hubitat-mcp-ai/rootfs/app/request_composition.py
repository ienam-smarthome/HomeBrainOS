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
        "route_shadow_observer",
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
        self._wrapped: weakref.WeakKeyDictionary[Callable[..., Any], AskHandler] = (
            weakref.WeakKeyDictionary()
        )
        self._assignment_count = 0
        self._original_class: type[ModuleType] | None = None
        self._tracking_class: type[ModuleType] | None = None

    def start(self) -> "AskLayerRegistry":
        if self._tracking_class is not None:
            return self

        registry = self
        original_class = self.application.__class__

        class TrackedApplicationModule(original_class):
            def __setattr__(self, name: str, value: Any) -> None:
                if name == "ask" and callable(value):
                    value = registry._instrument_assignment(value)
                super().__setattr__(name, value)

        self._original_class = original_class
        self._tracking_class = TrackedApplicationModule
        self.application.__class__ = TrackedApplicationModule

        current = getattr(self.application, "ask", None)
        if callable(current):
            self.application.ask = current
        return self

    def stop(self) -> None:
        if self._original_class is None:
            return
        self.application.__class__ = self._original_class
        self._original_class = None
        self._tracking_class = None

    def _instrument_assignment(self, handler: Callable[..., Any]) -> AskHandler:
        if getattr(handler, "__homebrain_layer_wrapper__", False):
            return handler
        cached = self._wrapped.get(handler)
        if cached is not None:
            return cached

        frame = inspect.currentframe()
        caller = frame.f_back.f_back if frame and frame.f_back else None
        source_module = str((caller.f_globals.get("__name__") if caller else "") or "")
        source_function = str((caller.f_code.co_name if caller else "") or "")
        self._assignment_count += 1
        record = AskLayerRecord(
            name=getattr(handler, "__name__", "ask"),
            tier=classify_ask_layer(source_module, source_function),
            source_module=source_module,
            source_function=source_function,
            order=self._assignment_count,
        )
        self._records.append(record)

        @functools.wraps(handler)
        async def observed(request: Any) -> dict[str, Any]:
            execution = _ACTIVE_ASK_EXECUTION.get()
            if execution is not None:
                execution.traversed.append(record)
            answer = await handler(request)
            if execution is not None and execution.answering is None:
                execution.answering = record
            return answer

        observed.__homebrain_layer_wrapper__ = True
        observed.__homebrain_layer_record__ = record
        self._wrapped[handler] = observed
        return observed

    def records(self) -> list[dict[str, Any]]:
        return [record.as_dict() for record in self._records]

    def summary(self) -> dict[str, Any]:
        counts = Counter(record.tier for record in self._records)
        return {
            "layer_count": len(self._records),
            "tiers": dict(sorted(counts.items())),
            "layers": self.records(),
        }


def install_ask_layer_tracking(application: ModuleType) -> AskLayerRegistry:
    registry = AskLayerRegistry(application)
    registry.start()
    application.ask_layer_registry = registry
    return registry


class AskLayer:
    """Named middleware layer used by explicit request composition."""

    def __init__(
        self,
        name: str,
        factory: AskLayerFactory,
    ) -> None:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("AskLayer name must be non-empty")
        if not callable(factory):
            raise TypeError("AskLayer factory must be callable")
        self.name = clean
        self.factory = factory

    def wrap(self, next_handler: AskHandler) -> AskHandler:
        handler = self.factory(next_handler)
        if not callable(handler):
            raise TypeError(f"AskLayer {self.name!r} did not return a callable handler")
        handler.__homebrain_ask_layer__ = self.name
        return handler


def compose_ask_layers(
    base_handler: AskHandler,
    *layers: AskLayer,
    base_name: str = "base-handler",
) -> AskHandler:
    """Compose ordered middleware while preserving legacy outermost-first order."""

    if not callable(base_handler):
        raise TypeError("Base ask handler must be callable")
    handler = base_handler
    names = [str(base_name or "base-handler")]
    for layer in layers:
        handler = layer.wrap(handler)
        names.append(layer.name)
    handler.__homebrain_composed_layers__ = tuple(names)
    return handler


class AskCompositionBuilder:
    """Capture legacy installers and republish them as one explicit composition.

    Each captured installer may still assign ``application.ask`` internally for
    compatibility with standalone tests. The builder restores the previous handler
    immediately, then records the produced wrapper as an explicit ``AskLayer``.
    Calling :meth:`finalize` publishes exactly one composed handler.
    """

    def __init__(self, application: ModuleType, *, base_name: str = "base-handler") -> None:
        self.application = application
        self.base_handler: AskHandler = application.ask
        self.base_name = str(base_name or "base-handler")
        self._layers: list[AskLayer] = []
        self._names: set[str] = set()
        self._finalized = False

    def capture(
        self,
        name: str,
        installer: Callable[[], InstallerResult],
    ) -> InstallerResult:
        if self._finalized:
            raise RuntimeError("Cannot capture after request composition is finalized")
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("Captured layer name must be non-empty")
        if clean in self._names:
            raise ValueError(f"Duplicate captured layer name: {clean}")

        previous = self.application.ask
        result = installer()
        installed = self.application.ask
        self.application.ask = previous
        if installed is previous:
            raise RuntimeError(f"Installer {clean!r} did not assign application.ask")

        def factory(next_handler: AskHandler, *, installed_handler: AskHandler = installed) -> AskHandler:
            closure = inspect.getclosurevars(installed_handler)
            legacy_candidates = [
                value
                for value in closure.nonlocals.values()
                if callable(value) and value is not installed_handler
            ]
            legacy = next(
                (
                    value
                    for value in legacy_candidates
                    if value is previous
                    or getattr(value, "__homebrain_layer_wrapper__", False)
                    or hasattr(value, "__homebrain_composed_layers__")
                ),
                None,
            )
            if legacy is None:
                raise RuntimeError(
                    f"Installer {clean!r} does not retain a replaceable downstream handler"
                )

            async def composed(request: Any) -> dict[str, Any]:
                if next_handler is legacy:
                    return await installed_handler(request)

                original_wrapped = self.application.ask
                try:
                    self.application.ask = next_handler
                    return await installed_handler(request)
                finally:
                    self.application.ask = original_wrapped

            composed.__name__ = getattr(installed_handler, "__name__", clean.replace("-", "_"))
            return composed

        self._layers.append(AskLayer(clean, factory))
        self._names.add(clean)
        return result

    def finalize(self) -> AskHandler:
        if self._finalized:
            return self.application.ask
        handler = compose_ask_layers(
            self.base_handler,
            *self._layers,
            base_name=self.base_name,
        )
        self.application.ask = handler
        self._finalized = True
        return handler


async def run_with_ask_layer_tracking(
    handler: AskHandler,
    request: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    execution = _AskExecution(traversed=[])
    token = _ACTIVE_ASK_EXECUTION.set(execution)
    try:
        answer = await handler(request)
    finally:
        _ACTIVE_ASK_EXECUTION.reset(token)
    return answer, {
        "traversed": [record.as_dict() for record in execution.traversed],
        "answering": execution.answering.as_dict() if execution.answering else None,
    }


__all__ = [
    "AskCompositionBuilder",
    "AskHandler",
    "AskLayer",
    "AskLayerRecord",
    "AskLayerRegistry",
    "AskLayerTier",
    "classify_ask_layer",
    "compose_ask_layers",
    "install_ask_layer_tracking",
    "run_with_ask_layer_tracking",
]
