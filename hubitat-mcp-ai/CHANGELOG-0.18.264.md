# v0.18.264 — Causal Investigator V3 Stage D1: source-witness claim attestation (shadow)

**Publication remains unchanged.** This release does not turn off or weaken the deterministic Historical Journal digest and does not change any Hubitat automation or Home Assistant installation.

## Baseline
The v0.18.263 live test used 27 read-only tools over 10 model rounds (55.7 seconds), versus v0.18.262's 31 calls/11 rounds (55.5 seconds), with 48 typed witnesses, 4 source-timed inputs and **zero matched ON-command issuers**. The new source-feasibility choices improved scope but did not make previously missing original upstream commands observable. The finalizer still replaced the native model's answer. Unlike the previous test, the shadow did not report any source-time token references in the native draft, so simply disabling the fallback would be unsafe.

## Claim-evidence contract
- New pure `causal_claim_attestation.py` validates only **versioned, structured claims** against actual V3 witness IDs and role/clock/provenance fields. It does not interpret unstructured English using keyword routing.
- Supported claim categories are source-timed ON/OFF state, independently source-timed sensor input, recorded app-issued command, recorded command-to-matching-state witness pair, and explicit upstream-origin uncertainty.
- Immediate command attribution requires a source-attested same-target recorded `issued_on` with app ID and matching source-timed state witness in the V3 ledger. An observed `setLevel` after ON, bridge state reporter, app listener, collector-only timestamp, forged witness ID, unrelated target or wrong app cannot satisfy it.
- The contract **does not certify prose** or a root cause, even when every structured claim is supported. `prose_verified=false` is always explicit. A valid immediate Hubitat command proves only a recorded local command preceding a report, not the upstream reason or physical ACK.
- The parser accepts an optional bounded `homebrain-claims.v1` JSON code fence and returns only limited, allowlisted reason codes. Raw draft, device names, times, commands, URLs and secrets are not copied to the new request metrics.

## Shadow pilot
- For the existing *two-target Historical Journal digest replacement route only*, the evidence instruction provides a small source-witness ID catalog and invites an **optional** model-authored claim envelope. This is experimental; it does not authorize tools or cause the publication of the envelope.
- On terminal reconciliation, the shadow validator counts missing/present, valid/invalid, supported/rejected claim metadata by request. The **existing digest/ledger output decision remains exactly as before**, regardless of pilot outcome.
- Other requests are not asked to emit metadata, avoiding code-fence pollution of ordinary natural-language answers.

## Tests and next gating decision
Positive and negative fixtures cover observed state, input, legitimate app command, matched command-to-state pair, later level adjustment, collector reception, wrong device, forged source, wrong app, incomplete envelope, bounded parser, request-only counters and unchanged legacy publication.

Only after a live trial shows the model can reliably emit witness-backed claims should Stage D2 consider separately validating or preserving model-authored natural language. Structured attestation on its own cannot prove that the rest of the prose is true; default publication must remain fail-safe.

No new MCP leaf, extra permission, live automation write or background polling. Full CI required before merging.
