# HomeBrainOS V2 alpha.92 — source-coverage aware final audit

**Date:** 14 November 2026

## Intent

Improve factual grounding and causal calibration for already-read MCP receipts without adding a new model inference/review pass, forcing any MCP read, or hardcoding a lighting/heating incident.

A source-real alpha.91 evaluation showed that a model could accurately find the command issuer and relevant motion events but then overclaim:
- That no other same-type commands existed in the **returned** event history, even when multiple such events were present.
- That a broad **requested** log interval had been exhaustively inspected even when thousands of entries matched but only a limited page was returned.
- That an internal controller decision was proven from a current configuration page and one correlated sensor, despite multiple selected inputs and potentially unobserved override conditions.

The failure class is **claim-to-returned-source inconsistency**, not an argument for expanding default source discovery or giving a model more rounds.

## Changes

1. Extend the **existing**, tool-free final claim audit to explicitly compare every material negative, exclusivity or definitive-cause claim with original successful MCP source receipts.
2. Add a bounded receipt **navigation index**, reusing only content already returned to the connected model:
   - **Event name counts:** exact event names and counts from the existing source-derived client event-attribute scope. Distinguish any one proximate event from *all* returned events of that name. No historical absence inference.
   - **Native log page coverage:** preserve source `matched`, `count`, actual `len(entries)`, and oldest/newest **as-reported** returned entry timestamps. Timezone is not inferred from offset-less native log time strings. A log query returning a limited page is not proof of complete requested-window coverage.
   - **Controller selected inputs:** bounded selected participants already available in the sanitised `client_config_source_map`. This can expose multiple relevant inputs or an override switch to the model without automatically reading any of them. Configuration does not verify historic state or event-specific callback.
3. First causal review reminds the model to consider these existing sources before deciding on further read-only sources. Final claim audit checks that current settings and command issuer are not promoted to an independently verified internal trigger.
4. Source-scope index never returns raw log messages, UI markup, credentials, full event rows, invented timestamps or new remote evidence. Unavailable fields stay unavailable. Existing 16-receipt cap and bounded group counts remain.
5. Keep **alpha.91 review and bounded follow-through lifecycle unchanged**. No extra model round, tool calls, provider/fallback path, changed default model, write approval bypass, local model, or V1 changes.

## Tests

New synthetic tests model four same-type commands, two selected controller inputs plus a separate override, a requested log interval with 2,303 matching entries but three returned entries, and secret-bearing raw messages. They assert original receipt immutability, bounded counts, no secret leakage, no implicit timezone conversion, incomplete coverage and unchanged failed/malformed source handling. Existing audit orchestration and read-only safety tests remain.

Synthetic tests do not claim that a deployed model will obey an audit prompt or that actual Hubitat device state is confirmed. Source-real A/B evaluation must compare first answers against original receipts and watch input token cost for this additional compact index.

## Acceptance next

Install alpha.92 in **HomeBrainOS V2 Preview** only, keep the chosen provider constant, and collect a genuinely new read-only causal first answer with PRIVATE Technical JSON. Check:
- actual original event names and their counts versus any `no other`/only-one claim;
- native log query request window vs matched count vs returned entries vs returned timestamp range;
- all materially relevant selected controller inputs rather than a single sensor narrative;
- reporter versus command issuer versus event-specific internal condition;
- source-review/follow-through and final-audit model rounds, tokens, read-only source receipts, time, and explicit unresolved causes.

Treat repeated source-real answer quality, not synthetic test counts, as the acceptance criterion.
