# Hubitat MCP AI v0.18.358 — distinguish device check-in from latest attribute event

## Real v0.18.357 evidence baseline
The first user-supplied post-upgrade read-only Freezer status result (2 Nov 2026, Gemma Cloud) was reported as Success, took **15,642 ms** end-to-end, used **4 model rounds, 4 tool calls** and correctly recorded the selected device ID 7105 with source-typed `switch=on`, `power=0`, `voltage=243`, `energy=604.958`. This **verifies the v0.18.357 selected-device receipt projection in the real app**, a concrete Q3 improvement over the earlier unable-to-audit v0.18.355 result. The single 15.642s measurement is above the 15-second status target but is neither median/p95 nor a matched A/B.

The model's answer incorrectly called **11:44:24 the last device check-in**. Its own selected-device current-state receipt reported `lastSeen=Mon Nov 02 11:40:29 GMT 2026`. The scoped returned event page separately included **power=0 at 11:44:24.221+0000**, amperage 0 at 11:44:24.227 and voltage 243 at 11:44:24.223; an earlier power=1 report at 11:43:38.308. These are **attribute event timestamps**, not a `lastSeen` update. The source event page was bounded/truncated with integrity not independently verified, and it contained **no switch event**; the last switch change was not established by HomeBrain's reads. A subsequent Claude answer mentioned older switch history (27 Oct), but its additional reads were later and are not independently available as source receipts in HomeBrain's sample.

## General source-first improvement
`current_state_clock_evidence.py` emits one compact source-derived packet from an existing verified selected-device resolver receipt plus optional same-device named event history, and attaches it to the **existing final model call** on ordinary current-state answers. It explicitly separates:
- the selected device's **driver-reported `lastSeen`**;
- the **host receipt read timestamp**;
- the latest returned timestamp **per attribute** (power, switch, current, voltage), only when a bounded, same-device reporter event actually exists.

A missing per-attribute event in a bounded result is labelled **unknown**, never absent in history or proven unchanged. A Hubitat event may be source-timestamped but does not independently prove physical compressor or hardware operation. Only sanitized numeric IDs, short typed values, source-format timestamps and exact label/ID associations enter the timing packet; disjoint device events are ignored. No extra Hubitat tool read, model round, physical actuation, publication template, device-name keyword or permission is added. Model retains authoring of the final natural answer.

## Frozen offline checks and limits
Anonymous source fixtures reproduce the *structural timing conflict*, using synthetic names/IDs. Tests verify lastSeen 11:40 vs latest power event 11:44, latest returned switch-event vs missing bounded switch history, no extra invented timestamps, privacy/mismatched reporter denials, failed/cached identity refusal and final call placement. They test source packet content, **not whether Gemma obeys it**.

**NOT MEASURED for v0.18.358:** live model answer correctness, first-answer usefulness, source-identical Claude comparison, median/p95 latency and whether the synthesis packet adds token time. Next step: install v0.18.358 and ask one fresh read-only status question in an unrelated domain, comparing source-attribute timestamps to words without repeating older scenarios. Keep the original 15.642s v0.18.357 trace as an unmatched before observation.

**Risk / rollback:** additional source text may increase provider tokens/time or be misused as overconfident last-change proof. The source-scope and no-new-calls test suite is blocking. Revert PR if live outcomes regress. No live Hubitat or Home Assistant changes were made in development.
