from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from execution_contract_bridge import execution_contract_guard


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def test_execution_contract_guard_preserves_message_and_adds_contract_metadata():
    request = SimpleNamespace(query="turn off the lamp")
    original = {
        "success": True,
        "route": "mcp-app-control",
        "message": "Lamp command accepted.",
    }

    answer = run(execution_contract_guard(request, original))

    assert answer["message"] == "Lamp command accepted."
    assert answer["execution_lane"] == "fast_control"
    assert answer["verification_state"] == "sent"
    assert "execution_lane" not in original


def test_registry_delegates_once_and_applies_execution_contract_guard():
    calls = []

    async def base(request):
        calls.append(request.query)
        return {
            "success": True,
            "route": "mcp-fast",
            "message": "Live status.",
        }

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_guard("execution-contract", execution_contract_guard)
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="status")))

    assert calls == ["status"]
    assert answer["message"] == "Live status."
    assert answer["execution_lane"] == "fast_read"
    assert answer["verification_state"] == "uncertain"
    assert handler.__homebrain_registry_catalogue__ == (
        {"name": "execution-contract", "order": 0, "kind": "answer-guard"},
    )


def test_public_entrypoint_places_execution_contract_in_final_read_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from answer_guard_registry import AnswerGuardRegistry" in source
    assert "from execution_contract_bridge import execution_contract_guard" in source
    assert 'read_execution_registry.register_guard(\n    "execution-contract",\n    execution_contract_guard,' in source
    assert '"read-execution-registry",\n    read_execution_registry.install,' in source
    assert "install_execution_contract_bridge" not in source
    assert source.index('"named-rule-status"') < source.index('"climate-metric-extrema"')
    assert source.index('"climate-metric-extrema"') < source.index('"execution-contract"')
