# HomeBrainOS v0.18.173 — Generic read-gateway schema compatibility

## Live regression behind this release

The 28 October 2026 10:00:52 UTC Investigation V2 read of
Livingroom Light 2 (#7828) returned the correct Hubitat-reported
switch=off, level=30 snapshot, but took 23.566s. The 204-device
identity inventory took 23.299s, whereas hub_get_device took 141ms.
The relevant diagnostic was
`targeted_status.identity_lookup=filtered_schema_unusable`.

## Root cause

V2's filtered identity reader treated the absence of the optional
`properties` key on an otherwise open inner MCP gateway argument
object as a malformed schema. The source lookup was not attempted.
The production main Ask resolver already issues an allowlisted,
read-only hub_list_devices(labelFilter=...) lookup on generic gateways.

## Correction

- Accept an open object argument schema with no explicit `properties`
  or `required` keys; these omissions do not themselves forbid
  additional arguments.
- Continue to reject an explicitly closed inner argument schema
  without `labelFilter`, invalid field structure, non-object type,
  or malformed required-list values.
- Validate the ACTUAL read request, including the labelFilter, against
  the live wrapper schema instead of silently omitting that field
  during preflight.
- Require the positively advertised, read-only `hub_list_devices`
  operation and all previously implemented source validation: exactly
  one complete terminal filtered result with a matching friendly
  label and numeric ID, followed by a new direct `hub_get_device`
  response that independently attests that same ID.
- If any gate fails, use the existing complete verified inventory
  fallback. Never infer device identity from model text, a stale
  cache or a previous command receipt. No write path is modified.

## Regression coverage

Synthetic HTTP tests exercise the exact V2 question against both
fully described and generic open gateway argument schemas. Security
tests reject explicitly closed unadvertised filters, malformed
types/properties/required lists, ignored filters, wrong labels,
duplicate labels and unverified pagination.

## Live acceptance

Update to v0.18.173 and repeat:
"Read the current switch state and brightness level of Livingroom
Light 2 directly from Hubitat. Do not change anything."

If the server permits a generic filtered read and returns complete
identity pagination metadata, expect
`identity_scope=exact_label`,
`targeted_status.identity_lookup=filtered_unique_exact_label`,
`full_inventory_ms=0`, `planning_ms=0`, and a separate
source-backed switch+level status for device 7828.

If it falls back again, report `targeted_status.identity_lookup`.
This update is a schema compatibility fix; live latency and filtered
coverage remain to be confirmed on the actual server.
