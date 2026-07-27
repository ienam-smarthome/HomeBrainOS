from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from answer_guard_registry import AnswerGuardRegistry


def run(coro):
    return asyncio.run(coro)


def test_registry_runs_terminal_routes_before_delegation_in_order():
    calls = []

    async def base(request):
        calls.append("base")
        return {"message": "base"}

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)

    async def first(request):
        calls.append("first")
        return None

    async def second(request):
        calls.append("second")
        return {"message": "terminal"}

    registry.register_terminal_route("first", first)
    registry.register_terminal_route("second", second)
    registry.install()

    answer = run(app.ask(SimpleNamespace(query="test")))
    assert answer == {"message": "terminal"}
    assert calls == ["first", "second"]


def test_registry_delegates_once_then_runs_guards_in_order():
    calls = []

    async def base(request):
        calls.append("base")
        return {"message": "start", "value": 1}

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)

    async def first(request, answer):
        calls.append("guard-one")
        answer["message"] += ":one"
        return answer

    async def second(request, answer):
        calls.append("guard-two")
        answer["message"] += ":two"
        return answer

    registry.register_guard("one", first)
    registry.register_guard("two", second)
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="test")))
    assert answer == {"message": "start:one:two", "value": 1}
    assert calls == ["base", "guard-one", "guard-two"]


def test_registry_rejects_duplicate_names_and_late_registration():
    async def base(request):
        return {"message": "ok"}

    async def guard(request, answer):
        return answer

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_guard("same", guard)
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register_guard("same", guard)

    registry.install()
    with pytest.raises(RuntimeError, match="after installation"):
        registry.register_guard("late", guard)


def test_registry_detects_untracked_ask_mutation_before_install():
    async def base(request):
        return {"message": "ok"}

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)

    async def replacement(request):
        return {"message": "changed"}

    app.ask = replacement
    with pytest.raises(RuntimeError, match="changed before"):
        registry.install()


def test_catalogue_preserves_cross_kind_registration_order():
    async def base(request):
        return {"message": "ok"}

    async def route(request):
        return None

    async def guard(request, answer):
        return answer

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_guard("guard-one", guard)
    registry.register_terminal_route("route-one", route)

    assert registry.catalogue() == [
        {"name": "guard-one", "order": 0, "kind": "answer-guard"},
        {"name": "route-one", "order": 1, "kind": "terminal-route"},
    ]
