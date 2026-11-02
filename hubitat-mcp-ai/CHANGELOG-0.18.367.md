# Hubitat MCP AI v0.18.367 — fix read-only source-checkpoint metrics crash

## Verified live failure

On 2026-11-02 the user's explicit **read-only** native Rule Machine inventory/reference investigation failed before it returned a result:

```
Request failed: Unsupported metric counter: investigation_source_checkpoint_offered
```

The installed add-on was v0.18.366. This is an application-side metrics bookkeeping exception, **not** a Hubitat Rule Machine error or proof of a rule mutation. The failed request returned route=`error`, `success=false`; no complete tool receipt was provided, so investigation evidence/outcome are unknown.

## Root cause and fix

The orchestrator's `offer_source_checkpoint()` counter call chooses its name via a conditional string expression, either `investigation_source_checkpoint_offered` or `investigation_source_checkpoint_suppressed`. Neither value was present in `RequestMetrics.ALLOWED_COUNTERS`. The existing v0.17.31 AST registry regression test only checked **direct constant** metric arguments and therefore did not catch either branch. Two additional existing metric callbacks (`investigator_producer_config_read` and `investigator_archived_producer_log_read`) were also absent from the registry because the callback was passed under `increment_metric`, not `increment_active_metric`.

- Add precisely those four bounded privacy-safe counters to the allowlist; retain `ValueError` for unknown/private counter labels.
- Extend the static runtime source scanner to check **both branches of a conditional expression** and literal metric names passed through the existing `increment_metric`/`count_metric` aliases.
- Add active-request synthetic tests for the checkpoint-budget permitted and suppressed paths, counter snapshots, source callsite AST, injected callback counters and malicious/unregistered metric rejection. No Hubitat tool calls or live configuration changes.

## Outcome and measurement

Target: the exact pasted read-only investigation can return a result rather than a bookkeeping exception. The fix does not guarantee that a valid native parent or surviving dated one-time rule exists. No native creation, live Hubitat/HA mutation, rule cleanup, tool permission or confirmation changes are introduced.

The captured pre-fix failure is a real first-shot crash. **Actual installed v0.18.367 after-result, answer usefulness and wall-time are NOT MEASURED** until user repeats the same question and provides the Technical JSON. Green synthetic tests alone are not a factual accuracy or latency score.
