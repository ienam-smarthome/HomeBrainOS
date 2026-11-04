# Q1 live read-only snapshot comparison — 4 November 2026

## Observed installed baseline (HomeBrainOS 0.18.399)

A user supplied an unchanged registered `multi_device_named` question, one
natural-language response and the full Technical JSON privately. This is
a **single live observational answer**, not a statistically estimated
success rate or independently certified first attempt. The API-bound
question digest matches the frozen case, but the envelope itself says
`first_attempt_verified=false`, `model_delivery_verified=false` and
`deployed_build_sha_verified=false`. No deployed Git SHA is proven.

The two requested device IDs were uniquely resolved. Individually read
Hubitat retained `switch=off` on both and `level=50` / `level=60`.
The published answer reported those attributes correctly. The levels
remain saved settings of OFF switches, not verified light output.

The answer added unsolicited activity history: five reported ON-to-OFF
intervals totalling 465 seconds for the first light, while explicitly
acknowledging no event-history read for the second. A bounded 20-event
page supported reported intervals only; its historical integrity was
unverified and its observed events were truncated. Multiple OFF/level
commands attributed to an installed app were present, but bridge-
reported state transitions and command records do not alone prove
the automation's upstream trigger or that every interval was driven
by that app. This surplus analysis was outside the user's objective.

**Inconsistent status:** transport `success=true`, metrics outcome
`success`, and `investigation_coverage.questionResolved=false`,
`sourceScopeComplete=false`, and `targetHistoryScope` missing the
second light's history. The question itself only asked for current
states: missing unsolicited history must not make the required
current-state comparison unresolved. Historical comparisons **must**
still require both target-scoped history reads.

**Observed timing:** 19,409 ms wall, 18,143 ms agent,
14,568 ms provider, 3,357 ms total MCP HTTP, six
free-model rounds, seven tool calls. This exceeds the 15-second
single routine-status target but cannot establish median/p95.

## Root cause and general correction hypothesis

`investigation_policy.HISTORY_INVESTIGATION` included the bare word
`compare`. Therefore an ordinary `Compare the states of ...` request
was classified as a history investigation, loaded historical
tool guidance and invoked history scope/retry processing. The model
also broadened the final answer with unrequested activity.

Limit current state/level/brightness comparisons to independent
reported device state by default; preserve historical/causal
classification when the question explicitly mentions past events,
patterns, transitions, temporal windows, history or causes.
Add generic model instructions to avoid decorative history and
overstated causal linkage in current-state answers. This changes
no permission, device identity, physical device or model provider.

## Expected and actual measurement

Expected: two source-verified current device states and saved levels
in a concise response, with no unrequested event-history calls,
no false historical completeness requirement, and preferably under
15 seconds. The model remains the natural-language answer author.

Before (one real first-received response): 19.409 s, 6 model rounds,
7 tools, correct reported states, unrequested history, source-scope
mismatch. After: **NOT YET MEASURED ON THE INSTALLED BUILD**.
Offline unit tests and CI can prove classifier boundaries but cannot
prove better real model answers. The objective is correctness and
fewer unnecessary reads, not an invented first-attempt quality score.

## Acceptance and rollback

Keep the registered 13 legacy / 40 curated fixed cases unchanged.
Test current-state comparisons and explicit historical comparisons
with unrelated synthetic subjects and a one-sided history packet.
After green CI, repeat the exact private registered read-only prompt
on the new installed version; compare source receipts, latency,
history calls, causal overclaims and completion fields. The repeat
is a paired regression, **not a new first attempt**. Roll back the
classifier if legitimate history questions lose source-scope checks
or status snapshots become less grounded.

Do not use this evidence as a Claude model A/B or as a success
percentage for the original Answer Quality roadmap.
