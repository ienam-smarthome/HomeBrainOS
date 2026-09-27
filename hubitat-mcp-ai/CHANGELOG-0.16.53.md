# Hubitat MCP AI 0.16.53

## Performance synthesis causality hardening

- Fixes the remaining wording gap exposed by the second 0.16.52 live performance retest.
- Recent logs may establish repeated Rule Machine activity, but they cannot be promoted to the `primary driver`, `main cause`, `major contributor`, or equivalent explanation of a measured busy/load/latency statistic without direct linking evidence.
- Labels such as `Confirmed Hypothesis` are downgraded to an explicitly unproven hypothesis in performance+log answers.
- Legitimate measured ranking remains untouched. For example, `LG webOS TV is the primary device-side performance concern at 16.3% busy` remains valid when supported by performance statistics.
- Threshold-crossing interpretation remains evidence-driven: a structured sample that genuinely contains readings on both sides of the threshold is not rewritten merely because a separate causal claim is unsafe.

## Regression coverage

The release includes the exact 0.16.52 escape pattern:

- `TV Power Trigger Loop (Confirmed Hypothesis)`
- `This is the primary driver for the high busy percentage of the LG TV.`

The guard now localizes those phrases while preserving the supported observation that the rule repeatedly triggered and restarted during the sampled log window.
