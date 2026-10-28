# HomeBrainOS v0.18.170 — Fix targeted-read eligibility and explain fallback

## Live v0.18.169 regression

27–28 October Livingroom Light 2 (#7828) switch+level snapshot remained
source-correct (on, 30%, zero missing/validation issues), but V2 took
43.109s and used the legacy semantic full inventory:
- identity inventory 17.322s
- full 204-device inventory 21.093s
- model planning 4.512s
- resolution_method: semantic_verified_inventory

The exact request was "Read the current switch state and brightness level
of Livingroom Light 2 directly from Hubitat. Do not change anything."

## Root cause from code inspection

The verified-device resolver treated 'switch' as an ambiguous possible
device name because LivCAM socket (#7786) and FP2 Livingroom socket (#7787)
both have the generic driver name 'switch'. Earlier v0.18.167 handling
covered 'switch state of <device>', but not coordinated attribute phrases
'switch state and brightness level of <device>'. The trusted resolver
therefore returned no unique candidate, and the V2 handler fetched the
complete state inventory and planned through the model.

## Correction and scope

- Extend host-level attribute qualifier grammar only for a bounded
  additional current-state clause (switch state **and** brightness level).
  Such a clause must lead directly to an independently matched full,
  unique friendly name. Genuine standalone ambiguous device requests
  ('check the switch and Livingroom Light 2') continue to reject.
- Regress the exact live question against a synthetic identity inventory
  containing both sockets with generic name 'switch'; verify it selects
  only #7828 and proceeds through the direct targeted Hubitat read
  without full inventory or AI planning.
- Surface bounded, operator-readable targeted_status diagnostics for
  candidate count, preflight, actual source RPC dispatch and reason for
  schema, ID, typed projection or question eligibility failure. Never
  include raw MCP response, credentials or opaque tool text.
- Preserve the strict V2 read-only access and no-write contract.
  A successful source read requires the original verified device ID,
  a live MCP READ manifest, and an approved typed attribute projection.

## Remaining limitations

- Cold identity inventory can still take 17–20 seconds. This release aims
  to eliminate the redundant full inventory and model planning when the
  exact question and live MCP source qualify. Warm read-only identity
  reuse remains scoped to a verified, generation-valid 90-second cache.
- If the live hub_get_device operation is not advertised, cannot
  validate its nested arguments, or does not attest #7828 and its current
  attributes, the fast path falls back safely. This will now be observable
  through semantic_diagnostics.targeted_status.outcome.
- Synthetic CI tests do not establish live latency or physical effects.

## Live acceptance

Update the add-on to 0.18.170, then repeat the identical read-only question:
"Read the current switch state and brightness level of Livingroom Light 2
directly from Hubitat. Do not change anything."

Expect resolution_method=verified_targeted_current,
semantic_diagnostics.targeted_status.outcome=verified_targeted_source,
full_inventory_ms=0 and planning_ms=0 when the MCP source qualifies.
If the legacy route still runs, report targeted_status fields; they now
identify the reason for exclusion instead of requiring guesswork.
