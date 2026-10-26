# HomeBrainOS v0.18.152 — Verified-device evidence-first orchestration

A v0.18.151 live test recovered 19 timestamped records for Bedroom 3 Mesh
(device 7103) but took 119 seconds. Two distinct model calls were serialised:
the initial intent classification, and a 40-second round to propose reads.
The latter did not improve the evidence; two additional successful calls
returned no new source facts, after which atomic-claim verification and
narrative synthesis rejected claims or fell back. Repeated speculation
about a physically online device misread hub MQTT session status.

## Architectural changes

- **Skip redundant first AI call when identity is already verified.** If
  the actual user question matches exactly one full Hubitat identity and a
  freshly fetched source inventory has separately proven completeness, the
  opt-in V2 test route proceeds to host-gated device investigation without
  a preliminary semantic model call. It does not use keywords, hardcoded
  device IDs, or AI-selected identity. Broad/multiple/ambiguous device
  requests continue through the semantic objective planner.
- **No unsupported second synthesis phase after fruitless reads.**
  When additional model-suggested operations return no new typed records
  or source identities, V2 preserves all canonical event records and commands
  through deterministic host-grounded synthesis, and does not call the
  provider for atomic-claim verification/repair/narrative. Speculative
  model hypotheses are not presented as verified interpretations.
- **Transparent diagnostics.** The dedicated response mode
  `verified_device_investigation` explicitly marks skipped preliminary
  classification and still reports planning rounds, model latency,
  executed reads, and evidence coverage.

## Safety and compatibility

A complete, fresh inventory is required before the automatic direct route
can assume a device name is uniquely resolved. Ambiguous/partial identity
cannot gain tool privileges. All reads still pass the existing MCP operation,
read-effect, target-ID, scope and schema gates. A direct single-device state
question may now receive an evidence investigation format instead of an
inventory-list format; multi-device rankings remain on semantic execution.

Synthetic tests assert the V2 endpoint never calls preliminary AI
classification for complete unique identity; broad queries still use it;
and duplicate target names do not bypass checks. An independent case replay
ensures an issued command survives a no-new-evidence stop without paid
atomic repair, unsupported physical claims or credential exposure.

No production V1 routing, Hubitat devices, apps, rules, or automation
state is modified. This release does not itself fix full-inventory latency,
historical retention gaps or guarantee a proven physical root cause.
