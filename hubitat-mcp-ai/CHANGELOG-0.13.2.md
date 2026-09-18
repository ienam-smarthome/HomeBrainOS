# Hubitat MCP AI 0.13.2

## Post-enrichment boundary evidence and direct provenance registry

0.13.2 follows the first live validation of 0.13.1.

The 0.13.1 run achieved the intended runtime improvement:

- outcome changed from Unresolved to Success;
- model rounds dropped from 8 to 3;
- total latency dropped from 52.7s to 22.7s;
- no speculative generic-dimmer or Ikea controller lookup occurred after the
  correct Bedroom 3 controller had been established; and
- both material intervals and both aligned physical button events survived final
  synthesis.

The live run also exposed two generic gaps.

### Boundary evidence after inferred history attributes

The model called semantic history without an explicit state attribute.

That is a supported path: HomeBrain fetched the bounded event page, then
`history_result_enrichment.py` inferred `switch` from the returned state rows and
constructed the deterministic interval analysis.

0.13.1 selected `boundaryEvents` inside `DeviceHistoryService`, before that
post-fetch inference. Therefore inferred histories had valid intervals but no
preserved boundary rows.

0.13.2 imports the existing `boundary_event_evidence()` selector into the
post-fetch enrichment stage and derives boundary rows after all deterministic
attribute/temporal inference.

This makes boundary retention independent of whether:

- the caller explicitly requests `attribute=switch`; or
- HomeBrain safely infers the one unambiguous supported binary attribute.

The resulting evidence receipt still keeps its normal newest-first
`observedEvents` cap, while `boundaryEvents` separately retains rows near the
investigated interval starts/ends.

### Canonical gateway operation view

The live provenance phase called the diagnostics gateway using the wrapped schema
shape:

`{"args":{"tool":"hub_get_logs","args":{...}}}`

Existing evidence and grounding helpers recognized only the direct shape:

`{"tool":"hub_get_logs","args":{...}}`

New `gateway_argument_view.py` supplies one canonical read-only interpretation of
both shapes.

It is now used by:

- `EvidenceRecorder` when storing `sub_tool`;
- `GroundingPolicy.is_live_log_call()`; and
- `ToolDiscoveryCatalog.gateway_operation_error()`.

The original provider payload is not rewritten.

### Known provenance gateways without fuzzy discovery

The causal-completion phase is already narrow, so 0.13.2 no longer requires
`hub_search_tools` merely to expose an app/rule/log read gateway that MCP
`list_tools` already reported as installed.

The completion registry now contains at most:

- `hub_search_tools`;
- `hub_read_diagnostics` when available;
- `hub_read_apps_code` when available;
- `hub_read_rules` when available; and
- one additional read-only gateway whose name/description/schema clearly exposes
  app/rule/log/diagnostic evidence.

Device/history/location and mutating gateways remain excluded.

The completion instruction permits up to two complementary read calls in that
single model round when both materially test the same command source, such as logs
plus the most relevant app/rule configuration.

This can improve command-source identification without reopening general device
exploration or adding another model round.

## Regression coverage

0.13.2 adds tests for:

- an attribute-less semantic history inferring `switch` and then preserving
  boundary command rows;
- boundary rows surviving when they fall outside the ordinary newest-16 receipt
  window;
- canonical direct/wrapped gateway operation and argument extraction;
- nested `hub_get_logs` recognition by grounding;
- nested diagnostics receipts recording `sub_tool=hub_get_logs`; and
- causal completion activating known app/rule/log read gateways even when they
  were not part of the normal initial declared registry.

## Live acceptance target

Repeat the same Bedroom 3 causal question.

With the same underlying Hubitat rows, the run should:

- remain Success;
- remain close to the 3-round 0.13.1 shape;
- populate boundary-event evidence even when the history call omits an explicit
  switch attribute;
- recognize a wrapped diagnostics call as `hub_get_logs`;
- avoid a discovery round when the needed provenance gateways are already known;
- allow one bounded round containing complementary log/app-rule reads when useful;
- preserve both controller-aligned material intervals in final synthesis; and
- identify the downstream app/rule when the available provenance evidence actually
  supports it, otherwise leave that source unresolved.
