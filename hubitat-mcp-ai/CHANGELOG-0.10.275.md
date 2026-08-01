# Hubitat MCP AI 0.10.275

- Extracted Hub Information Driver discovery, refresh, polling, reconciliation,
  units, and snapshot shaping into `HubInfoService`.
- Preserved the authoritative firmware, resource, and full snapshot scopes and
  their existing local tool contract.
- Kept firmware polling bounded at ten attempts and resource polling bounded at
  six attempts, with the existing half-second interval in production.
- Preserved cached identity enrichment when compact live device responses omit
  labels, capabilities, or other metadata.
- Kept tool visibility and live-claim authority in the orchestrator, evidence
  recording and payload bounding in `ToolExecutor`, and user-facing wording in
  the deterministic presenter.
- Retained thin orchestrator delegates for existing tests and integrations that
  call the local Hub Info handler or its pure helpers directly.
- Added direct regression coverage for invalid scopes, unique device matching,
  nested results, identity merging, resource units, command failures, missing
  devices, and bounded unsuccessful polling.
