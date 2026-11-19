# HomeBrainOS V2 alpha.152 — source-reported permission and package provenance

**Status: candidate only.** Alpha.151 private installed capture is intact and unpromoted.
Its 10 first answers returned successfully, with 22 successful of 25 tool attempts,
but the independent review identified an incorrect inventory aggregation,
incorrect elapsed-time prose, and unsupported assertions that stored device
attributes were fresh measurement/health events. The advisory review graded
only **4/10 first answers useful and complete**. A calibrated claim-level
grounding fraction is **not measured**; the alpha.151 permission receipt
requirement was also not satisfied. The original captures are preserved.

## Hypothesis and intervention

The installed read-only acceptance API already executed
`verify_read_only_client` immediately before every capture, with a real
`hub_get_info` native call using the configured token. That response was
not included in the saved first-answer export, so the offline verifier
properly found no source-reported Read ON / Write OFF client. Appending
a fabricated receipt to alpha.151 is forbidden.

Alpha.152 **retains the original already-executed preflight receipt**
under the new top-level private field `permission_preflight_receipt`.
It is labelled `receipt_origin=acceptance_server_preflight`, separate from
model-selected `response.tool_calls`, and contains the original MCP native
envelope rather than reconstructed permission booleans. The verifier accepts
it **only for the distinct alpha152 pack**, requires an executed successful
`hub_get_info` with empty arguments and a genuine text payload, and
extracts only safe global/per-client boolean flags into the public report.
No extra network call is made and no write/approval path changes.
The source report is still **not** an independent test of enforcement.
Permission failure rejects capture before the first-attempt marker.

The add-on Docker build now bundles its exact `config.yaml` as a second
version source. Capture fails closed unless the image build-version
metadata equals the bundled manifest and the expected alpha.152 runtime.
Unknown, missing, or conflicting package provenance is visibly reported,
not represented as `development` or silently substituted with runtime
version. The offline verifier checks each alpha152 export's version and
provenance indicator. No old export is rewritten.

## Scope and boundaries

- Distinct sealed `alpha152-prospective-v1` questions and a new private
  directory: `/data/homebrain-v2-alpha152-acceptance`.
- The alpha145, alpha148, alpha149, alpha150 and alpha151 manifests and
  offline scoring rules remain available without retrofit.
- No model prompt, source routing, model round, answer rewriting, typed
  claim-binding enforcement, native write or safety-approval change.
- This changes **acceptance eligibility plumbing**, **not first-answer semantic
  correctness**. Alpha.151 numerical, provenance and historical failures
  remain open engineering work. A future claim-to-receipt binding experiment
  should measure arithmetic/count errors and event-vs-current-state confusion
  rather than add per-case keyword suppressors.
- Private raw `hub_get_info` receipt remains in the private local capture
  and download; diagnostic report includes only booleans/receipt counts,
  with no client name, credentials, hub URL or original raw answer.

## Expected effect and metrics

A newly installed alpha152 capture using a truly dedicated per-client token
will yield one source-reported Read ON / Write OFF preflight receipt per
completed first attempt, even if the model never chooses `hub_get_info`.
Permission preflight must **not** add to the model-selected native tool-attempt
count. A fresh ten-case pack must be independently source-scored against the
permanent gates: >=90% supported factual claims, zero unsupported definitive
causes, >=80% useful complete answers, and no read-only safety regression.
No installed alpha152 results or outcome improvements are claimed.

## Validation and rollback

Focused fixtures require unknown build provenance to reject capture before
the first attempt; a write-enabled client must still be rejected; the exact
native preflight response must remain separately exportable; the offline
report must accept valid booleans and reject missing, nonexecuted, failed,
non-`hub_get_info`, mislabelled, or inconsistent evidence. Test an alpha151
document to show that the new receipt field is not retrospectively counted.
Use exact-head GitHub Actions for full tests and package validation.
Rollback is the alpha151 merged commit; do not delete or mutate private
capture directories.

## Next operator action after code/CI acceptance

Install alpha152 through the add-on repository. In Hubitat MCP Rule Server,
configure a dedicated per-client Read ON / Write OFF token, then check that
Acceptance study shows package version alpha152 with
`build_arg_and_bundled_manifest_match`. Seal the NEW ten questions,
capture each once, and export the ten private original files plus its offline
report. Independent scoring and per-token source review must precede
any promotion. No alpha151 rerun or receipt injection is permitted.
