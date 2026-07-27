from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Awaitable, Callable

from assistant_contracts import RouteClass, VerificationOutcome


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_ROUTE_ALIASES: dict[str, RouteClass] = {
    "mcp-fast": RouteClass.FAST_READ,
    "mcp-rule-control": RouteClass.FAST_CONTROL,
    "mcp-app-control": RouteClass.FAST_CONTROL,
    "ollama+mcp": RouteClass.AGENT,
    "ai-evidence": RouteClass.AGENT,
}


def classify_legacy_route(route: Any, *, success: bool = True) -> RouteClass:
    normalised = str(route or "").strip().lower()
    if normalised in _ROUTE_ALIASES:
        return _ROUTE_ALIASES[normalised]
    if "control" in normalised or "write" in normalised:
        return RouteClass.FAST_CONTROL
    if "agent" in normalised or "ollama" in normalised or "evidence" in normalised:
        return RouteClass.AGENT
    if normalised.startswith("mcp") or "read" in normalised or "status" in normalised:
        return RouteClass.FAST_READ
    return RouteClass.FAST_READ if success else RouteClass.AGENT


def infer_verification_outcome(response: Mapping[str, Any]) -> VerificationOutcome:
    if response.get("post_state_verified") is True:
        return VerificationOutcome.COMPLETED
    technical = response.get("technical")
    if isinstance(technical, Mapping):
        if technical.get("post_state_verified") is True or technical.get("command_verified") is True:
            return VerificationOutcome.COMPLETED
        if technical.get("command_sent") is False:
            return VerificationOutcome.UNCERTAIN
    intent = str(response.get("intent") or "").lower()
    if "verified" in intent:
        return VerificationOutcome.COMPLETED
    if "accepted" in intent or (
        response.get("success") is True and "control" in str(response.get("route") or "")
    ):
        return VerificationOutcome.SENT
    if response.get("success") is False:
        return VerificationOutcome.FAILED
    return VerificationOutcome.UNCERTAIN


def annotate_execution_contract(response: dict[str, Any]) -> dict[str, Any]:
    """Annotate legacy responses using the canonical assistant contracts."""

    if not isinstance(response, dict):
        return response
    annotated = dict(response)
    route = classify_legacy_route(
        annotated.get("route"),
        success=bool(annotated.get("success", True)),
    )
    verification = infer_verification_outcome(annotated)
    annotated.setdefault("execution_lane", route.value)
    annotated.setdefault("verification_state", verification.value)
    return annotated


async def execution_contract_guard(
    request: Any,
    response: dict[str, Any],
) -> dict[str, Any]:
    """Registry-compatible answer guard for canonical execution metadata."""

    del request
    return annotate_execution_contract(response)


def install_execution_contract_bridge(application: Any) -> AskHandler:
    """Compatibility installer retained for standalone consumers and tests."""

    original_ask: AskHandler = application.ask

    async def ask_with_execution_contract(request: Any) -> dict[str, Any]:
        response = await original_ask(request)
        return await execution_contract_guard(request, response)

    application.ask = ask_with_execution_contract
    application.execution_contract_bridge = ask_with_execution_contract
    return ask_with_execution_contract


__all__ = [
    "annotate_execution_contract",
    "classify_legacy_route",
    "execution_contract_guard",
    "infer_verification_outcome",
    "install_execution_contract_bridge",
]
