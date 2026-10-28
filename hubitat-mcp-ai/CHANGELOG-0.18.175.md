# HomeBrainOS v0.18.175 — safe model read-suboperation canonicalisation

## Live causal investigation motivating this release

On 28 October 2026, Investigation V2 asked why Livingroom Light 2
(#7828) last turned OFF. The available evidence identified the most
recent Hubitat-reported OFF transition at 2026-10-28 00:14:57 UTC, and
11 state reports but **zero initiating commands**. Source #7790 was the
state reporter, not verified as the controller initiating the action.
Current Hubitat status was switch=off, networkStatus=online, level=30.

The test took ~70.0s: 20.0s inventory, 21.0s first AI planning and
28.6s second AI planning. Both proposed read calls were rejected
as `tool not in live MCP manifest`. The investigation correctly kept
causal certainty unverified, but made no useful progress after bootstrap.

## Architectural fix

An LLM sometimes expresses an *already advertised read suboperation*
(e.g. `hub_list_device_events`) in the outer `tool` slot rather than
selecting the MCP gateway name (`hub_read_devices`). This is an
argument-shape problem when, and only when, the operation is positively
and uniquely enumerated by a live READ gateway.

The V2 host now canonicalises exactly such aliases before final read
authorisation. It uses only the actual live gateway enum, effect metadata,
one independently verified device ID where needed, and the actual MCP
schema for the complete normalised request. It never rewrites unknown
tool names, contradicting operation names, existing gateway names,
mutators, unsafe arguments or ambiguous gateway ownership. The original
reviewer still independently checks the manifest, schema, source scope,
read budget and no-write arguments before execution.

When an AI round proposes exclusively tools completely absent from the
live manifest, there is now a deterministic stop condition rather than
a second long provider retry that cannot grant new permissions. The
report retains the evidence and missing discriminator, and planning
diagnostics record `canonical_read_aliases` and a bounded
`unavailable_model_tool_count`. This is an evidence-first stop, not
an invented negative finding about available hub data.

## Tests and limits

Synthetic tests prove:
- a real read-operation alias resolves to the unique live READ gateway;
- host-verified ID completion cannot override a model-supplied wrong ID;
- unknown operations, write operations, mutating gateways, overlapping
  gateway owners, contradictory nested arguments and unadvertised
  operations remain rejected;
- a read loop successfully executes the repaired proposal only after
  the original host permission review;
- wholly unavailable model tool proposals stop after one AI round.

This release does not identify source #7790 as an initiating app and
does not claim that a switch event proves a command or historical rule
execution. It also cannot create missing Hubitat command history.
It does not change production Main Ask, device controls, or V2 write
permissions. Actual live causal coverage depends on operations exposed
by the connected Hubitat MCP server.

## Live acceptance

After deploying v0.18.175, repeat the same read-only causal question:

"Investigate why Livingroom Light 2 turned OFF most recently. Examine
its switch history, actual device commands, controlling apps and rules,
and relevant execution logs. Correlate timestamps, identify the most
likely cause, and clearly distinguish verified facts from assumptions.
Do not change anything."

Inspect `planning_diagnostics[].canonical_read_aliases`,
`planning_diagnostics[].unavailable_model_tool_count`, `reads_executed`,
`read_rejection_reasons`, and `stopped_because`.

A positive canonical alias repair may obtain additional relevant source
evidence. If the model selects truly unavailable tools, the report must
stop cleanly without inventing provenance. A causal conclusion remains
unverified until real command/execution evidence supports it.
