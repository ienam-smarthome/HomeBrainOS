# Hubitat MCP AI 0.13.5

## Causal evidence pipeline and write-state isolation

0.13.5 follows the first live 0.13.4 causal run.

The 0.13.4 evidence layer correctly retained `windowEvents` and activated the
known-history fast path, but the live request exposed two architectural problems:

- a read-only causal investigation ended as `request_class=write` and the final
  analysis was replaced by the unverified-mutation refusal even though every
  recorded evidence receipt was read-only; and
- the investigation still consumed eight model rounds / thirteen tool calls /
  37.4 seconds before finalization.

## Root cause: fail-closed execution classification leaked into request semantics

Unknown/undeclared model tool names are intentionally classified fail-closed as a
sensitive write by `classify_tool_effect()`. That is the correct safety posture for
execution.

The orchestrator also used the same classification to set
`_mutation_call_seen` before checking whether the named tool was actually declared.
A hallucinated unknown tool during a read-only investigation therefore:

1. could not execute;
2. produced no mutating evidence;
3. nevertheless changed the whole request to `write`; and
4. caused `_unverified_mutation_guard()` to discard the final causal answer.

0.13.5 separates those responsibilities.

- `_mutation_requested_by_user` records explicit user mutation intent.
- `_mutation_call_seen` now records only a real declared mutating tool selection.
- unknown tools remain blocked/fail-closed for execution but cannot promote an
  unrelated read request to `write`.
- the unverified-mutation guard still applies when the user requested a write, even
  if the model only attempted an undeclared/non-executable tool.

This preserves mutation safety without allowing model tool-name mistakes to corrupt
read-only answer semantics.

## Fixed causal evidence acquisition layer

Once a causal subject history establishes bounded transitions, HomeBrain now gathers
the stable subject-adjacent evidence layer host-side:

1. exact-room device discovery;
2. one highest-ranked same-room controller/button history when available; and
3. one location/mode history read.

The model no longer spends separate unrestricted rounds deciding whether to fetch
those same evidence classes.

Metric:

- `causal_location_read`

## Location evidence is clipped to the active history window

The 0.13.4 live run asked about an ongoing "last night" window beginning at 18:00,
but its location history still contained a `Late Night` mode event from 01:30 that
morning, outside the investigated window.

`homebrain_location_events` now binds to the same active semantic history window
used by device history.

When a semantic window is active it:

- resolves the hub timezone;
- fetches enough bounded location history to cover the requested start;
- uses the 50-row local ceiling before filtering; and
- keeps only events whose timestamps fall inside the requested start/end bounds.

The filtered rows are used both for model tool content and authoritative location
evidence receipts.

## One bounded provenance round

After the host-owned controller/location layer is complete, HomeBrain immediately
switches from the general registry to the causal provenance registry.

The next model round may choose only installed read-only provenance gateways such as:

- native diagnostics/logs;
- app/config reads; and
- Rule Machine rule reads.

After that provenance tool round, HomeBrain immediately enters shared final
synthesis.

This replaces repeated general "think -> ask for another context source -> think"
cycles with a data-first pipeline:

`subject history -> controller/location evidence -> one provenance round -> synthesis`

## Installed provenance readers before fuzzy discovery

The causal provenance registry already knows the MCP tools returned by
`list_tools`.

0.13.5 therefore no longer exposes `hub_search_tools` alongside installed
provenance read gateways.

If one or more suitable installed readers exist, only those readers are exposed.
Fuzzy search remains a compatibility fallback only when the MCP registry contains
no suitable provenance reader at all.

This removes the extra `hub_search_tools("list apps rules")` round seen in the
0.13.4 live run.

## Regression coverage

0.13.5 adds/updates tests for:

- a read request containing an undeclared model tool call remaining
  `request_class=live-read`;
- existing explicit write requests still receiving unverified-mutation protection;
- semantic location history clipping out events before the active window;
- authoritative location receipts using the same clipped event set;
- `causal_location_read` metric support;
- causal provenance views excluding fuzzy search when installed readers exist; and
- search remaining available as a sparse-registry fallback.

## Live acceptance target

Repeat the same Bedroom 3 causal question after installing 0.13.5.

Expected:

- `request_class=live-read`;
- no unverified-mutation refusal;
- `history_known_tool_fastpath=1`;
- `causal_room_plan=1`;
- `causal_location_read=1`;
- controller history checked at most once;
- location evidence contains only events within the active "last night" window;
- causal completion does not call `hub_search_tools` when native
  diagnostics/apps/rules readers are already installed;
- one bounded provenance tool round followed by final synthesis; and
- materially fewer than the 0.13.4 eight model rounds / 37.4 seconds.
