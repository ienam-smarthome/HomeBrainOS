from __future__ import annotations

from typing import Any

from fastapi.responses import HTMLResponse, Response

from cancellable_requests import install_cancellable_ask
from device_intelligence_webui import patch_page


NETWORK_ONLY_SERVICE_WORKER = r"""const VERSION='0.10.59';
self.addEventListener('install',event=>{self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('hubitat-mcp-ai-shell-')).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.origin!==self.location.origin)return;if(request.mode==='navigate'||url.pathname.endsWith('/')||url.pathname.includes('/api/')){event.respondWith(fetch(request,{cache:'no-store'}));return;}event.respondWith(fetch(request,{cache:'no-store'}).catch(()=>Response.error()));});
"""

CACHE_RESET_SCRIPT = r"""
<script>
(() => {
  const release = '0.10.59';
  const key = 'hmcp_runtime_cache_reset';
  if (localStorage.getItem(key) === release) return;
  localStorage.setItem(key, release);
  if ('caches' in window) caches.keys().then(keys => Promise.all(keys.filter(name => name.startsWith('hubitat-mcp-ai-shell-')).map(name => caches.delete(name)))).catch(() => {});
  if ('serviceWorker' in navigator) navigator.serviceWorker.getRegistrations().then(registrations => registrations.forEach(registration => registration.update())).catch(() => {});
})();
</script>
"""


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

    # Replace the HTML home endpoint and service worker. The previous PWA worker used
    # a cache-first fallback for the complete shell, which could keep an old release
    # header visible indefinitely under Home Assistant ingress.
    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None) in {"/", "/service-worker.js"}
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.get("/service-worker.js")
    async def runtime_service_worker() -> Response:
        return Response(
            NETWORK_ONLY_SERVICE_WORKER,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Service-Worker-Allowed": "./",
            },
        )

    @api.get("/", response_class=HTMLResponse)
    async def runtime_home() -> HTMLResponse:
        version = str(getattr(application, "VERSION", api.version))
        api.version = version
        page = application.render_page(
            str(application.OPTIONS.get("web_title") or "Hubitat MCP AI"),
            version,
        )
        page = patch_page(page).replace("</body>", CACHE_RESET_SCRIPT + "</body>", 1)
        return HTMLResponse(
            page,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-HomeBrain-Version": version,
            },
        )

    @api.on_event("shutdown")
    async def cancel_runtime_requests() -> None:
        await request_registry.cancel_all()

    return request_registry


__all__ = ["CACHE_RESET_SCRIPT", "NETWORK_ONLY_SERVICE_WORKER", "install_runtime_route_bridge"]
