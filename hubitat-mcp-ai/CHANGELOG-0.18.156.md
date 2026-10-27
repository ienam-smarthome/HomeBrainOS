# HomeBrainOS v0.18.156 — Verified Identity Projection and Controller-Read Diagnostics

## Live regression prompting this change

On 27 October, v0.18.155 correctly answered Livingroom Light 2 status
in 18.929 seconds (18.488s inventory) and recent ON/OFF in
40.567 seconds (37.413s inventory). Both skipped all AI planning.
Bedroom 3 Mesh investigation spent 25.167s in inventory and then
timed out its optional 15-second AI investigation planner; the
controller app #3103 was identified but no app-config read occurred.

## Implementation

- **Two-stage fresh inventory:** Attempt a paginated, validated
  identity-only `hub_list_devices` projection first, selecting only
  ID, names and other identity fields. A uniquely named device from an
  independently complete source may proceed to the normal read-only
  device status/history flow. For broad/multi-device/unresolved scope,
  retrieve the original full state/capability inventory before
  semantic planning or a whole-house state answer.
- **No authority regression:** The small projection still checks
  total count, advancing page offsets, unique IDs and live generation.
  An incomplete projection cannot authorise a direct verified target;
  fallback provenance remains explicitly incomplete. The model and
  cached labels cannot grant device identity or MCP write permission.
- **Per-stage timing:** Named-device diagnostic metadata now includes
  `identity_inventory_ms`, `full_inventory_ms` and
  `inventory_projection`. The existing `inventory_ms` remains total
  elapsed lookup time, so actual gains or regressions can be measured
  without relying on assumptions about the upstream Hubitat runtime.
- **Controller read visibility:** An independently event-attested
  command issuer is still eligible for safe stored app-config lookup,
  but the host now records why the read was skipped when the live
  `hub_read_apps_code` manifest, nested arguments or effect rules do
  not permit it. Proposals rejected by the host are similarly
  reported. No unadvertised operation or invented schema is called.
- **Tests:** Synthetic tests cover complete and incomplete projected
  pagination, omission of state/capability/command metadata, exact
  name matching, and controller-read availability or denial.

## Scope and outstanding work

Performance gain is **not yet measured in live Hubitat**. The
identity-only stage may not be faster on a busy hub; broad questions
may incur an extra inventory fetch. No automatic cache substitution
or unchecked targeted write/read permissions were introduced.
The 15-second model-planner timeout on complex causal questions
remains, as do limits of historical coverage. A configured app name
is not proof of its event-time actions; even retrieved stored settings
would not establish historical causality.

Production V1 and all Hubitat write permissions, automations and
confirmation rules are unchanged. V2 remains opt-in, read-only.

## Live follow-up

1. Repeat status and history questions for Livingroom Light 2.
   Compare `inventory_ms` with the new identity/full timing fields.
   Verify zero model-planning rounds.
2. Retry the Bedroom 3 Mesh causal question. Read the new
   `bootstrap_diagnostics` `controller_config` entry to establish
   whether `hub_get_app_config` is live-permitted, unavailable, or
   host-rejected. A model timeout may still occur afterward.
3. Run a broader inventory query and verify `full_inventory_ms`
   is nonzero and the result is not based on identity-only metadata.
