# HomeBrainOS V2 alpha.123 — readable answers without losing evidence

**Status:** merged in [PR #1683](https://github.com/ienam-smarthome/HomeBrainOS/pull/1683) at `cb936fc26fe90cf1f1bba448a84b1323cac63ffa` after **11/11 exact-head CI checks green**. Installed source-real acceptance and measured answer-quality improvement remain pending. V2 only. No V1, native API, device write, approvals, model routing or automatic source selection changes.

## Source-real observation motivating this change

Installed alpha.122, 16 November 2026, PRIVATE first-answer review for an uncoached 12-hour power-history request on a new device type:
- Exactly two successful read-only current-request receipts, 0 failures: targeted `hub_list_devices` inventory and `homebrain_read_device_monitor` 12-hour power archive. The configured historian **was actually used**, unlike the previous alpha.121 light/TRV examples.
- Original monitor scope: 144 five-minute positions; 72 report-containing, 40 carried-forward, 32 explicitly null; 1–81 W saved-bin range; latest non-zero saved value 1 W in the 09:00 GMT bin with a monitor-received report at 09:01:29.610 GMT. Current hub snapshot reported switch ON and 1 W. Missing bins do not prove device OFF or a reporting outage.
- Five model rounds, provider-reported 282,659 input and 5,650 output tokens; 35.6-second server elapsed; no writes. The answer contained a large two-column evidence matrix, raw ISO/HTML `<br>`, fenced JSON in a Markdown table, repeated technical summaries. The captured screen displayed raw markup and code, making the useful data difficult to read.
- The drafts and some final prose **overstated** that the switch remained ON throughout, the telemetry stream paused, and compressor activity was physically verified. An ON **current** snapshot and binned power data cannot establish historical switch continuity or a physical cause of missing records. Full PRIVATE receipts are retained outside this note.

## General changes

1. **Model-led answer-first presentation:** The existing bundled answer-presentation skill now instructs the model to lead with the direct finding, use readable UK time, add only relevant observations and unknowns, avoid paragraphs in evidence tables, raw JSON, HTML and repetition. No deterministic answer writer and no device-specific response template.
2. **Existing evidence review/final audit:** Internal prompts retain all substantive source/causal checks but explicitly tell the model to correct unsupported claims while preserving a compact user-facing reply. Gaps are missing saved data, not proof of an outage; sampled power is not physical proof of a mechanism; an inventory switch snapshot is not 12-hour continuous evidence. No additional model rounds, forced native reads or weaker native command permissions.
3. **Safe V2 display:** Extend the existing DOM-only Markdown-subset renderer so literal legacy `<br>` or `<br/>` becomes a real line break **only** in the displayed answer. All other HTML stays inert visible text: no `innerHTML` or script execution. Long 2-column tables have a more legible label column and wrapping. The original model answer, copy, evidence receipts and PRIVATE technical export remain byte-for-byte unchanged.

## Tests and acceptance

- Source presentation skill loaded into the agent and generic wording contract checked.
- Focused safe renderer regression (optional Node with no packages) ensures literal HTML does not execute and legacy line breaks display. Existing first-answer UI and source-review/native safety tests must remain green.
- After green CI and install, ask a fresh uncoached read-only question (any domain) and capture original PRIVATE JSON/screenshot. Measure legibility **and** factual source scope, time-zone, absent-vs-null-vs-held bins, current-vs-history boundary, model rounds/tokens and server elapsed. No unmeasured quality/latency improvement claims.
- Rollback: revert the V2 PR; original receipts and V1 are unchanged.
