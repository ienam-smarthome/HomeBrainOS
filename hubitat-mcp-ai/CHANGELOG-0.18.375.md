# 0.18.375 — Q3 concise and bounded partial-telemetry answer opportunity

## Live evidence and hypothesis

Two real installed first responses to the registered read-only `device_mqtt_conflict` question were supplied:

- v0.18.373: **57.559 s wall, 51.182 s provider, 8 Gemma4:31b rounds, 9 tool calls, 0 paid**. It definitively attributed an unverified ghost MQTT state while `rootCauseVerified=false`: source-reviewed causal calibration **FAIL**.
- v0.18.374: **44.647 s wall, 33.685 s provider, 8 Gemma4:31b rounds, 8 tool calls, 0 paid**. It admitted **16 source-observed rows from 17 reported**, marked **1 unknown**, replaced original model draft through `source-typed-evidence`, preserved `rootCauseVerified=false` and avoided a definitive root cause: source-reviewed causal calibration **PASS**, root-cause resolution still **unresolved**. Answer was lengthy despite a simple question. The ~12.9 s observed wall difference is **not a matched performance trial**; distinct source conditions and no repeated sampling mean no causal latency improvement is established.

General Q3 hypothesis: evidence-backed telemetry sufficiency and brief publication are unnecessarily disabled for *all* truncated event pages, including those with independently paired exact source/analysis counts and a preserved unknown-row count. This causes unnecessary recovery rounds and forces a long technical report even when no commands or verified watchdog causal timeline were returned. There is no new model reasoning, paid provider use or network diagnosis.

## Code change

1. `telemetry_completion_policy.ready_for_bounded_telemetry_answer` now accepts **only** source-count-matched, explicitly truncated paired history packets with positive observed and unshown counts, non-verified completeness, precise target identity and the original positive status/history/log/checkpoint requirements. It grants a bounded no-tools synthesis opportunity; it does **not** call the diagnosis complete or verify hardware, broker packets, commands or the historical cause.
2. `answer_publication_policy.publish_source_typed_answer` prefers the existing source-backed **concise** renderer when truncation is the *only* detail trigger and a positive retained/unshown source-count match is established. That renderer already reports the observed/source counts, unknown-event count, reported attributes, clock disagreement, current evidence limits and next read-only discriminator. Uncounted/ambiguous partials, any command rows, independently correlated watchdog timeline and explicit full-detail requests continue using the full renderer.
3. Cross-domain anonymous telemetry read-only tests and negative controls for missing/contradictory counts, ID/window mismatch, missing scoped logs, absent checkpoint and explicit full reports.

## Expected effect and limitations

**Before:** 8 Gemma rounds and 44.647s on the single source-real v0.18.374 live first answer, 16/17 join accepted, causal calibration PASS, answer verbose. Offline default readiness function returns false for every truncated sample, and publication mode was `evidence-depth-required`.

**Offline after (candidate):** The exact source-attested partial shape plus targeted logs and checkpoint now can trigger `telemetry_sufficiency_stop`, while the same packet with no commands uses a concise publication mode. This is a *static decision behavior* result, not an observed provider-time or accuracy gain. The historical rows and `rootCauseVerified=false` survive the new path. Negative cases must remain fail-closed.

**Real installed after:** **NOT MEASURED.** Expected fewer unnecessary model rounds, shorter first answer and possible latency reduction, but no guaranteed wall-time delta. Semantic grounding, first-usefulness, accurate diagnosis, local-vs-cloud A/B and overall 90/80% targets remain NOT MEASURED beyond the two individual source-reviewed observations.

**Risks:** An early bounded answer can omit a useful additional read, so require exact joined source evidence plus scoped logs and one independent diagnostic-source check or previously offered high-information checkpoint. Missing source/identity matches never qualify; do not apply to historical causal multi-target, heating, lighting, writes or user-requested comparisons. Revert the two policy changes and version metadata to roll back. There are no live Hubitat/HA mutations, rule writes, provider calls, or add-on setting changes in this PR.
