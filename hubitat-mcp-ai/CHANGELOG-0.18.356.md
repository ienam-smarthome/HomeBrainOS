# Hubitat MCP AI v0.18.356 — current-status completion is not a historical causal investigation

## Observed first-attempt benchmark (2026-11-02)
A real user-rated **useful** v0.18.355 present-status answer (Ollama Cloud Gemma 4 31B; **12.255 seconds, four model rounds and four tool calls**) returned `Unresolved` due to missing `command_history` under `causal_provenance` despite asking whether a device is currently operating and what switch/power reports imply. This is **one** user-rated example, not a production success-rate estimate. A separately supplied Claude answer to a similar prompt provided additional attribute-specific freshness/history qualifications, but ran later against potentially different source results; no same-source timing or blinded accuracy comparison exists.

## General cause and minimal correction
In `shared_investigation_completion.apply_shared_investigation_completion`, the read-only completion check previously returned early for non-causal questions **only when there was no prior investigation coverage object**. A model-proposed hypotheses packet is a coverage object, but it does *not* mean the user's question asks which command or automation caused a historical event. The subsequent fallback treated `goal=None` as `causal_provenance`, automatically required device/command history and marked the response partial, independent of whether the plain-language current-status answer was useful.

The early exit now follows the actual **request objective and previously verified specialist domain**: when no recognized investigation domain exists, no historical causal question was asked, and no host-attested specialist domain is present, preserve the original answer, metrics and any attached source/hypothesis packet **without** creating command-history obligations. A previously established device-telemetry, rule-verification, lockout, rule-design or scheduler domain still runs through its existing evidence requirements even when the broad text classifier does not match the user's exact wording. There is no new model round, tool call, device type, keyword-to-action route, generated prose template, or change to Hubitat/HA behavior.

## Regression boundary
New cross-domain offline tests verify:
- Present-status question with an existing model-proposed source-check packet retains the original outcome and does not inherit `command_history`.
- Another non-causal multi-sensor factual comparison preserves source-check limitations rather than inventing a historical cause.
- A real “why did the device turn off?” question still goes through strict command-provenance coverage and can remain `Unresolved`.
- An actual offline/telemetry diagnosis still uses its domain-specific incomplete-evidence coverage.
- An independently established specialist telemetry domain is **not** skipped simply because the broad question classifier did not select it.

**Not fixed or claimed:** the exported Technical JSON does not currently preserve independently inspectable per-attribute switch/power values, their last-change timestamps, or packet freshness beyond current receipt projection; no statement of physical execution can be certified from a driver reporting 0 W alone. The short answer's potential over-absolute physical-state wording remains an evaluation note, not a case-specific rewrite.

**Measurements still needed:** installed v0.18.356 first-shot result, human-reviewed factual source grounding, latency distribution, model/tool-round saving (not expected from this deterministic gate), and source-identical comparison to Claude. All are **NOT MEASURED**.

No live Hubitat/Home Assistant reads or writes were run during development. Merge only after full exact-head CI all green.
