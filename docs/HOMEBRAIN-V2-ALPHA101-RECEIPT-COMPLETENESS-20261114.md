# HomeBrainOS V2 alpha.101 — returned-event completeness in the existing final audit

**Date:** 14 November 2026. **Scope:** V2 Preview only. No V1 changes, live Hubitat reads, private home receipts, provider change or new model round.

## Why this is general, not a room-specific patch

A source-real alpha.100 read-only historical heating-continuity investigation **did** invoke the existing source review and final claim audit. It completed in about 22 seconds with two successful native MCP reads, no errors and no writes. However, the model's final answer said that four hourly observed idle/0% pairs were the only returned state samples. The original 100-row native history actually contained **six** paired reported-state/level observations at approximately **30-minute** intervals, plus a recorded thermostat setpoint command. It also retrieved a full 203-device inventory (~68 KB) rather than targeting one label. These are separate evidence-completeness and efficiency issues. The command issuer is proven from a specific command row, not from state-report `producedBy` or `triggered[]` listeners; its internal decision and effect on prior idle reports remain unknown.

The main no-continuous-*reported*-heating inference was compatible with the returned idle observations, but not the claim that these six were only four hourly observations. Regular returned observations do not prove continuous physical radiator heating or source-retention completeness.

## Change

- Reuse the **existing tool-free final audit** and the already-successful, unmodified original `hub_list_device_events` receipts. Index only exact event names explicitly mentioned in the candidate draft (up to four source fields per receipt). Provide original returned counts, **full offset-aware timestamps**, source values from a strict, short numeric/enum allowlist, chronological source-row previews and actual gaps in seconds. An excerpt is clearly marked if capped; never call it an exhaustive archive.
- Separately surface up to eight material **originally returned command rows** with safe command event names/timestamps and numeric issuer app IDs, even when the draft omitted the command. The index must not imply that issuing a command caused a subsequent state or revealed its internal controller reason. Do not copy free-text event description, user-defined actor names, arbitrary command arguments, logs, secrets or untrusted values.
- Add one concise evidence instruction to the pre-existing final audit: reconcile definite total observation/refresh counts, period/cadence claims, all named matching event rows, and previously omitted material command rows. The original successful receipts remain the sole authority; this small index is navigation, not independent evidence or a model-independent semantic postprocessor.
- Safety/cost: no compulsory historical source query, automatic retry, polling, authorization change, native write, extra model pass or provider change. The extra index is computed from already returned source receipts, and will modestly increase input tokens for audits using matching source fields. Existing first-answer review eligibility and time budgets are unchanged.

## Fictional isolated regression contracts

Synthetic, non-identifying tests exercise 6 (30-minute) versus 4 (hourly) event-row mismatch, correctly observed intervals, material omitted setpoint command and issuer ID, strict privacy sanitization, no inference of commands absent outside a bounded source, explicit preview truncation, failed/unparseable/non-device sources, and scripted execution of the **existing** final model round with zero tools and no extra native reads. Tests do not claim connected Nemotron reasoning is fixed.

## Acceptance, rollback and next development

Require full exact-PR-head V2 Python, metadata, container/smoke, pilot and UI fixture CI before merge; then post-merge checks. After operator-confirmed hub stability, install alpha.101 and ask one **new, independent, read-only** historical question with a mixed-attribute event stream (not the already exposed heating fixture). Compare all original event-name counts, timestamps, command rows and final answer; verify model source-review/final-audit flags, native command issuers versus state reporters, no unearned cause, no writes, tokens and elapsed time. Do not infer completeness from a capped sample or missing command. If the model still omits important rows after receiving the correct structured source summary, consider typed claim checking or controlled model comparisons rather than more overlapping natural-language prompting.

Rollback to alpha.100 if timeline indexing corrupts source role/time, adds unacceptable token overhead or breaks source-review safety. V1 stays unaffected.
