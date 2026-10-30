# v0.18.266 — V3 D2 final-synthesis claim handoff (shadow-only)

## Evidence from the 0.18.265 live test

The 30 October Bathroom Light 1 and Bathroom Light 2 read-only replay recovered 20 source-timed switch observations and 20 collector-reception copies. It returned 48 witness rows, including four independently source-timed sensor reports, but no verified original ON-command issuer. It executed 27 tools in 11 model rounds with a 93.1-second response. The model consumed 79.3 seconds of provider processing. The recovery-claim pilot was offered three times, yet the **terminal** draft contained no structured claim envelope, and the legacy digest replaced it.

An absent terminal envelope does not by itself prove the model never emitted one: the final answer coordinator may repair or rewrite an earlier draft. Also, repeated recovery offers are not a final-output requirement.

## Change

- The existing two-target, independently source-timed Historical Journal witness gate now also supplies a **final synthesis** claim format request, positioned **after** all other synthesis instructions.
- This final no-tool message explicitly asks for one `homebrain-claims` fence after the natural-language explanation using current verified witness IDs. Earlier checkpoint prompts remain optional.
- New allowlisted, privacy-safe counters distinguish a final prompt actually offered (`v3_claim_pilot_final_offered`), an envelope in the **first** final synthesis model draft (`v3_claim_first_draft_present` or `v3_claim_first_draft_missing`) and the existing terminal envelope present/valid/rejected or missing.
- The same bounded, source-qualified typed evidence examples are reused; no duplicate tool execution, new permission or ungrounded command source is authorized.
- Regression tests cover the positive two-target source packet, single-target, collector-only and absent journal cases, natural-language-first ordering, and counter privacy.

## Safety and acceptance

**No publication change.** The source-first legacy digest remains authoritative for this pilot, and structured claims do not certify unrelated narrative text. `setLevel` after an ON report, notified listeners, reception-only sensor patterns and missing upstream logs cannot prove the originating controller. No writes to Hubitat, Home Assistant, drivers, rules or devices.

Run all CI. After a clean merge, reproduce the same read-only Bathroom question and inspect the new counters. If a valid envelope appears, next review whether the model's **prose** is evidence-supported before considering conditional natural-language finalization. If envelopes remain absent even in the first draft, rework the model output protocol rather than stacking additional prompt patches. Compare tool count, response time and source coverage against earlier baselines.
