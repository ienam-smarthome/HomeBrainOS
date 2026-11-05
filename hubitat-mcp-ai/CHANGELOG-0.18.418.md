# HomeBrainOS Hubitat MCP AI v0.18.418 — typed parent and date-guide preflight

## Installed 0.18.417 observation

At 17:15 UTC on 5 November 2026 a read-only one-time Rule Machine preflight returned MCP initialize serverInfo 5.1.6, a hub-local backup timestamp 2026-11-05T03:02:31+00:00 and both native tool guides readable, but it did **not** inspect parent app 169 or provide the source-specific reason `atDate#` was unverified. The preflight's `preflightEvidenceComplete=true` covered the core three sources only; authoring/readback remained unverified and no Hubitat write occurred.

## v0.18.418 correction

- Preserve the fast three-source no-model preflight for requests that do not explicitly require parent or creation-contract evidence.
- For an **explicitly requested exact parent app ID**, independently read installed app instances, built-in app types, the app's summary, and its read-only app configuration. Verify the same ID, native Rule Machine type-name/ID join, `system=true`/`isBuiltIn=true`, native namespace from source, `user=false`, root parent flags and at least one returned child row. Return safe failure codes when data is missing or conflicting; never infer a parent by names or counts.
- Project safe guide field evidence for `atDate#`, its explicit date type, `yyyy-MM-dd` format, other named trigger fields, Certain Time trigger wording, `hub_set_rule(operation=create)` and `parent_id` declarations. Do not publish guide content, acknowledgement keys, sensitive values or unrelated names. Distinguish an unavailable/missing guide declaration from affirmative unsupported functionality.
- Evaluate core preflight, requested parent identity, date guide, creation guide and saved-date readback as independent obligations. Keep `readinessForMutation=false` unconditionally; an authoring guide does not prove runtime execution, form/scheduler safety or writer authorisation.
- Add synthetic MCP regression tests for correct class identity, conflicting class/namespace/parent metadata, absent typed date fields, missing target ID, no write operations, zero model rounds and evidence redaction.

## Boundaries

Changes are limited to read-only evidence collection and reporting; no Hubitat rule, device, router, backup or permissions change. The previous 0.18.417 successful readback of rules 2967/3985 contained no verified enabled dated trigger, and this patch does not create one. GitHub CI and installed acceptance are separately required. A native one-time test requires explicit independent user authorisation after all safety checks.
