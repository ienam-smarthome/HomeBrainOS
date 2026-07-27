from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
AnswerGuard = Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]]
TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class _RegisteredStep:
    name: str
    order: int


class AnswerGuardRegistry:
    """Ordered same-tier request registry with one published ask wrapper.

    Terminal routes may answer before the delegated handler. Answer guards run
    after delegation in registration order. Small route/guard functions remain
    independently testable while the application publishes only one wrapper.
    """

    def __init__(self, application: Any) -> None:
        self.application = application
        self._base_handler: AskHandler = application.ask
        self._terminal_routes: list[tuple[_RegisteredStep, TerminalRoute]] = []
        self._answer_guards: list[tuple[_RegisteredStep, AnswerGuard]] = []
        self._names: set[str] = set()
        self._installed = False
        self._next_order = 0

    def _step(self, name: str) -> _RegisteredStep:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("Registry step name must be non-empty")
        if clean in self._names:
            raise ValueError(f"Duplicate registry step name: {clean}")
        self._names.add(clean)
        step = _RegisteredStep(clean, self._next_order)
        self._next_order += 1
        return step

    def register_guard(self, name: str, guard: AnswerGuard) -> AnswerGuard:
        if self._installed:
            raise RuntimeError("Cannot register an answer guard after installation")
        if not callable(guard):
            raise TypeError("Answer guard must be callable")
        self._answer_guards.append((self._step(name), guard))
        return guard

    def register_terminal_route(self, name: str, route: TerminalRoute) -> TerminalRoute:
        if self._installed:
            raise RuntimeError("Cannot register a terminal route after installation")
        if not callable(route):
            raise TypeError("Terminal route must be callable")
        self._terminal_routes.append((self._step(name), route))
        return route

    def catalogue(self) -> list[dict[str, Any]]:
        rows = [
            {"name": step.name, "order": step.order, "kind": "terminal-route"}
            for step, _ in self._terminal_routes
        ]
        rows.extend(
            {"name": step.name, "order": step.order, "kind": "answer-guard"}
            for step, _ in self._answer_guards
        )
        return sorted(rows, key=lambda item: int(item["order"]))

    def install(self) -> AskHandler:
        if self._installed:
            return self.application.ask
        if self.application.ask is not self._base_handler:
            raise RuntimeError("application.ask changed before registry installation")

        async def registered_ask(request: Any) -> dict[str, Any]:
            for _, route in self._terminal_routes:
                answer = await route(request)
                if answer is not None:
                    return dict(answer)

            answer = dict(await self._base_handler(request))
            for _, guard in self._answer_guards:
                answer = dict(await guard(request, answer))
            return answer

        registered_ask.__name__ = "ask_with_answer_guard_registry"
        registered_ask.__homebrain_registry_catalogue__ = tuple(self.catalogue())
        self.application.ask = registered_ask
        self._installed = True
        return registered_ask


__all__ = [
    "AnswerGuard",
    "AnswerGuardRegistry",
    "AskHandler",
    "TerminalRoute",
]
