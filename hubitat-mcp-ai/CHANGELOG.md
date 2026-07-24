# Hubitat MCP AI changelog

## 0.10.67

- Wires the enhanced Hub health tiles into the actual final `application.ask` response chain.
- Promotes database size from the old note into a dedicated tile in the live Web UI.
- Shows installed firmware and the precise software-update state, including the available version when supplied by Hubitat.
- Uses the MCP response already attached by request tracing and does not make a duplicate hub call.

## 0.10.66

- Shows the Hubitat software update state as a dedicated **Software update** tile in Hub health.
- Displays the installed firmware as **Installed firmware** and includes the available version when an update exists.
- Promotes Hubitat database size from a note into its own **Database size** tile.

## 0.10.65

- Adds an **Apps** smart shortcut beside **Rules** in the HomeBrain Web UI.
- The shortcut sends the deterministic command `List apps`.
- Injects the shortcut at the final runtime rendering layer so existing Web UI composition remains unchanged.

## 0.10.64

- Retries `hub_update_firmware` exactly once when HomeBrain has independently verified a fresh backup but the MCP firmware guard still reports `BACKUP REQUIRED`.
- Waits four seconds for the MCP backup index to settle before retrying.
- Never creates a second backup or repeats the user confirmation during the retry.
- Reports a specific backup-index-lag result when the retry is still rejected.

## 0.10.63

- Removes the `mcp_tool_catalogue.py` startup handler that reset the running application to `0.10.56`.
- Keeps the version baked into `/app/.homebrain-build-version` as the sole runtime authority.
- Adds a startup regression proving the MCP tool catalogue installer cannot mutate application or API versions.
- Keeps the authoritative rendered-version diagnostic introduced in 0.10.62.

## 0.10.62

- Rewrites the Web UI's embedded JavaScript version after every renderer and UI patch has completed.
- Adds `/api/runtime-version` with baked, application, API and rendered versions for direct diagnosis.
- Fails loudly if the generated HomeBrain page does not contain exactly one replaceable version declaration.
- Keeps the baked container version as the single authoritative release value.

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
