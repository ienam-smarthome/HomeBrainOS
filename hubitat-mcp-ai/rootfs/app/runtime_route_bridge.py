from __future__ import annotations

from typing import Any

from fastapi.responses import HTMLResponse

from cancellable_requests import install_cancellable_ask
from device_intelligence_webui import patch_page


def install_runtime_route_bridge(application: Any):
    """Rebind final HTTP routes after outer deterministic controllers are installed.

    The preserved composition root installs the cancellable /api/ask endpoint and
    captures the then-current ask handler. Release-specific outer controllers must
    therefore rebind that endpoint after wrapping application.ask. The home route is
    also recreated so it reads application.VERSION at request time instead of keeping
    a release value captured during entrypoint_core import.
    """

    api = application.app

    # Recreate the cancellable API route so it captures the final deterministic ask
    # chain, including guarded app management.
    request_registry = install_cancellable_ask(application)

    # Replace only the HTML home endpoint. PWA assets registered by the core remain
    # intact; the page itself always renders the current runtime release.
    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.get("/", response_class=HTMLResponse)
    async def runtime_home() -> HTMLResponse:
        version = str(getattr(application, "VERSION", api.version))
        api.version = version
        page = application.render_page(
            str(application.OPTIONS.get("web_title") or "Hubitat MCP AI"),
            version,
        )
        return HTMLResponse(
            patch_page(page),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @api.on_event("shutdown")
    async def cancel_runtime_requests() -> None:
        await request_registry.cancel_all()

    return request_registry


__all__ = ["install_runtime_route_bridge"]
