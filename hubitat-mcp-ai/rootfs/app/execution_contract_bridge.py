from __future__ import annotations

from typing import Any, Awaitable, Callable

from execution_contracts import classify_legacy_route, infer_verification_state


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def annotate_execution_contract(response: dict[str, Any]) -> dict[str, Any]:
    """Add the new typed contract metadata while preserving legacy response fields."""

    if not isinstance(response, dict):
        return response
    annotated = dict(response)
    route = classify_legacy_route(
        annotated.get("route"),
        success=bool(annotated.get("success", True)),
    )
    verification = infer_verification_state(annotated)
    annotated.setdefault("execution_lane", route.value)
    annotated.setdefault("verification_state", verification.value)
    return annotated


def install_execution_contract_bridge(application: Any) -> AskHandler:
    original_ask: AskHandler = application.ask

    async def ask_with_execution_contract(request: Any) -> dict[str, Any]:
        response = await original_ask(request)
        return annotate_execution_contract(response)

    application.ask = ask_with_execution_contract
    application.execution_contract_bridge = ask_with_execution_contract
    return ask_with_execution_contract


__all__ = [
    "annotate_execution_contract",
    "install_execution_contract_bridge",
]
