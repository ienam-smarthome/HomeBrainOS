# v0.18.341 — shared source-claim admission and command-witness negative controls

## Purpose

Continue the permanent Answer Quality roadmap from v0.18.340. This is a cross-domain source-proof foundation and a truthful telemetry caveat correction, **not** a measured speed/quality improvement or permission to publish unrestricted model prose. GitHub's release gate requires a new package version whenever the maintained runtime source changes.

## Changes

- Extract closed-schema, source-catalog-only claim selection into source_claim_contract.py. The current telemetry admission uses the exact established two-key plan schema and source-verified host text; raw model prose remains untrusted.
- Add an **offline-only** recorded-command claim adapter based on source-timed, target-scoped Hubitat device command-event witnesses. A documented app command does not establish its upstream trigger, delivery, acknowledgement or physical device execution. Not connected to live lighting, heating or incident publication.
- Do not claim a device's stored health state was *offline* when healthStatus actually says online, stale or another reported value. A generic unresolved-state caveat now describes the real source value.
- Add adversarial tests for wrong target identity, wrong time window, multiple issuers, state reports misread as commands, model-authored prose, duplicate/unknown IDs, missing material caveats and non-offline health states.

## Safety, performance and acceptance

No new provider or MCP calls, no additions to tool permissions or live home modifications, and no expansion of actual production publisher eligibility. All previously accepted source-typed telemetry plans must remain accepted; original invalid-plan fallbacks continue. This release does **not** establish new free-form model entailment or a causal claim for lighting/heating.

Measured answer-quality results remain **NOT MEASURED** (0 independently certified frozen first-attempt production cases). The v0.18.339 live result (11 rounds, 9 tool calls, 51.152s) is an observational baseline, not an identical-evidence A/B. Verify v0.18.340/341 actual model claim-plan admission and read-loop behavior with one read-only HomeBrain Q&A and complete technical JSON. Exact-head CI release, full Python suite, add-on smoke, metadata and scorecard integrity must all pass before merge.

## Rollback

Revert the shared claim admission extraction and command adapter, restore the original telemetry-only admission function and wording if regressions occur, and revert the version/readme/release note metadata together.
