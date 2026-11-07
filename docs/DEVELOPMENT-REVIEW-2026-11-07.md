# HomeBrainOS development review — 7 November 2026

## Verified baseline

Reviewed main `070f6f9b19248868ef4d44096425629b9cab2b9f`, AGENTS, charter, active status/handoff, autonomous roadmap, evaluation guide, 53-case inventory, recent claim-migration PRs, open PR metadata, adapter/response integration and capture tooling. This is a focused current-development review, not a claim that every historical PR or runtime module was audited.

The maintained component is `hubitat-mcp-ai/`; current release is **0.18.455**. PR #1514 merged as `adf9e5ca1ff046ca85c8687d5b4010e9bb8c76fc`; documentation PR #1515 merged as the reviewed main above. GitHub Actions independently confirms successful Release assurance, Hubitat MCP AI tests, Validate HomeBrain OS and Answer Quality scorecard integrity on implementation head `33d9d911377cb76c9a8fabcec56c25deaceca132`. Existing release notes record 6,747 passing Python tests and container smoke. These are code-verification results, not a model-quality denominator.

## What has progressed

- v0.18.451 introduced canonical source-role, clock, focal-scope and coverage claim validation.
- v0.18.452 added a narrow claim-validated factual floor for eligible failed causal repairs.
- v0.18.453 connected host-generated source packets to a non-publishing diagnostic.
- The installed v0.18.453 response failed diagnostic acceptance: optional domain and correlation markers prevented the adapter from running. Its bounded global past-log query did include the OFF instant; zero returned rows do not exclude app/rule execution.
- v0.18.455 permits independently attested latest-OFF device history to activate the existing guard/diagnostic route. This remains a narrow latest-OFF integration, not general cross-domain model-selected claims.
- The current sidecar explicitly reports `model_claims_assessed=false`. It assesses host-generated evidence claims, not every sentence in the natural-language answer.

## Next uncompleted milestones, in order

1. **Installed v0.18.455 acceptance.** Obtain the full answer and Technical JSON for the unchanged original read-only latest-OFF question. Inspect diagnostic presence, focal attestation/source, source-vs-collector clocks, bounded negative evidence, listener roles and speculative cause ranking. Treat changes in retained evidence and query choices separately from code changes. No historical controller or first-attempt deployment provenance is verified yet.
2. **Preserve observation metadata.** The existing privacy-minimal capture discarded the new diagnostic entirely. This change preserves missing/invalid/provided state, rejection-status presence, strict reported booleans and two fixed focal-source labels. It exports no arbitrary reason/source strings or witness payloads and cannot assign an answer grade.
3. **Frozen typed-claim comparison.** Use the existing 40 synthetic/anonymised packets plus 13 legacy task definitions without changing questions/rubrics to fit this incident. Introduce model-proposed typed-claim envelopes in an offline comparison before enabling a model-facing menu or replacing publication. Fix model/settings, packet hashes and attempt provenance; source-review factual support, unsupported causes, usefulness and downgrade rate. Current generic held-out quality remains unmeasured.
4. **Publication simplification only after evidence.** Retire overlapping prose guards only when matched evaluations show supported facts and useful first answers are preserved. Avoid another per-device phrase correction.
5. **Source completeness and continuation.** Evaluate app-specific execution/decision evidence, actual native sensor windows, time-series pagination and progress-based continuation across domains. A general hub-log request is not complete app execution coverage.

## Open PR disposition

| PR | Observed state | Development action |
| --- | --- | --- |
| [#1502](https://github.com/ienam-smarthome/HomeBrainOS/pull/1502) | Open, mergeable=false; older v0.18.449 causal implementation | Compare any unique hunks against merged #1503 and later fixes before closing as superseded; do not merge its stale version metadata. |
| [#1183](https://github.com/ienam-smarthome/HomeBrainOS/pull/1183) | Open, mergeable=false; v0.18.292 opt-in cloud benchmark | Retain as historical candidate pending comparison with current benchmark services. Any useful work needs a focused port to current main and fresh CI. No cloud benchmark call was made. |
| [#1147](https://github.com/ienam-smarthome/HomeBrainOS/pull/1147) | Draft RFC, mergeable=false | Keep as design reference; its description explicitly requests competing architecture review before merge. Reconcile with current typed-claim roadmap. |

No old PR was closed or merged as part of this review.

## Open issue backlog to reconcile against current code

Seven open issue records remain. Their historical descriptions do not prove the same defects persist in v0.18.455. Prioritise source-contract and acceptance reconciliation: [#942](https://github.com/ienam-smarthome/HomeBrainOS/issues/942) proposal-only identity/native-rule preflight; [#923](https://github.com/ienam-smarthome/HomeBrainOS/issues/923) typed action overlap and scheduler provenance; [#828](https://github.com/ienam-smarthome/HomeBrainOS/issues/828) upstream fresh bulk-health inventory; [#758](https://github.com/ienam-smarthome/HomeBrainOS/issues/758) room-status completeness and timestamps; [#733](https://github.com/ienam-smarthome/HomeBrainOS/issues/733) whole-hub optimisation evidence; [#725](https://github.com/ienam-smarthome/HomeBrainOS/issues/725) configuration markers versus runtime failure; [#686](https://github.com/ienam-smarthome/HomeBrainOS/issues/686) concrete performance-target naming. Keep these as cross-domain evaluation candidates, verify current implementation and fresh source acceptance before closing, and avoid reviving obsolete intent-routing rules from old issue text.

## Continuity improvements

AGENTS still described v0.18.451 as the current migration checkpoint, while the status/roadmap correctly documented v0.18.455. CLAUDE.md also retains an obsolete “512 tests” line and a three-workflow summary. Prefer exact-head Actions results and current handoff over those historic counts. This review refreshes the primary AGENTS checkpoint; historical status entries remain chronological records rather than current acceptance claims.

## Validation and limits

Capture changes are offline tooling only; add-on version stays 0.18.455. Local Python compilation and a standard-library smoke check passed. The bundled local Python has no pytest, so pytest verification ran in PR CI. [PR #1516](https://github.com/ienam-smarthome/HomeBrainOS/pull/1516) passed all four required workflows on exact head `975202fa56d3d54ee0e32681d5f7909b5d63ba6f`: **6,756 Python tests**, two nonblocking warnings, container smoke, metadata, Hubitat gate and scorecard integrity. Squash merge: `bcded55b65703406cd337763112e9e9b756e120b`. The Hubitat workflow now includes capture script/test paths so these changes trigger its blocking gate. Regression tests cover missing/rejected/unattested diagnostics, both source paths, unknown schemas, strict booleans and private-field exclusion.

No Home Assistant/Hubitat device, rule, provider, cost policy, confirmation or runtime publication was changed. Rollback is a revert of the capture fields/tests and documentation; existing captures remain readable because the new summary is additive. Installed quality, first-attempt provenance, deployed SHA and initiating controller remain unverified.
