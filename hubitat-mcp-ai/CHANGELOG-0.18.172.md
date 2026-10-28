# HomeBrainOS v0.18.172 — Production-compatible verified filtered identity

## Live failure: v0.18.171

On 28 October 2026 at 09:45 UTC, V2 correctly reported
Livingroom Light 2 (#7828) switch=off and level=30 via a 166ms direct
hub_get_device read, but still took 24.581s overall. A 204-device
identity-only inventory took 24.357s. Its diagnostic identified the
reason: targeted_status.identity_lookup=filter_not_advertised.

Production HomeBrain's own DeviceQueryService already performs
hub_read_devices/hub_list_devices with a fixed labelFilter argument,
even when the gateway's generic nested args schema does not enumerate
that one field. v0.18.171's V2 gate refused that established read contract
before calling the endpoint.

## Correction

Use a *host-owned, fixed, read-only* production compatibility contract
for hub_list_devices(labelFilter=...). It is accessible only after:
- An exact, bounded single-device current switch/brightness question.
- Live tool discovery advertises hub_list_devices under hub_read_devices.
- The gateway is classified READ and not destructive/mutating.
- Every other requested argument passes the actual nested schema check.
- The response explicitly reports one source-matched device, a decimal
  ID, a unique matching friendly label, total=1 and hasMore=false with
  terminal pagination; only then is filtered identity accepted.
- The follow-up live hub_get_device response independently attests the
  same ID and supports the requested state attributes.

The new diagnostic field targeted_status.filter_contract distinguishes
live_schema from host_allowlisted_production_read_contract. No model
output, unverified or stale cache, guessed identifier or write permission
may authorize this path. If the server ignores the filter, returns multiple
devices, omits pagination completeness, or rejects the known argument, V2
falls back to the established verified 204-device inventory path.

## Tests

Regression tests cover the legacy generic schema with working
labelFilter, an ignored filter and unfiltered 204-device response,
explicit denied READ/writable tool, absent hub_list_devices operation,
and existing exact-label/duplicate/partial/mismatch cases.

## After deploying

Repeat the unchanged read-only test:
"Read the current switch state and brightness level of Livingroom Light 2
directly from Hubitat. Do not change anything."

If source filtering and pagination are supported, expect:
- semantic_diagnostics.identity_scope=exact_label
- targeted_status.filter_contract=host_allowlisted_production_read_contract
- targeted_status.identity_lookup=filtered_unique_exact_label
- full_inventory_ms=0, planning_ms=0
- schema_validated_hub_get_device state read matching #7828

If fallback persists, inspect targeted_status.identity_lookup. Automated
test success alone does not establish an actual latency improvement or
independent physical lighting state.

No Hubitat device commands or automation writes were performed during
development.
