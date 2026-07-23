# Hubitat MCP AI 0.10.61

## Fixed

- Forces every Home Assistant add-on release to build a fresh runtime image by using the Supervisor-provided `BUILD_VERSION` as a Docker build argument.
- Bakes the running image version into `/app/.homebrain-build-version`.
- Makes the Web UI and API report the version from the running image rather than repository metadata alone.
- Adds standard Home Assistant image labels for version and architecture.

This addresses the mismatch where Home Assistant showed a newer installed add-on version while the running HomeBrain container still served an older Web UI release.
