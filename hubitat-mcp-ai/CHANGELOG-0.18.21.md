# 0.18.21 — Source-method evidence that survives final synthesis

## Live finding (0.18.20)
The code-first investigation of Bedroom 3 Mesh completed in ~43 seconds rather than ~147 seconds and returned a meaningful answer. However, it declared full-file source retrieval (driver code 3686, 20,531 UTF-16 offset units) while saying essential later-file method bodies were outside the visible model excerpt. Whole-file retrieval did not prove that those method implementations were examined, and objectiveSatisfied was marked true even when the answer admitted they were unseen.

## Change
- Reuse the existing, verified single-piece `hub_get_source` response. Generate a bounded, line-numbered source evidence packet containing candidate full Groovy method bodies selected from user-named symbols and language appearing in real source. This is done in memory without extra Hubitat calls, write permissions, background jobs, or model-selected source pagination.
- Preserve relevant late-file method evidence beyond the existing 2,200-character per-tool synthesis packet prefix. Present the candidate bodies with explicit lexical-boundary and excerpt-budget limitations, and redact apparent credentials.
- Final synthesis prioritizes these verbatim source-derived excerpts, while separating implementation claims from runtime execution and MQTT broker/physical connectivity.
- When the answer explicitly admits material methods were not in its visible excerpt, preserve the useful answer but mark the objective unresolved rather than fully satisfied, even if the entire driver source was retrieved.

## Safety
Only actual current-turn Groovy source from a successful, ID-matched, length-verified read is eligible. No guessed code, no source evaluation, no device control or setting changes. Complete source retrieval does not imply method or root-cause certification. A model can still produce a partial, uncertainty-calibrated answer.

## Tests
Generic late-method extraction, malformed/gapped/incorrect-ID reads, Java UTF-16 offset handling, obvious secret redaction, model-admitted missing method coverage, and normal supported answers. Requires full CI plus live verification after installation.
