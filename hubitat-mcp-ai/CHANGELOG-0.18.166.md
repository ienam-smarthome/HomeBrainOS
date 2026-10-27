# HomeBrainOS v0.18.166 — source-grounded multi-device V2 status

## Live regression (27 October 2026)
Following a correctly verified routine ON write to Hallway Light 1
(device 7829), V2 rejected a read-only question requesting both
Hallway Light 1 and Livingroom Light 2 (7828):
HTTP 422 'Named device is absent or ambiguous in current inventory'.
V2's trusted resolver already recognised up to four distinct devices,
but its semantic plan and inventory executor assumed a single named device.

## Architectural correction
- Extend typed semantic inventory plans with an optional bounded
  device_names array (1–4 exact distinct names), preserving legacy device_name.
- The host independently identifies device names in the original user
  question and verifies the proposed names against unique live Hubitat
  identities. Model-generated IDs or additional targets are never trusted.
- If an AI returns a joined name for a user question explicitly naming
  multiple devices, the host reconstructs the exact independently verified
  set, without broadening to room or whole-home device lists.
- Filter/read all selected devices separately from one current source
  snapshot, report missing values as unknown and preserve UTC timestamps
  and read-only limitations.
- Regression tests cover two distinct states, joined model names,
  duplicates, ambiguity, unrelated model-selected devices and existing
  single-device questions. An HTTP regression reproduces the original 422.

## Safety and remaining performance
No device commands or writes are enabled in the V2 panel.
The full verified inventory route may still take 30–40 seconds on a
cold two-device read; this release fixes correctness and target scope,
not pagination latency. The routine write path remains unaffected.

## Live acceptance
After deploying 0.18.166, ask V2:
'What is the current switch state of Hallway Light 1 and
Livingroom Light 2? Read both devices directly from Hubitat.
Do not change anything.'
Expect exactly two named devices with independently reported switch
states and no command evidence or writes.