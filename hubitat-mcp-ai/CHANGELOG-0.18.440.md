# HomeBrainOS v0.18.440 — source-grounded historical log-retention explanations

## Actual Q1 live evidence (6 November 2026)

The v0.18.439 ordinary Ask investigation of 5 November 16:30–16:53 GMT reported a successful unbounded `past` log sample with **20 timestamped messages** (1 app-identified, 19 device-identified; 9,082 source rows reported) and a separate **zero-match bounded** `past` query (9,085 raw source rows reported, 0 matching rows). An independently typed event read preserved lowMemory (16:41:40), sunriseSunsetUpdated (16:44:20) and systemStart (16:52:15). The model nevertheless claimed confidently that reboot(s) purged the missing historical log buffer and labelled the recent uptime-derived restart time as reported fact. No source receipt established oldest retained native-log timestamp, the purging mechanism, or which app consumed memory. A source-completeness footer contained literal escape sequences.

## General change, not a case-specific culprit rule

- Extend the existing unresolved causal publication guard to unsupported **historical-source loss attribution** (e.g. logs supposedly purged, cleared, erased or rotated because of reboot/update). Preserve hedged/explicitly unverified hypotheses and non-investigative status replies.
- If the model confidently states that an unverified restart/update cleared historical records, replace its unsupported explanation with an evidence-first answer. Preserve successfully read bounded zero-match page counts, pre-time-filter source totals, and trusted typed system/location events. Display the sunrise/sunset event as unrelated to confirmed reboot cause.
- Add bounded source-qualified metadata for existing successful unbounded recent `past` samples: returned page/message counts and app/device source identity counts. Never present the most recent 20 rows or upstream `sourceRowsReported` as proof of oldest retained timestamp.
- Retain specific read-only next checks on timezone, actual oldest/newest source times, and existing external recorder/journal evidence. No retroactive log recovery or invented reboot purge cause.
- Fix literal `\n\n` source-coverage suffix rendering in the shared orchestrator.
- Add regressions reproducing the v0.18.439 evidence pattern and controls for uncertain language, completed cases, failed source reads, mixed mode coverage, event order and privacy.

## Expected effects, verification and rollback

**Hypothesis:** More useful, source-calibrated natural explanations of partial historical coverage with zero unsupported definitive history-loss causes. This is a code-level change, **not a verified live improvement**.

The observed 36.9-second single run is a descriptive metric, not a latency pass/fail criterion. No fixed complex-investigation time target applies. The full historic time range, old message recovery, model first-attempt answer quality, and underlying memory consumer remain unverified. No additional MCP calls, polling, paid routing, write permission or operational deadline changes.

CI is required before merge. Roll back on confident false history assertions, improper removal of genuinely supported conclusions, privacy leakage, source-class regression, or general Ask/incident routing failure. Live retest should compare the exact 5 November retention question and full Technical JSON, with all cause hypotheses kept explicit.
