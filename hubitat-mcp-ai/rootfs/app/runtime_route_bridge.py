from __future__ import annotations

import json
import re
from typing import Any

from fastapi.responses import HTMLResponse, Response

from cancellable_requests import install_cancellable_ask
from device_intelligence_webui import patch_page


PWA_CLEANUP_SERVICE_WORKER = r"""self.addEventListener('install',event=>{self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('hubitat-mcp-ai-shell-')).map(key=>caches.delete(key)))).then(()=>self.registration.unregister()).then(()=>self.clients.claim()));});
"""

PWA_REMOVAL_SCRIPT = r"""
<script>
(() => {
  if ('caches' in window) {
    caches.keys()
      .then(keys => Promise.all(keys.filter(name => name.startsWith('hubitat-mcp-ai-shell-')).map(name => caches.delete(name))))
      .catch(() => {});
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations()
      .then(registrations => registrations.forEach(registration => {
        const worker = registration.active || registration.waiting || registration.installing;
        const script = String(worker?.scriptURL || '');
        if (script.includes('service-worker.js')) registration.unregister().catch(() => {});
      }))
      .catch(() => {});
  }
})();
</script>
"""

_VERSION_DECLARATION = re.compile(
    r'(const\s+TITLE\s*=\s*.*?,\s*VERSION\s*=\s*)("(?:\\.|[^"\\])*")',
    flags=re.S,
)


def remove_pwa_markup(page: str) -> str:
    """Remove installable-PWA markup and registration from the ingress page."""

    page = re.sub(r'<link\s+rel=["\']manifest["\'][^>]*>\s*', '', page, flags=re.I)
    page = re.sub(r'<link\s+rel=["\']apple-touch-icon["\'][^>]*>\s*', '', page, flags=re.I)
    page = re.sub(r'<meta\s+name=["\'](?:mobile-web-app-capable|apple-mobile-web-app-capable|apple-mobile-web-app-status-bar-style|apple-mobile-web-app-title)["\'][^>]*>\s*', '', page, flags=re.I)
    page = re.sub(
        r'<script>\s*\(\(\)\s*=>\s*\{.*?serviceWorker\.register\(["\']service-worker\.js["\']\).*?\}\)\(\);\s*</script>\s*',
        '',
        page,
        count=1,
        flags=re.I | re.S,
    )
    return page


def enforce_rendered_version(page: str, version: str) -> str:
    """Replace the renderer's embedded VERSION value with the live image version.

    Older composition modules can retain a release constant captured during import.
    The final HTTP layer is authoritative and rewrites the JavaScript VERSION value
    after every other Web UI patch has run.
    """

    encoded = json.dumps(str(version))
    rewritten, count = _VERSION_DECLARATION.subn(
        lambda match: match.group(1) + encoded,
        page,
        count=1,
    )
    if count != 1:
        raise RuntimeError("HomeBrain page did not contain one replaceable VERSION declaration")
    return rewritten


def install_runtime_route_bridge(application: Any):
    """Rebind final HTTP routes after outer deterministic controllers are installed."""

    api = application.app

    # Recreate the cancellable API route so it captures the final deterministic ask
    # chain, including guarded app management.
    request_registry = install_cancellable_ask(application)

    # Replace the HTML home endpoint, runtime diagnostic, and legacy PWA asset routes.
    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None)
            in {"/", "/service-worker.js", "/manifest.webmanifest", "/api/runtime-version"}
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.get("/service-worker.js")
    async def retired_service_worker() -> Response:
        # Keep this endpoint temporarily so previously registered workers receive an
        # update that deletes HomeBrain caches and unregisters itself.
        return Response(
            PWA_CLEANUP_SERVICE_WORKER,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Service-Worker-Allowed": "./",
            },
        )

    @api.get("/api/runtime-version")
    async def runtime_version() -> dict[str, Any]:
        version = str(getattr(application, "VERSION", api.version))
        return {
            "success": True,
            "baked_version": str(getattr(application, "BAKED_VERSION", version)),
            "application_version": version,
            "api_version": str(api.version),
            "rendered_version": version,
        }

    @api.get("/", response_class=HTMLResponse)
    async def runtime_home() -> HTMLResponse:
        version = str(getattr(application, "VERSION", api.version))
        api.version = version
        page = application.render_page(
            str(application.OPTIONS.get("web_title") or "Hubitat MCP AI"),
            version,
        )
        page = remove_pwa_markup(patch_page(page))
        page = enforce_rendered_version(page, version)
        page = page.replace("</body>", PWA_REMOVAL_SCRIPT + "</body>", 1)
        return HTMLResponse(
            page,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Clear-Site-Data": '"cache"',
                "X-HomeBrain-Version": version,
            },
        )

    @api.on_event("shutdown")
    async def cancel_runtime_requests() -> None:
        await request_registry.cancel_all()

    return request_registry


__all__ = [
    "PWA_CLEANUP_SERVICE_WORKER",
    "PWA_REMOVAL_SCRIPT",
    "enforce_rendered_version",
    "install_runtime_route_bridge",
    "remove_pwa_markup",
]
