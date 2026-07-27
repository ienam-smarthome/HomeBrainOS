from __future__ import annotations

from typing import Any

from semantic_home_query_router import install_semantic_home_query_router


class _ApplicationProxy:
    """Expose application services while isolating legacy ask installation."""

    def __init__(self, application: Any, ask: Any) -> None:
        self._application = application
        self.ask = ask

    def __getattr__(self, name: str) -> Any:
        return getattr(self._application, name)


def build_semantic_home_query_terminal_route(application: Any):
    """Adapt the semantic home wrapper to a registry terminal route."""

    passthrough = object()

    async def passthrough_ask(request: Any):
        del request
        return passthrough

    proxy = _ApplicationProxy(application, passthrough_ask)
    install_semantic_home_query_router(proxy)
    installed = proxy.ask

    async def terminal_route(request: Any):
        answer = await installed(request)
        return None if answer is passthrough else answer

    return terminal_route


__all__ = ["build_semantic_home_query_terminal_route"]
