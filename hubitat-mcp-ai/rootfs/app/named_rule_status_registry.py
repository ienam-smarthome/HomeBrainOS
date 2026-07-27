from __future__ import annotations

from typing import Any

from named_rule_status_route import install_named_rule_status_route, parse_rule_status_target


def build_named_rule_status_terminal_route(application: Any, controller: Any):
    """Adapt the legacy named-rule status wrapper to a registry terminal route."""

    original_ask = application.ask
    installed = install_named_rule_status_route(application, controller)
    application.ask = original_ask

    async def terminal_route(request: Any):
        query = str(getattr(request, "query", "") or "")
        if parse_rule_status_target(query) is None:
            return None
        return await installed(request)

    return terminal_route


__all__ = ["build_named_rule_status_terminal_route"]
