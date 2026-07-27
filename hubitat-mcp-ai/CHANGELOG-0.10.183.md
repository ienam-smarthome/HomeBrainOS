# Hubitat MCP AI 0.10.183

## Final deterministic read-route migration

- Moves device-health, attention and whole-home priority reads into the shared
  read/execution registry.
- Moves grouped Octopus whole-house energy reads into the same registry.
- Removes two direct `application.ask` wrappers from `entrypoint_core.py`.
- Retains compatibility installers and keeps query-classification metadata hooks
  separate from answer routing.
