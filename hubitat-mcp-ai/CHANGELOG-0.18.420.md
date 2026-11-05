# HomeBrainOS v0.18.420 — requested guide contract must be assessed

## Live 0.18.419 acceptance (5 November 2026, 18:05 UTC)

An installed v0.18.419 preflight verified MCP Rule Server 5.1.6, the latest hub-local backup at 03:02:31 UTC, both readable tool-guide sections, built-in Rule Machine parent app 169/type 18 and 42 returned child-parent links. The non-rendering source path passed: 6 external MCP reads plus one local typed projection, no native writer, editor page or model round, wall-time 4.185 s (1.3 s agent).

However the same request explicitly asked to report `nativeGuideContract` and guide evidence gaps. The preflight's intent detector did not recognise that structured reporting objective as a request to inspect date/creation fields. As a result `nativeGuideContract` was a default object with `gapCodes=["guide_unavailable_or_oversized"]`, although both guides were readable, and `investigation_coverage.evidenceComplete=true` / UI Success misrepresented the uninspected requested contract. This is a **scope/completion honesty defect**, not a new upstream failure.

## Correction

- Treat positive requests to report `nativeGuideContract`, guide declarations or guide evidence gaps as verification obligations for the existing typed date-field and native creation guide checks. Ignore prohibitions.
- Independently inspect the already fetched `set_rule_reference` guide for its source-declared contract fields on every preflight; this adds **no MCP reads**, form renders or AI rounds. Publish safe structural booleans and gap codes, never raw guide content or acknowledgement keys.
- Expose `inspectionStatus` (checked, guide-unavailable or guide-oversized). Do not label an uninspected default as a missing or oversized guide; distinguish unreadable/empty guide from a read-size guard.
- Complete a simple server/backup/guide availability preflight on its own scope; do **not** mark requests for date/creation guide proof complete when those declarations are absent. Keep `preflightEvidenceComplete` distinct from `evidenceComplete` and `readinessForMutation=false` independent of completion.
- Synthetic regression tests replay the live 0.18.419 wording, alternate positive guide-reporting phrases, simple preflight budget, negated clauses, no app-page rendering and zero writer calls.

## Evidence boundaries / performance

The installed MCP 5.1.6 guide does **not** list the exact `atDate#` typed input contract that the detector requires, whereas upstream MCP Server PR #576/issue #575 verified `atDate#` date input support and `yyyy-MM-dd` through upstream tests. An omitted declaration is not a proof of unsupported functionality. No existing verified enabled saved dated trigger or runtime one-time firing was identified; native rule writes remain disabled and separate confirmation will be required before any write.

Expected impact: same source-call budget and no additional provider rounds. CI proves only synthetic regression behaviour; repeat the same read-only question on installed 0.18.420 for acceptance. Continue the permanent Answer Quality roadmap rather than multiplying request-specific stages.
