# Hubitat MCP AI changelog

## 0.10.61

- Bakes Home Assistant `BUILD_VERSION` into every add-on image so each release invalidates Docker build cache.
- Reads the running image version from `/app/.homebrain-build-version` instead of trusting repository metadata alone.
- Adds Home Assistant image labels for the build version and architecture.
- Keeps the non-PWA ingress UI and guarded deterministic app controller.

## 0.10.60

- Removes the installable PWA layer from the Home Assistant ingress page.
- Unregisters legacy HomeBrain service workers and deletes `hubitat-mcp-ai-shell-*` caches.
- Keeps a temporary cleanup worker endpoint so previously registered workers can retire themselves.
- Adds cache-clearing response headers while preserving the guarded app-controller route.

## 0.10.59

- Replaces the stale cache-first PWA service worker with network-only navigation handling.
- Deletes all historical `hubitat-mcp-ai-shell-*` caches when the new worker activates.
- Adds a one-time browser cache reset and an `X-HomeBrain-Version` response header.
- Prevents Home Assistant ingress from displaying an older HomeBrain release after the add-on has updated.

## 0.10.58

- Rebinds the final `/api/ask` endpoint after the guarded app controller is installed, so explicit app commands cannot fall through to generic AI device handling.
- Rebuilds the Web UI home route from the live runtime version instead of a release value captured during `entrypoint_core` import.
- Adds no-store headers to the rendered HomeBrain page so the displayed version cannot remain frozen after an add-on update.

## 0.10.57

- Adds deterministic Hubitat app inventory with enabled, disabled, and unknown counts.
- Adds guarded app enable/disable commands through `hub_set_app_disabled`.
- Requires clickable confirmation before every app write and resolves confirmed actions by exact App ID.
- Verifies changes from the write response and an independent `hub_list_apps` read-back when available.
- Keeps ordinary device enable/disable commands outside the app controller unless the request explicitly says app or application.

## 0.10.56

- Adds a live, deterministic MCP app-management capability diagnostic.
- Reports app inventory, app state read-back, and app enable/disable write support separately.
- Includes a developer-ready suggested MCP contract when support is missing.
- The diagnostic is read-only and never changes an app.

Previous release history is preserved in `CHANGELOG-history-through-0.10.55.md`.
