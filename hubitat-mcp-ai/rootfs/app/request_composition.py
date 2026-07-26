from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
AskLayerFactory = Callable[[AskHandler], AskHandler]


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


__all__ = ["AskHandler", "AskLayer", "AskLayerFactory", "compose_ask_layers"]
