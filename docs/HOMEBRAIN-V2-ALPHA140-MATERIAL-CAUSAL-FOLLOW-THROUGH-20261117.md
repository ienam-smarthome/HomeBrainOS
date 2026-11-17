# HomeBrainOS V2 alpha.140 — material causal-source follow-through

**Status:** code PR candidate, exact-head CI pending. Independent installed live first-answer acceptance remains outstanding.

## Source-real baseline (private)

The installed alpha.139 uncoached first answer (human review 5/8) correctly found the main output's last heating state report, its reporter, and notified listeners, but did not establish the demanding room or controller's event-time decision. Original seven successful native reads: one **67.7 KB broad inventory**, two current device summaries, one current hub modes read, two 24-hour filtered `thermostatOperatingState` histories, and one `hub_get_info`. That final general hub-metadata read was added during the causal review; it did **not** address the missing event-specific input, command or execution. `causal_follow_through_invoked=false` because the existing optional follow-through required zero additional receipts. User-provided earlier controller logs are separate from these original alpha.139 first-answer receipts and are not scored as model retrieval. No private identifiers or raw household records are committed here.

## General correction

- Keep the existing source-review and the existing **single optional** model-owned causal follow-through. Extend eligibility only when the reviewed answer explicitly leaves a causal link unresolved and the intervening native reads were **all contextual / empty / unsuccessful**, rather than requiring zero reads.
- The new small `causal_review_read_delta` categorizer inspects only successful, original current-request receipts **after the review started**. Recognize well-known Hubitat hub/device inventory, current summary, modes and installed configuration reads as contextual; nonempty validated device history, original nonempty app-scoped past logs, and monitored saved historical reads as potentially discriminating source categories. An unknown read-only tool is conservatively *not* called useless. Neither the type of read nor its successful return proves event-time causation.
- Give the MODEL the resulting bounded read-category delta and existing advertised safe read-only source contracts in the **already existing** optional follow-through. No tool, device, app, source order, scheduler policy or final cause is selected or dispatched by the host. The model may safely decline additional reads. Existing timeout budget (>25 sec), one-shot follow-through limit, user explicit no-fresh-read restrictions, original reply, and native write/approval boundaries remain.
- Narrowly broaden the existing unresolved wording recognition to include explicitly **not captured**, **not identified**, and investigation/execution-log follow-up formulations. This is a checkpoint trigger, not a publication guard or generated causal answer.
- Surface `causal_review_source_delta_at_follow_through` in Technical JSON only to support review of the decision to reopen source investigation, without source content or private names.
- No modifications to V1, native write safety, provider routing, physical device data, thermostat scheduler, source receipts or the 53-case benchmark.

## Test acceptance

Use fictional cross-domain event and app-log receipt tests for contextual read versus potentially discriminating history, failed/empty/mismatched responses, unknown future tool contracts, explicit read prohibition, time bounds, model selecting a log read after hub metadata, declining a read, and avoiding additional follow-through after nonempty historical logs. Require the complete PR-head CI suite before merging. A synthetic green result does **not** prove that the live model chooses the correct event-time source, that a log proves causation, or that cost/latency improves. Next acceptance: a fresh uncoached alpha.140 PRIVATE first-answer Technical JSON for heating and at least one other domain, with chronology, source scopes, model rounds, reported token cost and independently scored correctness.
