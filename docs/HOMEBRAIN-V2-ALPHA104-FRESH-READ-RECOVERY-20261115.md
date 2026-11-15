# HomeBrainOS V2 alpha.104 — recover missing fresh observational reads

**Date:** 15 November 2026. **Scope:** V2 Preview only; PRIVATE source receipts not committed to repository.

## Source-real finding

An installed alpha.103 six-hour Shower Light read produced a successful state-filtered empty native result; the structured ledger correctly showed zero returned matching state reports with incomplete command coverage. A subsequent independent six-hour Bathroom Light history question brought two prior Shower Light receipts but performed **zero new native tool calls**. Nemotron incorrectly assumed a read-only "do not change anything" instruction prohibited fresh observations and treated older unrelated receipts as exhaustive evidence. The existing source review and final audit supplied additional cloud rounds without retrieving a source. The current native catalog was available; this is not a hub/driver source failure or evidence that a switch did not change.

## General intervention

- The current-request tool receipts, not prior context or an old conversation source index, determine whether a fresh source was attempted. Exclude prior-evidence, catalog and clock helper receipts; count genuine native `hub_list_*` / `hub_get_*` / `hub_read_*` or optional Monitor attempts.
- For a current-request historical/causal/source-verification question without any such attempt and with advertised read-only tools, use the **existing** optional model review (no extra model stage). Its short, explicit guidance distinguishes the user's prohibition on device writes from permission for proportionate READ-ONLY observations, cautions against cross-device prior evidence, and leaves live tool/target selection entirely to the model.
- Explicit user prohibitions such as "do not query the hub", "no new tool calls" or "use only previous receipts" disable this special read invitation. Ordinary current-state and device control paths remain unchanged.
- If the model still declines all fresh observation, skip the existing tool-free final audit because it cannot manufacture evidence. Publish an unverified current-request result; do not claim zero historical events or a missing device. If a read is attempted, normal final audit and source-verification paths remain in place.
- Add private telemetry `fresh_source_recovery_invoked` and `fresh_source_recovery_status` with `not_invoked`, `read_succeeded`, `read_attempt_failed`, or `no_current_read_attempt` outcomes. The telemetry attests to tool selection/results only, not factual correctness.

No automatic MCP read, new model stage, polling, provider change, native action/write, approval shortcut, V1 runtime change or private receipt publication.

## Tests and acceptance

Fictional scripted lifecycle covers a source-free first draft with unrelated prior context, an independently chosen live native lookup followed by source read, preserved exact-source ledger, no automatic tools and no extra audit on continuing refusal. Negative cases cover explicit no-read direction, action/write intents, existing source attempts and present vs stale receipts. Existing history/source-review and action-approval regressions remain.

Require exact-head full Python/V2 test suite, UI fixtures, container smoke, metadata, repository and scorecard CI before merge, then post-merge validation. Installed acceptance remains pending. Evaluate one new read-only historical question with original PRIVATE successful receipts and compare identity, chronology, requested/returned bounds, row caps, provenance, source omissions and full token latency. Cross-check a non-exhaustive causal control. Do not treat scripted model execution as a measured gain in Nemotron reliability. Roll back if unrelated requests are intercepted or read-only/write permission boundaries change.
