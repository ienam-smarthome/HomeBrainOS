from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
AskLayerFactory = Callable[[AskHandler], AskHandler]
InstallerResult = TypeVar("InstallerResult")


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
    "compose_ask_layers",
]
