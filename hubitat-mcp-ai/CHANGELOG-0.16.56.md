# Hubitat MCP AI 0.16.56

## Performance synthesis quality

- Blocks implementation-specific optimisation advice such as `use asynchronous calls`, timeout/retry tuning, or reconnect changes when the current turn did not read the relevant app/driver code or settings.
- Preserves conditional analytical wording such as `could block execution threads if calls are synchronous` because that remains explicitly hypothetical rather than a configuration prescription.
- Keeps the original recommendation label while replacing unsupported implementation tuning with an inspection-first message.
- Recognizes explicit app/driver code or implementation evidence as sufficient grounding for specific implementation advice.
- Adds a serialization fallback for diagnostic-style performance answers that contain measured resource consumers and observations/hypotheses but omit any recommendation/next-action section. The fallback adds only two process-level grounded actions: inspect high per-call latency at the same component, and inspect high call volume at the same component before prescribing tuning.
- Does not add Hubitat calls or change performance/log evidence collection, causality thresholds, or threshold-sample compaction.

## Regression coverage

- Reproduces the 0.16.55 live LG TV recommendation that prescribed asynchronous calls and generous timeouts without reading implementation/configuration evidence.
- Verifies conditional synchronous-thread analysis is left unchanged.
- Reproduces the second 0.16.55 run that stopped after observations and verifies a grounded next-actions section is added without inventing numeric settings.
- Verifies an existing recommendation section is never duplicated.
- Verifies current-turn code evidence allows specific implementation advice.