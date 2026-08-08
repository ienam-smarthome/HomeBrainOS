# 0.10.371

## Fixed

Live re-testing of 0.10.370 against the real WebUI reproduced an intermittent
`Refused` outcome (zero tool calls, zero evidence gathered) on repeated,
identical "living room light" queries — traced through the server's uvicorn
logs rather than inferred.

Two back-to-back, otherwise-identical requests in the same session each got
exactly one automatic tool-discovery addition (`hub_manage_rule_machine`) for
a total of 15 declared tools, and both completed normally. A third request —
same wording, same session — additionally matched `hub_read_rooms` and
`hub_manage_rooms`, two unrelated room-administration gateways, pushing that
one request to 17 declared tools:

```
Tool hub_search_tools completed in 0.706s
Original-request discovery expanded registry with: hub_manage_rule_machine, hub_read_rooms, hub_manage_rooms
System prompt built in 0.001s (13196 chars, manifest=False)
Ollama streamed round completed in 0.684s with 21 chunks and 17 declared tools
Ollama streamed round completed in 0.745s with 27 chunks and 17 declared tools
```

Both rounds ended without a single tool call, so
`LiveEvidenceAuthority`/`GroundingPolicy` correctly refused to answer (no
verified live evidence gathered) — that refusal logic is working exactly as
intended. The bug is upstream of it: the orchestrator seeds
`hub_search_tools` with the raw, unfiltered original-request text (e.g.
`"living room light"`), and the upstream Hubitat MCP server's own search is a
fuzzy match over tool names/descriptions, not something this app controls —
the substring "room" legitimately, if unhelpfully, ranked
`hub_read_rooms`/`hub_manage_rooms` alongside the actual light-control hit.
`ToolDiscoveryCatalog.discovered_tools()` then declared every ranked gateway
hit unconditionally, with no cap on count and no relevance cutoff, so one
fuzzy word could balloon a routine 15-tool request into 17+ declared tools —
extra surface that correlates with the small cloud model (`gemma3:31b`)
answering across multiple rounds without calling anything at all.

## Fix approach

Added `MAX_DISCOVERED_GATEWAYS = 2` in `tool_discovery_catalog.py` and capped
`discovered_tools()` to upstream's top-ranked hits (upstream already returns
results most-relevant-first — confirmed by the existing
`test_expansion_supports_recognised_result_envelope_and_preserves_order`
test). A cap of 1 would have fully reproduced the known-good 15-tool shape
for this specific case, but a genuine two-gateway need already exists and is
covered by an existing test (`test_expansion_accepts_upstream_search_results_wire_contract`,
"create Rule Machine rule" legitimately wants both `hub_manage_rule_machine`
and `hub_read_rules` declared together) — capping at 1 would have broken that
documented case. Capping at 2 keeps it intact while still bounding what was
previously unbounded growth and dropping the long incidental tail beyond
upstream's top two hits.

This is a structural bound on discovery-result count, not prompt-text
keyword filtering — `tool_discovery_catalog.py`'s existing rule that it
"never inspects user prompt text" still holds; the query sent to
`hub_search_tools` is untouched, only how many of its ranked hits get
declared is now bounded.

Note this narrows, but does not claim to fully eliminate, the observed
`Refused` outcome: the correlation between declared-tool-count and the model
skipping tool calls is drawn from one reproduced live case, not a controlled
experiment. If `Refused` outcomes continue to recur on tool-discovery-bloated
requests after this ships, the next step would be tightening the system
prompt to more forcefully require at least one tool call before answering,
or reducing `MAX_DISCOVERED_GATEWAYS` further at the cost of the
multi-gateway rule-authoring case above.

## Validation

- `python -m pytest -q` — 628 passed (1 new: `test_tool_discovery_catalog.py`
  case proving a 3-hit search result is capped to the top 2 declared
  gateways, reproducing the live "living room light" over-expansion and
  confirming the incidental third gateway is dropped).
- `python scripts/run_release_gate.py` — 623 passed
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` — 0.10.371
- `python scripts/analyze_imports.py` — `orphan_modules: []`
- Live re-check pending: re-run "living room light" repeatedly against the
  real WebUI to confirm the registry now stays at 16 declared tools (14
  initial + `hub_manage_rule_machine` + at most one room gateway) instead of
  17, and check whether `Refused` outcomes on that query become rarer.
