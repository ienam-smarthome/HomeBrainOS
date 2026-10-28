# HomeBrainOS v0.18.169 — schema-gated targeted current status

## Live acceptance driving this change

In v0.18.168, Livingroom Light 2 (Hubitat ID 7828) was reported
switch=on and level=30 in a separate snapshot after setLevel(30).
The result was correct, with zero missing readings and validation issues,
but took 42.270s: 20.861s identity inventory, 17.689s full inventory
and 3.536s semantic planning for one known light.

## Architecture: proof-carrying targeted read

- Preserve the complete, unique-ID-checked, read-only identity inventory.
  Reuse only its bounded generation-valid 90-second snapshot on a warm request;
  writes invalidate the cache.
- An exact, independently verified single-device, current switch+brightness
  question may use a special narrow read contract. Neither ambiguous wording,
  other named devices, history, causal analysis nor write requests enter it.
- Before execution, inspect the live MCP gateway manifest: require
  hub_read_devices/hub_get_device declared as READ and validate exact
  deviceId/mode args against the advertised input schema.
- Read the device's current status once and require the returned payload to
  attest the same numeric ID. Project it through the existing typed V2
  device snapshot contract. Reject unavailable, malformed or wrong-ID reads;
  fall back to existing full inventory rather than fabricate values.
- Feed only this verified current snapshot into the established V2
  multi-attribute renderer. Keep missing switch/level explicitly unknown,
  and report source scope, ID, identity inventory time, targeted-read time,
  zero full-inventory pages and zero model planning for successful requests.
- The change does not affect Main Ask write execution, permissions or
  confirmations, and does not turn V2 into a device control interface.

## Coverage and limitations

Synthetic tests reproduce a successful current read, a missing brightness,
wrong device ID, write-capable tool manifest, undeclared operation and
an API-level request that must never call the full-inventory or model paths.

A cold identity audit may still require five pages (~20 seconds). A warm
request can avoid both full-inventory pagination and model planning.
Upstream Hubitat may not advertise an eligible hub_get_device read or may
return insufficient typed status, in which case the full old path remains.
No speed numbers for this release have been measured on the live hub.

## Acceptance after deployment

Repeat the same read-only question in the V2 panel:
"Read the current switch state and brightness level of Livingroom Light 2
directly from Hubitat. Do not change anything."

Check:
- resolution_method = verified_targeted_current
- semantic_diagnostics.full_inventory_ms = 0
- semantic_diagnostics.planning_ms = 0
- semantic_diagnostics.read_source = schema_validated_hub_get_device
- source-backed values at inventory_query.reported_device_values
Repeat within 90 seconds to check warm identity reuse. No write is needed.
