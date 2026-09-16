# Hubitat MCP AI 0.10.436

## Changed

- Hub Information Driver discovery no longer refreshes the whole detailed device manifest on a cold request. It reuses an already-warm manifest when available and otherwise uses the Hubitat MCP server's targeted `labelFilter: "Hub Info"` lookup before refreshing the single Hub Info device.
- Firmware polling now treats two consecutive complete, identical post-`updateCheck` reads as settled. An already-up-to-date hub therefore does not automatically run to the final poll solely because its status/version correctly remain unchanged.
- Detailed device-manifest TTL now starts when the slow upstream refresh completes, rather than when it begins. A long Hubitat read therefore no longer produces a cache entry that is already stale as soon as it arrives.

## Why

These are structural read-path fixes rather than prompt or keyword shortcuts. They remove avoidable whole-home inventory pressure, stop stable firmware state from being mistaken for an unfinished refresh, and make the existing cache lifetime reflect the age of the data actually returned.

## Validation

- Added a cold Hub Info regression test that fails if discovery attempts a detailed-manifest refresh.
- Preserved the orchestrator firmware-refresh contract for lightweight MCP test clients while keeping the production `HubitatMCPClient` on the non-blocking cache peek path.
- Added a slow-refresh cache regression test proving a completed manifest receives its full configured TTL.
