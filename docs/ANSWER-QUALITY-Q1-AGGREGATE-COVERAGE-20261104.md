# Q1 read-only whole-home aggregate coverage — 4 November 2026

## User-observed baseline

The exact registered `all_lights_on` prompt was submitted to HomeBrainOS
v0.18.401: `Which lights are currently on?` The displayed answer was
`No lights are currently on.` The API reported `success=true`, a
4,054 ms wall time, 2 model rounds, 2 tool calls, and a successful
`hubitat://context` bulk read containing **211 device records**.
The local `homebrain_active_lights` result was reported successful
with the field names `lights`, `count`, `definition`, `total_scanned`,
`complete`, `read_scope`, `scope`, `scopeVerified`, `requestedRoom` and
`matchedRooms`. **The Technical JSON did not expose the values of
`count`, `complete`, or `scopeVerified`.** Consequently this source
packet alone does not establish that the correct ON-light count
was zero, even though the local tool likely used the actual returned
count to produce the answer. The exact physical on/off situation
was not independently inspected. Do not score this sample as
confirmed wrong or independently verified correct.

## General evidence gap

Upstream `hubitat://context` validates inventory IDs, truncation,
pagination and source shape. It does not establish that every
recognized light or switch in its device list supplied a valid
`switch=on/off` value. Previously, the aggregate tools marked
`complete` solely from authoritative room-scope resolution.
Missing switch values were silently excluded from the ON list,
which makes `no lights on` potentially broader than the evidence.
Also, the sanitized Technical JSON exposed only a generic object
field-name summary, preventing independent confirmation of
the result's count and coverage.

## Scope of v0.18.402 correction

- One common `switch_state_coverage` routine counts eligible recognized
  light/non-light switch candidates, explicit ON, explicit OFF, and
  unknown/unusable switch states, filtered by authoritative room
  when requested. An OFF dimmer with a saved nonzero level stays OFF.
  A label-only Light Sensor without any switch semantics is not a
  controllable light candidate for this denominator.
- Retain the existing efficient bulk context and zero additional
  Hubitat/HA/router reads. Preserve the distinct inventory/room
  `complete` flag and add `state_coverage_complete` instead of silently
  redefining a previously used field.
- Publish only bounded typed aggregate counts, scope and coverage
  booleans to the Technical JSON, never the full private device list.
  If a tool receipt is missing or conflicting, reject a strong
  zero-active assertion rather than silently guessing.
- Before publication, qualify absolute no-light/no-switch claims
  if the returned count is nonzero, relevant candidate status is
  unknown, there are no identified eligible candidates, or the
  relevant source/scope isn't verified. Preserve a grounded zero
  answer for a verified complete ON=0 aggregate. Keep other
  model-authored prose untouched.

## Test and acceptance boundary

The prior response's 4.054s single wall-time result meets the
15-second routine-status target. It is not a sample distribution
or a certified model-first-attempt result; provenance flags
`model_delivery_verified`, `first_attempt_verified` and
`deployed_build_sha_verified` were all false.

After the changed version is installed, repeat the same unchanged
prompt as a **paired regression**. Confirm that Technical JSON
shows `aggregateState.onCount`, `candidateCount`,
`unknownStateCount`, `inventoryComplete`, `stateCoverageComplete`,
`totalScanned` and source scope; final prose must not claim
that missing switch values are OFF. If no on lights and coverage
is verified, a concise source-reported zero answer is valid.
The repetition is not a new independent first attempt.

CI verifies synthetic source invariants only. Live answer
quality, accuracy and performance after install are NOT MEASURED
until this repeat is supplied. Roll back if the general coverage
check erases known active devices, leaks private identities,
misclassifies retained OFF levels, or degrades room-scoped reads.

Do not add device-specific patches or claim whole-home physical
connectivity from a Hubitat reported-state snapshot.
