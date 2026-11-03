# 0.18.374 — verified partial source-history join (Q2)

## Evidence and hypothesis

The first installed v0.18.373 read-only MQTT health comparison answered in 57.559 s (8 Gemma4:31b free rounds, 9 tools; provider 51.182 s). It definitively called the outage an application-telemetry failure / ghost connection despite `rootCauseVerified=false`, `questionResolved=false`, and all three hypotheses being unverified. This is one verified **first-answer causal-grounding failure**, not a model-wide performance estimate. No physical transport proof was provided.

Root cause of a **separate, independently inspectable software path failure:** a direct scoped `hub_list_device_events` receipt reported 19 rows, while the matching deterministic `homebrain_device_history` receipt retained 16 and explicitly marked `observedEventsTruncated=true`, with `sourceEventCount=analysisEventCount=19`. The source-typed history normalizer previously demanded exact row-count equality, returning no packet. The final user-facing model narrative therefore escaped the normal source-backed, no-cause publication path. This does not prove that correcting source admission alone fixes every unsafe model claim.

## Change

- Admit **only an explicitly truncated** immediate derived history paired with a successful target-ID-scoped native receipt when its declared source and analysis counts both agree with the native summary and its retained rows are a strict positive subset.
- Preserve the difference between **source-reported rows** and **retained, inspected rows**; do not infer missing rows' content, event types, origin, causality or last physical packet.
- Publish an explicit partial-history warning in both concise and detailed source-typed answers. Continue reporting offline/connected as saved Hubitat attributes, not broker/physical proof.
- Keep all existing no-write, source scope, multiple-match rejection and clock-consistency guards. No extra reads, tool/model rounds, model/provider routing or cloud inference.
- Add synthetic cross-domain positive and adversarial negatives plus a shared-completion regression requiring replacement of an unsupported causal model draft.

## Verification and metrics

**Observed before:** One v0.18.373 first attempt = causal-grounding FAIL, first-usefulness for confirmed cause FAIL, 57.559 s elapsed vs preferred <45 s, read-only safety PASS. Source-backed projection absent; no formal comparative model sample.

**Expected offline after:** In a controlled 19-reported/16-retained fixture, normalisation changes from `None` to 16 observed rows with 3 explicitly unshown and a source-backed uncertainty-bearing final publication. No inferred additional observations.

**Real-world after:** NOT MEASURED until version deployment and a fresh first attempt. AI semantic accuracy, cause-resolution rate, latency improvement, same-packet A/B and Claude parity remain NOT MEASURED. CI/unit passes demonstrate source-contract behavior only, not a real-world accuracy percentage.

**Risks:** A native summary might disagree with derived source counts; these cases continue to fail closed. A truncated sample may omit decisive commands or physical evidence; never upgrade its completeness. Source-typed fallback can be more rigid than model prose. **Rollback:** Revert this release's changes to `typed_device_history_evidence.py` and version references. No live Hubitat or HA device/config changes were made.
