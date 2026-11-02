# Hubitat MCP AI 0.18.348 — source-attested alias binding for bounded app-decision evidence

## First-shot user evidence, not an invented benchmark

On 2 Nov 2026 user ran a read-only bathroom ventilation fan boost investigation using v0.18.347 (Gemma 4 31B Ollama Cloud). It took **66.506s, 11 model rounds, 19 tools**. Source-timed Fan Boost device 7850 commands show app 3995 `on()` at 21:59:59.941Z, bridge-reported ON at 22:00:00.261Z, app `off()` at 22:30:00.036Z and bridge-reported OFF at 22:30:00.666Z. The recorded 30m cycle matches the configured 22:00 schedule, **supporting** (not independently proving) scheduled trigger. App decision logs were not read; 21:30 humidity 54% and 22:30 56% are too sparse to rule out other events, and no complete manual input history was provided. Model asserted 'scheduled cycle confirmed', 'humidity ruled out', 'manual override ruled out' despite technical `rootCauseVerified=null`. **Causal calibration and latency fail**. Command issuer source is correct, upstream trigger unverified.

## General fix to current source contract

- Bind differently worded causal questions to the same **single** read-only verified target only when a positive device ID + label from a *detailed, exact-label-filtered, targeted lookup* is unique, a successful independent device-ID-scoped history for that ID exists, the corresponding label-bearing deterministic event wrapper has real typed command witnesses, and a successful resolver read for a phrase in the request exists. A common lexical token only rejects contradictions; it is not device identity. An explicit longer compound name conflicting with the label rejects the match.
- Once attested, allow the existing one-shot, live effect-gated, read-only app-ID log window around a verified method/switch command. No extra model rounds, no new write privileges, no retry after failed attempt.
- The generic source packet now reminds the model that matching schedule and commands are *circumstantial support*, not verified scheduler decision; sparse humidity/input samples cannot rule out missing events, and a bridge reported state does not establish independent hardware action.
- Preserve the natural model-authored publisher. No new host prose replacement or device-name-specific behavioral rule.

## Quality, validation, safety

Regression tests cover successful alias binding, no target, ambiguous targets, missing native history, mismatched identity and explicit conflicting compound names. CI and container smoke at exact PR head mandatory; do not merge if checks incomplete. No live Hubitat/HA device, automation, config, storage or backup changes. The trace also independently found **Hubitat local backup failed due to free 938MB (<1GB required)**; user was advised to inspect storage safely, not delete backups. If the new app-log source is empty/unavailable, the actual scheduler cause remains unverified. The 66s latency persists unless separate planner/tool overlap is reduced. Model accuracy impact is NOT MEASURED.
