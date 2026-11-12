# HomeBrainOS V2 alpha.63 — read-only inventory questions in optional frozen evaluation

**Date:** 12 November 2026. **Scope:** Optional frozen-evidence evaluation only.

## Background

Alpha.62 correctly retained transport timeouts on contractually read-only native MCP operations. However, an unrelated eligibility rule still excluded ordinary *read-only inventory questions*, such as requests to list devices with low battery and evaluate missing, stale or verified offline status. The live agent could answer those questions, but the three-stage experimental evaluator accepted only causal, historical or verification questions phrased with explicit review verbs.

This exclusion would produce a second, unrelated replay error even after the original timeout fix. Excluding an evidence-rich inventory response simply because the wording begins with "Which..." would bias cross-domain comparisons.

## Change

Add `frozen_review_kind()` to the existing generic review module. It preserves all existing `review_kind()` classifications. **Only** when the original matcher returns no result, it accepts a read-only inventory/status question beginning with a generic inventory word (`which`, `what`, `list`, `show`, `identify`, `find`, `compare`) and containing a broad device, measurement, health, history, event or configuration subject. It routes such questions to the existing source-verification **tool-free** reviewer.

The default live agent `review_kind()` function is **unchanged**; there are no new production model rounds or prompt restrictions. The mobile and offline frozen evaluators now call the new optional-only classifier. The failure-preserving, native read-only tool validator from alpha.62 remains unchanged.

Synthetic tests cover inventory questions plus a timed-out read-only native inventory attempt, a successful original receipt, and three model rounds with zero MCP calls. Write-intent and irrelevant non-evidence questions remain ineligible.

## Observed evidence-quality limitation (no patch)

An inventory may show battery percentages, but the device-level `lastActivity` is not necessarily the last *battery-attribute* timestamp. A stale device record alone is not proof of offline state. Distinguishing report-age, source completeness and verified device connectivity remains a question for independent source-grounded grading, not a hardcoded device rule.

## Safety and acceptance

As in alpha.62: no Hubitat commands, no new read-source calls, no hidden evidence, no new write permissions, no persisted server-side private data, and one-time explicit cloud consent for the original frozen-replay endpoint. V1, the real-time V2 Ask agent, source routing, prompts and Hub & Device Monitor recorder are untouched.

CI must pass V2 pilot tests, release assurance and repository validation before merge. A passed replay does not prove that the answers are accurate; human grading remains required. No private household evidence was committed.
