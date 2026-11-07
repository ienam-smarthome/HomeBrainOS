# HomeBrainOS v0.18.451 — Generic claims-v2 offline shadow validator

## Why

Installed v0.18.449 live evidence showed the model could retrieve correct
records but still publish bridge->external-cause leaps, overbroad command
absence, inactive motion described as activity and an irrelevant historical
controller correction. v0.18.450 addressed these at final prose checkpoints;
it passed GitHub CI but still awaits source-real installed acceptance.

A user-supplied Claude `claims_v2.py` prototype and accompanying `test_claims_v2.py` (13 isolated tests)
were reviewed. The proposed claim-first approach aligns with the permanent
Answer Quality roadmap and partially existing V1 witness ledger, typed
attestation and narrow incident publication, but the prototype itself
accepted fake no-record claims, unverified command timestamps, invalid
interval pairs and model-selected context bypasses. It did not translate
actual V1 source roles or evidence classes. Shipping it unchanged as a
publisher would introduce new unsupported factual paths.

## General implementation

- New pure, dependency-free `claim_evidence_contract.py`: typed claim envelopes,
  deterministic validation, computed intervals/deltas, and a bounded
  source-grounded render for offline comparative development.
- `packet_from_v1_ledger` translates actual `causal-witness-ledger.v1`
  witnesses: `state-report` switch records with known reported ON/OFF,
  `issued-command` with Hubitat command provenance, `input-report`
  exact sensor values; collector timestamps remain unqualified.
- Use `command-issuer`, not `initiator`, for app-issued commands;
  neither a command nor a listener notification attests the upstream cause.
- Require real offset-aware clocks, role-compatible exact values, correct
  entity and trusted focal event identity. Context is valid only for
  separately authorised event keys, never merely because a model labels
  it context.
- Require compatible state-report ON->OFF (or supported equivalent)
  intervals, and finite same-unit observed numeric deltas. Elapsed time
  is code-computed from verified source clocks; never substitute a model
  numeric estimate.
- `absent_in_scope` demands a successful checked source window, nonzero
  pages examined, a true zero-result exact filter and typed query target.
  An adapter admits only `windowVerified` exact absolute native
  device-event rows with correct timestamp, target ID, attribute,
  `eventCount` and returned rows. It never claims complete retention.
- `assess_claims_shadow` exposes only summary counts and allowlisted
  rejection reasons, not confidential event data or model prose.
- Imported and adapted the 13 user-provided baseline tests, and added
  adversarial tests covering zero-page and no-window absence, event identity,
  listener roles, mixed clocks, source values, v1 schema and output leakage.

## Deliberate boundaries

This module is **offline shadow only**. It does not change the current
HomeBrain Ask path, replace the synthesiser, call a model, mutate devices,
query MCP endpoints, affect provider billing or relax write confirmations.
The deterministic render is a candidate floor for later comparison and
must not be promoted to live publication simply because its unit tests pass.
V1 `target_source_coverage` cannot prove a command absence; no new
coverage object is fabricated from that summary.

## Acceptance and next steps

Merged as [PR #1506](https://github.com/ienam-smarthome/HomeBrainOS/pull/1506) at commit `900243183915d98510a8b9f11fa51dd30328095d`, after all four CI workflows passed on tested head `c0f015ea2aeb55fd4ec1913fa01e915710269bbd`. The final full Python suite had **6,720 passing tests**; add-on smoke and metadata checks also passed. Installation of v0.18.450/451 and
fresh read-only HomeBrain Technical JSON remain unverified.

Follow up by deriving trusted focal/context keys from an existing final
answer planning receipt, connecting shadow-only claim envelope transport
without another model round or read request, and freezing held-out
cross-domain packets for measured supported-claim rate, unsupported
causation, deterministic downgrades, first-answer usefulness and latency.
Only graduate claim-first publication and retire redundant regex safeguards
after source-real acceptance. Do not claim a quality percentage from CI.
