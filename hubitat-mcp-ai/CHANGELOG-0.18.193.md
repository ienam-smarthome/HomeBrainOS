# HomeBrainOS v0.18.193 — Generic-load warning attribution and numerical history coverage

## Live regression: 28 October 2026, v0.18.192

Native Investigation V2 completed in **19.554 seconds**, with eight successful READs, then stopped after two repeated device snapshots. The targeted WARN query returned **three Google Nest Hub generic excessive-load warnings**, all between **19:55:19.194 and 19:55:19.399**. This sample did not return a slow driver-method duration.

The separately sourced device history returned **92 source rows**. Its bounded model projection kept 80 individual events and an issuer summary. Two apps are independently attested as device command issuers:
- Adhan Player (app 1679), 30 commands in the source response, latest 18:15:02 on 28 October.
- 00 Google Calendar Notifier (app 4080), 18 commands in the source response, latest 17:51:43.

Neither of those sampled command streams coincided with the *specific* generic 19:55 warning. V2 incorrectly wrote that the "warning-window caller" was unverified despite already verifying device callers, and used an eight-read budget on status snapshots and a memory-history response whose projection contained only timestamps. The model also proposed hub_get_device via hub_read_apps_code, which the READ manifest correctly denied.

## Changes

- **Separate evidence dimensions.** A source-backed device command issuer is a verified identity, not a proven cause for any generic load-warning interval. The new `target_generic_warning_origin_unverified` state preserves verified app IDs, explicitly marks incident-window attribution as unverified, and recommends an independently authorised, model-chosen more discriminating historical WARN or performance read. Neither a keyword route nor an automatic hub call is introduced.
- **Earlier evidence-based guidance.** Immediately after relevant device history (or a repeated device snapshot), Native V2 provides the model a compact source-derived diagnostic gap/candidate READ view, while normal rounds remain. All candidate actions still pass the live manifest, typed identity and read-only guards.
- **Evidence-accurate fallback.** Generic excessive-load WARNs alone no longer become a claim of independently timed slow driver-method execution. The explanation can say that apps issue commands to the device, while the particular generic warning still has no proven triggering callback or app. `generic_warning_cause_unverified` replaces the misleading actor-unverified validation flag for this case.
- **Partial event projection declared.** The source may return more event rows than the model-safe projection retains; counts and omitted-row coverage are explicit rather than claiming that the oldest visible event covers all returned evidence. Issuer counts are separate from the displayed event subset.
- **Numerical memory-history evidence.** The bounded privacy-filtered `hub_get_memory_history` projection preserves numeric/boolean measurements and source timestamps when present, and explicitly flags timestamp-only results as insufficient to assess CPU/memory at the warning time.
- **Operation mapping guidance.** When a READ is rejected for the wrong gateway, the model receives fixed guidance to use the independently attested gateway instead of retrying an invented mapping.

## Safety and limits

These are general source/provenance fixes and affect only experimental read-only Native V2. No devices, drivers, automations, rules or production Main Ask were changed. No extra Hubitat calls are executed automatically by the coverage checker. Driver implementation/trace analysis and atomic claim-to-evidence validation remain incomplete. A verified issuer does not prove that the app blocked a driver callback, and generic hub-load warnings do not independently prove hub-wide CPU degradation.

CI regression tests replay the generic 19:55 warning vs earlier app commands, the 92/80 event sample distinction, memory-history numeric privacy and missing measurement cases, the model's early source-coverage hint and wrong-gateway repair. Live testing is still required after merge.
