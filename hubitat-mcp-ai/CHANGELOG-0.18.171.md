# HomeBrainOS v0.18.171 — scoped verified identity for fast named status

## Live observation
On 28 Oct 2026 at 09:11 UTC, v0.18.170 correctly read Livingroom
Light 2 (#7828) as switch=off, level=30, but total time was 25.301s:
- 24.998s verifying all 204 device identities
- 179ms reading the known device through schema-gated hub_get_device
- 0ms full-state inventory and model planning

## Architectural improvement
The full identity inventory, verified total and 90-second generation-valid
cache remain in place for all broad, ambiguous and causal questions.
For one narrowly defined current switch+brightness question with an
explicit full friendly name, HomeBrain now tries a source-verified,
read-only labelFilter lookup *before* cold 204-device pagination.

The gateway must:
- advertise hub_list_devices and labelFilter in its LIVE read-only MCP
  schema and accept schema-validated, bounded arguments
- return exactly one identity with a numeric ID and an exact matching
  user-defined friendly label
- attest complete FILTERED coverage through explicit total=1,
  hasMore=false and a terminal page
- be followed by the existing schema-verified hub_get_device read whose
  returned ID must equal the identity lookup ID.

Unknown, duplicate, truncated, malformed, mismatched or unfiltered
identity responses are rejected; HomeBrain falls back to the complete
verified inventory route without silently expanding a device scope.
The filtered source never proves that the entire home inventory is
complete: result diagnostics distinguish
identity_scope=exact_label and home_inventory_complete=false from
full 204-device inventory completeness.

## Regression coverage
Synthetic tests confirm the exact question, page completeness, ambiguous
duplicates, missing filter capability, incorrect ID/label, ignored filter
returning 204 devices, and an HTTP flow that performs exactly two Hubitat
READs (filtered identity + device state) without full inventory or AI.

No Hubitat write path, permission, confirmation or device state is changed.
The existing Main Ask verified control path is unaffected.

## Live test
After deploying 0.18.171, repeat:
"Read the current switch state and brightness level of Livingroom Light 2
directly from Hubitat. Do not change anything."

On a supporting server, expect:
- semantic_diagnostics.identity_scope = exact_label
- semantic_diagnostics.home_inventory_complete = false
- semantic_diagnostics.full_inventory_ms = 0
- semantic_diagnostics.planning_ms = 0
- semantic_diagnostics.targeted_read_ms approximately the prior 179ms
- resolution_method = verified_targeted_current
- two separate, verified Hubitat reported attributes

If the filtered operation fails or is absent, the complete-inventory path
continues to run and a new read-only diagnostic records the rejection.
No live speed promise is made before deployment testing.
