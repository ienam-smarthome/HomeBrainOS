# HomeBrainOS v0.18.149 — Live gateway discovery and actionable V2 reads

The .148 Bedroom 3 Mesh investigation correctly verified device 7103 but
timed out in semantic planning and made **zero MCP evidence reads**. The V2
evidence bootstrap silently required explicit operation enums and fields that
the live MCP's generic gateway schemas need not provide. No cause was
established, but the report did not expose why no read was attempted.

## Change

- V2 uses independently refreshed Hubitat target identity, and then resolves
  `hub_get_device` and `hub_list_device_events` using the current-session MCP
  manifest. Where the *read-only* `hub_read_devices` schema has no operation
  enum, the host can ask the advertised `hub_search_tools` for each exact
  operation and verify structured tool/gateway mappings.
- Operation discovery never invents gateway names, trusts model instructions,
  selects a write gateway, or bypasses a concrete gateway enum that excludes an
  operation. Read/write multi-membership is allowed only through a listed
  read gateway. Every resulting call is independently rechecked by the
  existing V2 schema, ID, effect and budget gates.
- Generic but permissive gateway schemas may now accept verified
  `deviceId` arguments without requiring an invented per-operation
  nested schema. A restrictive schema remains authoritative.
- The existing current-device snapshot and bounded history page are
  interpreted as *reported* status/event evidence, never proof of physical
  connectivity. Recognised Hubitat BST/GMT `lastSeen` values may inform a
  capped event window without asserting their telemetry clocks are correct.
- `bootstrap_diagnostics` in Investigation details records the status of
  each discovery and read attempt, including whether its live operation was
  unavailable or schema validation rejected it. No raw discovery response,
  gateway secrets or credentials are retained.
- Synthetic regressions reproduce generic `tools/list` gateways,
  duplicate read/write memberships, denial-by-enum, missing discovery,
  unrelated mappings, and a validated October BST last-contact timestamp.

The Claude MCP skill files informed the workflow, but do not confer
permission. Live MCP manifests and the central Hubitat Read/Write gate are
authoritative. No skill installs, rule creation, Hubitat commands or changes
to production V1 are part of this release.

## Remaining limitations

A model timeout still causes degraded, host-only evidence recovery rather
than a complete AI investigation. The initial full inventory may still be
slow. Deep app-driver causality, source completeness and physical/network
health are not proven merely by these reads. If a gateway's advertised schema
or live discovery cannot authorise a read, V2 now reports that limitation.
