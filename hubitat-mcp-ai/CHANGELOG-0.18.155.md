# HomeBrainOS v0.18.155 — Question-bound Factual Answers and Verified Issuer Follow-up

The 27 October live Investigation V2 runs correctly verified devices and
retrieved evidence but all five model-planning calls timed out. Basic status
and last-ON/OFF questions waited for an unrelated causal investigation and
returned the same generic report.

## Changes

- **Question contract:** After independent live inventory identity resolution,
  recognise only complete, unambiguous, single-device factual question forms:
  current ON/OFF status or most recent ON/OFF event timestamps. Not an
  unrestricted word/verb router; mixed, multi-device, ambiguous and causal
  questions continue through the existing semantic/investigation paths.
- **Source-first factual execution:** Status questions read the current device
  snapshot only; last-event questions read the current device and bounded
  switch event history. Both retain exactly the existing live MCP schema,
  read-only effect, verified device-ID, source-projection and auth gates.
  No AI planning or synthesis is required after these reads.
- **Question-specific answers:** Status returns the actual read-time switch
  value. History separates last ON and last OFF reports, preserves UTC source
  timestamps and identifiers, and never equates reporting bridge with issuer.
  Missing history is not presented as evidence of no activity; physical state
  and historical completeness are not invented.
- **Controller evidence:** The causal path can now read a stored app
  configuration for an event-confirmed command issuer even when a current
  app catalogue has already supplied its friendly name. This fixes the
  Bedroom 3 Mesh #7103 / button app #3103 progression bottleneck while
  leaving app configuration as *current*, not historical execution proof.
- **Diagnostics:** Named factual responses now identify
  `verified_device_status` or `verified_device_history` in `answer_mode`,
  report `factual_objective` and reflect that the investigation model
  was not attempted.

## Scope and non-goals

This is a focused architectural increment, not proof of Claude-quality
causal reasoning or a production switch-over. Broad inventory and multi-device
questions still need the semantic planner; complex causal investigations may
still reach the 15-second model-planning timeout. Provenance of any retrieved
controller app configuration needs further live verification before drawing
historical conclusions.

Production V1, installed automations, write permissions and confirmation
rules remain unchanged. Investigation V2 remains explicitly opt-in and
read-only.

## Recommended live regression

1. "Is Livingroom Light 2 currently on or off?" — one current source read;
   no 15-second investigation planner call; reported read-time status.
2. "When did Livingroom Light 2 last turn on and off?" — two source reads;
   last ON/OFF timestamps and coverage warning; no investigation planner.
3. "Why did Livingroom Light 2 turn on?" — still causal, should not be
   downgraded to status or short history.
4. "Why is Bedroom 3 Mesh offline while MQTT says connected?" — read-time
   health, unfiltered event fallback and identified issuer config if live
   read schema supports it. Do not claim physical reachability or causality
   from MQTT connected.
5. A mixed or multi-device question — no silent single-device factual answer.

Synthetic regression tests use fake MCP clients and forbid writes and model
calls on the factual path. Live-device results must still be reviewed before
claiming production readiness.
