# v0.18.40 — Complete broad audits and recover grounded results on synthesis timeout

## Evidence behind the changes (19 October 2026)
Two HomeBrain results were compared against an independent ClaudeAI audit of the same Hubitat environment. The Claude API request through HomeBrain 0.18.38 ran six model rounds and eight read-only tool calls, taking ~207 seconds and ending at the 30-second *final synthesis* limit with only a generic timeout notice. The Free Gemma run completed seven rounds and nine reads in ~48 seconds but returned a narrow performance/job summary despite requested device, rule and log investigation. Both successful evidence sets contained useful measured facts; the system-wide analysis was not completed.

## Cross-domain audit routing
- Add a conservative goal classifier for genuinely whole-hub reviews spanning error/warning logs, applications/Rule Machine and device/health sources. These use the existing **read-only Comprehensive System Check**, which already gathers detailed device/automation inventories, capped log samples, performance leaders and selectively scoped source reads.
- This route takes priority over the performance-only plan **only for compound audits**. Scheduler-only efficiency requests, individual-device causal questions and performance-only questions keep their specialist workflows.
- The comprehensive report does not depend on an extra paid synthesis round; optional AI commentary remains controlled by existing configuration. Do not confuse a lack of reported alerts with proof that every driver/rule is healthy.
- The System Check's intentional-unpowered-device setting and existing privacy, partial-source and safety guards remain in effect.

## Provider-independent timeout recovery
- The specialised performance workflow retains its optional single provider synthesis round. If it exceeds its existing timeout, reuse successfully captured **same-request** metrics, performance, scheduler digest and sampled warning/error receipts in a bounded, source-derived report.
- Show actual numeric metrics and measured leaders only when usable payloads exist. Report only countable sampled warnings and link recommendations to read-only verification or configuration review. Never reuse unverified model draft text, claim a complete audit, infer CPU savings or authorise Hubitat state changes.
- Preserve successful read receipts, including any final API-level read, alongside this partial report. Retain the unresolved/timeout outcome and make the limitation explicit.
- Add a regression suite checking multi-domain versus scheduler-only routing, privacy-safe labels and no raw API URLs, failed/missing-source restraint, no provider retry on timeout, no stale draft reuse, and retained evidence.

## Scope
No Hubitat mutations, no new tool privilege, no cloud sync. **Free Gemma remains default**; paid DeepSeek and Anthropic Claude remain opt-in. Existing collapsible chat interface unchanged.

## Remaining development
A subsequent architecture phase should rank source hypotheses and perform dependency-aware automation overlap checks with evidence IDs and scoped logs. This release does not pretend to reproduce every claim in the externally supplied ClaudeAI audit.
