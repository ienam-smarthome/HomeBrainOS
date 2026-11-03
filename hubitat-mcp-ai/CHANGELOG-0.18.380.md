# v0.18.380 — preserve exact native-read evidence in the final answer

## Observed live quality failure

Installed v0.18.379, literal read-only request for `hub_set_rule operation=read rule 4259 args.sections=["actions"]`: one successful 148 ms MCP read, 1.914s wall, **zero model rounds and one tool call**. Receipt `typed_native_rule_section` contains `sourceSuccess=true`, `projectionVerified=true`, and ordered actions `id=1/value.method=getDelay`, `id=2/value.method=getOnOffSwitch`. No Hubitat writes.

Despite that, user-facing prose was replaced with a generic "Read-only existing-rule verification" claiming actions not independently verified, and `investigation_coverage.questionResolved=false` / `outcome=unresolved`. **Technical retrieval PASS; first-answer usefulness FAIL.** This is a source-to-publication mismatch, not a native MCP failure. Saved delay and switch settings were independently verified in earlier requests, but this actions-only receipt does not establish their parameters, execution or physical effects.

## Cross-domain fix / hypothesis

The orchestrator applies the broad existing-rule claim guard to the successful direct source-read answer; the shared completion layer then repeats whole-rule proof obligations. Introduce a **generic source-scoped completion projection** admitted only when a source-verified, target-matched, nonmutating `typed_native_rule_section` receipt matches the exact requested rule and section list. Both layers use this one contract, preserving original verified native action IDs/methods and honest limitations. The request is resolved only for the **named sections**, not full rule semantics, timing or execution. Failed source reads preserve their bounded actual error and remain unresolved. No extra Cloud rounds/MCP calls or incident-specific output template.

## Measured baseline and expectations

Before: installed v0.18.379 wall **1.914s** (148 ms source HTTP, 165 ms agent), 0 model rounds, 1 MCP tool, 0 modifications; native actions verified in JSON but ignored in final answer. Prior installed v0.18.378 wall 22.202s / 5 model rounds / 6 tools, differing execution path, not paired latency proof. After v0.18.380 **not yet live measured**. Expect source-matched answer preserves IDs/methods, `questionResolved=true`, success outcome, no additional read/model round. Evidence failure and malformed/mismatched receipts must fail closed. Tests are synthetic and cannot certify live answer performance.

## Regression/rollback/safety

Tests replay the actual source-shaped success, source-level error, conflicting IDs/scopes, mutating receipt, missing source success and duplicate action IDs. All required CI must pass at exact head before merge. Roll back the source-scope classification if non-explicit investigations are misrouted. Maintains free-model selection, no live Hubitat/HA writes, and disabled Internet block writer. Permanent Answer Quality Q0→Q4 remains primary. Official broad factual-grounding/first-attempt percentages and Claude parity remain NOT MEASURED.
