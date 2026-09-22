# Hubitat MCP AI 0.16.6

## Control-path hardening

0.16.6 closes three correctness and observability gaps found during a fresh
full-code audit.

### Preserve the real Hubitat dispatch failure

A thrown exception from `hub_call_device_command` could enter the local
exception handler before the `result` variable had been assigned, then the
failure-reporting path inspected `result.data`. That could replace the real
Hubitat/transport failure with a local `UnboundLocalError`.

The command result is now explicitly initialized before dispatch, so transport
exceptions stay on the normal deterministic failed-command path and preserve the
original failure reason.

A regression test raises from the MCP transport boundary and proves that:

- the request returns a normal failed control result;
- no mutation is reported as successful;
- the original transport error remains visible;
- the request records `device_control_failures`;
- no `UnboundLocalError` escapes.

### Cumulative provider timing

Provider timing now accumulates across model rounds instead of replacing the
previous round's value. Multi-round requests therefore report total provider
time in Technical details rather than only the final model round.

### Enforce `rule_write_enabled`

The existing add-on setting `rule_write_enabled` is now authoritative.

When disabled:

- bounded deterministic Rule Authoring requests are rejected before discovery;
- model-generated mutating `hub_manage_rule_machine` calls are blocked before
  they can reach Hubitat;
- no rule is queued, changed, or executed.

Read-only Rule Machine discovery remains unaffected.
