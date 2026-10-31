# v0.18.271 — Stable source-witness aliases and evidence-grounded alternatives

## Live acceptance finding (v0.18.270)

HomeBrain recovered the complete 30 October two-light switch sequence, correlated the independent sensor reception stream (7895: 5/5 ON and 5/5 OFF), actually read input 7895's Hubitat dependents, and read the configuration of a currently shared app (4129). The missing initiating command provenance remained correctly unresolved.

The authoring model's structured witness envelope was invalid: 1 claim supported and 5 rejected with allowlisted reason `missing_witness`; the exact bad witness identifiers were not exposed. The existing source-only brief correctly avoided publishing an invalid model-authored explanation. However the shared completion layer appended a repetitive list of generic competing explanations after the concise brief despite being able to compare source evidence.

## Fixes

- `source_witness_aliases` binds short references such as `w_t1_on`, `w_t1_off`, `w_t2_on` and `w_t2_off` to the first independently source-timestamped ON/OFF witness for each source-qualified target. Mapping is regenerated from the **current request's** witness ledger, never a remembered device name, previous session or supplied model mapping.
- The exact existing `homebrain-claims.v1` role/clock/target validator receives resolved witness IDs. Unknown aliases, collector-reception-only evidence, wrong-target aliases and unsupported command issuers still fail closed; the publication gate uses the identical resolved IDs.
- The model prompt uses short aliases instead of cryptographic-length hashes. This reduces copying difficulty but is not assumed to guarantee valid output; the previous short source-verified fallback remains.
- A new pure source-comparison module contrasts a verified input's complete same-collector receptor pairing against the best other retrieved input **without equating their differing clock windows or treating truncated retained samples as complete**.
- `shared_investigation_completion` no longer appends generic proposed hypotheses after verified source-brief or claim-guided publication; for **explicit** comparison requests it uses only this checked source contrast. Unrequested comparisons and other investigation domains retain their existing behavior.

## Scope

All changes are read-only and request-local. No additional MCP calls, no Hubitat or HA writes, no new model rounds, no invented source event time and no unverified app-command attribution. The match between 7895 and both lights is still correlation and the original ON issuer remains unverified.

## Regression gates

Valid short aliases, wrong-target/unknown alias rejection, IDs renamed across fixtures, model prompt examples, source-comparison boundedness, truncated archive disclosure, and shared final-completion suppression of generic speculative hypotheses. Full Python suite, repository validation and container smoke testing are release blockers.
