# HomeBrain V2 alpha.151 — publication-scope hardening

## Why this candidate exists

The complete private alpha.150 cohort failed promotion: 68/80 supported factual
claims (85%), 3/10 useful first answers (30%), one unsupported definitive causal
claim and 7/10 relevant-source sufficiency (70%). In particular, a limitation in
one clause could exempt a separate categorical absence or continuity assertion,
and bounded fallback summaries could omit the original `since`/`until` scope.

## Runtime change

The existing read-only historical publication check now treats semicolons and
the contrastive conjunctions `but`, `however` and `yet` as claim boundaries. A
qualification in one claim therefore does not license a separate categorical
claim that no events existed or that a state continued throughout an interval.
Tentative continuity language remains permitted.

Bounded fallback summaries retain validated `since` and `until` strings in
addition to device, app, attribute, level, hours and limit scope. Unsafe scope
text is not published. The change does not add an MCP call, model round, native
write, deterministic source route or approval bypass.

Alpha.151 also packages the already-merged claim/receipt contract shadow. That
packet remains private telemetry with no claim bindings: `enforced=false` and
`answer_changed=false`.

## Prospective gate

`alpha151-prospective-v1` is a new ten-case pack with new identifiers and
wording. It covers current-versus-historical health, complete inventory
aggregation, two-device attributes, reporter/listener/issuer roles, continuity,
app execution, stored-versus-event values, activity/health/measurement roles,
bounded contact history and grouped bounded logs. Earlier packs remain in the
offline verifier and must not be pooled with this cohort.

Promotion still requires a complete installed first-attempt cohort, independent
review of the original private receipts, at least 90% factual grounding, zero
unsupported definitive causal claims, at least 80% useful first answers, and
the existing source/permission attestations. CI and synthetic tests establish
packaging and regression health only.
