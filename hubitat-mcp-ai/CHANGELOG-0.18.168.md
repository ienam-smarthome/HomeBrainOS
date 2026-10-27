# HomeBrainOS v0.18.168 — Verified brightness read-back and multi-attribute snapshots

## Live acceptance evidence

On 27 October 2026 at 23:42 UTC, Main Ask issued setLevel(30) to
Livingroom Light 2 (device 7828) and received a successful Hubitat waitFor
level=30 acknowledgement in 1.269 seconds. A later Main Ask targeted lookup
reported only switch=on but the model answer also asserted brightness=30%.
Investigation V2 separately spent ~40 seconds reading a full 204-device
inventory and returned a device row with no readings because the model
selected attribute=null.

The write passed at the Hubitat-reported acknowledgement level, but that
does not establish a separate fresh level=30 read or physical luminosity.

## Architectural improvements

1. **Multi-attribute V2 current-state contract**: a bounded, named read can
   return separate switch and level measurements. If a question explicitly
   asks both current switch state and brightness, the host corrects an
   incomplete one-attribute or null-attribute model plan; it does not
   reclassify causal, historical, filtered or ranked questions.
2. **Never fill from an older write**: source values come independently from
   the live Hubitat snapshot. Missing switch or level is explicitly
   reported as unavailable, not inferred from the preceding setLevel
   command or a model narrative. Typed per-device reported attribute values,
   missing_readings and coverage remain inspectable in the API result.
3. **Main Ask claim validation**: the existing same-turn current-state guard
   now treats inline phrases such as "brightness level of 30%" as numeric
   measurements. If only switch=on was actually returned, it corrects
   the narrative and discloses that no level was independently read.
   A fresh, matching level supports retaining the claim; contradictory
   level readings correct the answer rather than silently passing.
4. **Read-only security**: no additional Hubitat write permission, retry,
   automatic device control or cached-command substitution. Host-level
   verified identity and current inventory projection rules remain active.

## Validation and limits

Synthetic regression cases cover switch+level, explicit absent level, model
plan omission, inline brightness claims, same-turn matching and mismatching
readings, and non-current questions remaining outside the fast contract.

This release improves **accuracy**; it does not eliminate the ~36 second
cold V2 inventory scan. The next optimisation should replace the
full second inventory for a verified named target with schema-gated
Hubitat individual-device reads, without losing source freshness,
identity validation or read-only isolation.

## Live acceptance

After deploying v0.18.168:
1. In Main Ask, read the switch state and brightness of Livingroom Light 2.
   The answer must not assert 30% without fresh source level evidence.
2. In V2, ask "Read the current switch state and brightness level of
   Livingroom Light 2 directly from Hubitat. Do not change anything."
   Expect two separate fields and no invented value for missing data.
3. Review semantic_plan.attributes and
   inventory_query.reported_device_values in technical details.
4. Do not send a new light command merely to test these read-only changes.

Automated tests are not physical-device confirmation.
