# Hubitat MCP AI 0.16.87

## Adaptive evidence-use consolidation

This release builds on 0.16.86 and closes the remaining evidence-use gaps found in the 0.16.85 live proof without expanding retrieval or adding provider rounds.

### Exact adaptive target provenance

Adaptive device/app diagnostics now preserve the exact `hub_get_performance_stats` row that selected each scoped target. The receipt records target kind, ID, name, selection score, the original performance row, and whether the row identity matches the scoped target. This makes the retrieval decision auditable without re-resolving names from final prose.

The public `select_adaptive_log_targets()` return shape remains backward compatible; richer provenance is internal to evidence receipts.

### Long-running operations vs network causes

Comma-formatted Hubitat WARN durations remain normalized as introduced in 0.16.86. The final evidence-use guard now prevents a very long `runQ`/operation duration from being promoted into an unsupported network/connectivity or API-latency cause. Long-operation evidence supports a calibrated long-running/stalled-operation hypothesis only unless explicit failure/connectivity evidence is also present.

### Literal WARN/ERROR preservation

Current-turn WARN/ERROR rows are preserved as literal observations through the final semantic stack. Generic wording such as "returned activity is worth reviewing" no longer replaces an available concrete warning such as a slow internal `/logs/json` request.

These observations remain bounded: a warning does not by itself prove it caused the longer-window performance statistics.

### Same-second cluster recommendations

A same-second timing cluster remains an observed timing pattern. Recommendations are inspection-first unless configuration evidence establishes that scheduling/reporting is configurable and that a particular change is safe and necessary. The final guard therefore avoids directly prescribing staggering, offsets, or frequency changes from cluster evidence alone.

### Adaptive ranking compatibility

The 0.16.86 retrieval policy remains unchanged: 15% busy share may enter the bounded ranking while 20% remains a stronger priority bonus. The release adds regression coverage proving a near-threshold busy-share app can win the single adaptive app slot and that its exact source row is retained in the evidence receipt.

### Architecture unchanged

- Quiet broad-performance request: 3 host reads, 0 exploratory agent rounds, 1 synthesis round.
- Adaptive request: maximum 5 host reads, 0 exploratory agent rounds, 1 synthesis round.
- At most one device-scoped and one app-scoped diagnostic read.
- No extra provider round, no broader diagnostic fan-out, and no duplicate performance snapshot replay.

### Regression coverage

The release gate covers:

- comma-formatted Nest long-call WARN classification;
- long-running-operation evidence not being converted into an unsupported network cause;
- near-threshold SenseCap target selection with exact-row provenance;
- literal MCP Rule Server WARN preservation through final semantic validation;
- inspection-first guidance for same-second Octopus timing clusters;
- backward-compatible adaptive target API shape; and
- executor compatibility when optional result-detail helpers are absent.
