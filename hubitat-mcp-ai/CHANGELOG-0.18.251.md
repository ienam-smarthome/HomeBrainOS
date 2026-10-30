# v0.18.251 — Unified investigation consumes all verified event history

## What changed

- The original unified MCP investigation bridge now reads **both** the low-level `hub_list_device_events` receipts and detailed `homebrain_device_history` receipts. Previously it required low-level event rows even when the authoritative event rows survived only in the deterministic history wrapper.
- The bridge binds derived history to an independently verified targeted device lookup, including sensors discovered during the investigation rather than only devices named in the original question. Unresolved and ambiguous names cannot authorize causal event records.
- Native and deterministic presentations of the same source event are de-duplicated so intervals and correlations are not double-counted.
- The existing original-agent read-only model follow-up can now fire when real multi-device histories were retrieved but no independent input history was checked. When an input history is checked and upstream command ownership remains unresolved, the same bounded model read-choice opportunity advances toward controller dependencies, execution logs, command provenance or installed app logic.
- Source attestation does not establish upstream initiation. No command in the returned bounded sample is **not** proof of external control. The model retains freedom to choose its own next safe MCP read.

## Validation and safety

- New tests cover summary-only native receipts with real derived events, independent sensor discovery, deduplication, ambiguous device identities, failed/mutating source rejection and causal uncertainty.
- No Hubitat writes, permissions, model routing-by-device-name, new MCP gateway or background tasks.
- This enables additional causal reads in the original model tool loop; it does not certify that every incident has reconstructable historical command provenance or that all possible dependencies are discoverable from Hubitat.

Merge only after all required GitHub Actions checks are green. Update the Home Assistant add-on independently.
