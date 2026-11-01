# HomeBrainOS v0.18.316 — Stage 8.1 contextual completeness diagnostics

## Real phone test

On 1 November 2026, a consented read-only Live Shadow preflight for Hubitat device 7103 returned `blocked_incomplete_context`, with no device states. The original message conflated an explicit partial context, missing `idsComplete` or `totalDevices` metadata, a count mismatch and a malformed device list. The screenshot **does not establish which** condition actually occurred. The existing generic `live_context_is_complete` consumer accepts absent markers, while v0.18.315's experimental preflight additionally required `idsComplete: true` and a strictly integer `totalDevices`.

## Change

- Preserve strict blocking of **explicit** `truncated=true`, `partial=true`, `idsComplete=false`, malformed/oversized device array, incompatible declared total, multiple target-ID matches, and missing target state shape.
- Parse a bounded, numeric-string `totalDevices` when present (same semantics as the existing context reader); it still must exactly equal device-array length.
- When the completeness markers are merely missing/unrecognised and one exact target ID occurs in the returned subset, expose only sanitised, enumerated **provisional target-scoped reports**. `live_context_complete` remains false and `ready_for_read_only_investigation` remains false; no device absence, completeness, physical liveness, causal inference or producer provenance is asserted. An unseen target in an unverified subset is `target_not_seen_in_unverified_context`, NOT `target_not_found`.
- Return a bounded diagnostic object (static labels and source-list count): array well formed, identity marker category, count agreement category, explicit partial/truncation flag. Do not echo raw hub payload, app logs, arbitrary state strings, identifiers beyond the specifically selected device, addresses or secrets.
- Show those diagnostics and the provisional-vs-verified distinction in the existing consented mobile preflight.
- No additional MCP request, API endpoint, Cloud call, tool dispatch, persistence, device control or production publisher action.

## Evidence policy

The hub's reported current state can be useful even when **completeness** cannot be established, but a report from a returned subset is not proof the whole inventory was searched. The original strict `ready_for_read_only_investigation` gate remains false in this situation. The next live step must separately test actual historical source authenticity, timestamp/receipt distinctions and command-correlated acknowledgement before any evidence-led AI investigation or publication.

## Regression

Synthetic tests cover missing markers, bounded numeric-string totals, explicit partial contexts, declared total mismatches, repeated IDs, unknown target in a partial subset, private field redaction and endpoint consent/security. Full CI must pass before merge.

After update, repeat Live Shadow for 7103. Inspect the **Context integrity checks** and the reported state. Do not re-run the Cloud synthetic benchmark for this diagnosis.