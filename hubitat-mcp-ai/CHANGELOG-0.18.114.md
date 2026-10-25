# HomeBrainOS 0.18.114 — Restore investigation objective end-to-end

## Repeated live failure
On v0.18.113 a read-only "Why does Livingroom Light 1 sometimes stay ON?"
request completed in about 9.3s with "17 devices in Living Room" and no
app config, event history, source or log read. It had 2 model rounds and
only discovery/identity/inventory receipts. This is NOT resolved by the
previous 0.18.112 keyword-route fix or 0.18.113 causal claim validator:
the lower-level tool loop still exposed the inventory presenter and no
pre-final obligation required actual diagnostic evidence.

## Reviewed path and root causes
- API route AI interpretation -> host targeted-device override ->
  request-scoped effective objective.
- HomeBrain snapshot shortcuts -> orchestrator tool catalog ->
  model discovery and read tool execution.
- No-tool finalization -> completion checkpoint -> API evidence
  metadata and user answer.
- Existing model-routing tests validated intent selection but allowed
  the exact failed answer even when all source classes were missing.

## Implementation
1. The lower-level catalog can suppress `homebrain_device_inventory`
   for diagnostic read requests, including after tool-list refresh and
   expansion. Ordinary inventory questions retain the efficient shortcut.
2. Model-led investigations with inventory-only evidence get ONE more
   focused read-only evidence opportunity (not another keyword router).
   Allowed capabilities remain restricted to verified safe read gateways.
   No app/rule/device writes are permitted by the retry.
3. An early inventory response is rejected at the agent-output boundary.
   It becomes an accurate incomplete answer rather than a false diagnosis
   if the bounded retry cannot collect relevant evidence.
4. Host scope overrides preserve a real `model_led` effective objective and
   target instead of silently discarding interpretation.
5. Clone/virtual sensor reports cannot be treated as independent physical
   occupancy evidence without verifying their parent and configured input.
   The specifically mentioned Livingroom Soft Sensor should not be used as
   an independent cause; if it is referenced in actual app configuration,
   that connection still needs validation rather than being ignored blindly.

## Regression verification
Simulate the exact identity/inventory receipts and a fake agent returning
"17 devices in Living Room". Assert:
- no definitive inventory response to an investigation;
- tool registry cannot re-offer the inventory presenter mid-investigation;
- retry chooses only allowed read-source gateways;
- normal room inventory and quick state questions remain fast;
- no write confirmation/actions are fabricated.
No Hubitat state is changed by these tests.

## Remaining live acceptance
Repeat the original read-only light question. Confirm the response contains
actual app configuration, history and decision evidence, or a clearly
unresolved statement when the necessary sources cannot be acquired.
No finite tool loop can guarantee a physical cause, but it must never
substitute a room list for the requested diagnostic task.
