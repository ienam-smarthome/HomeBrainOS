# Hubitat MCP AI 0.10.463

## Temporal proof hardening for investigative history

Live 0.10.462 validation showed that current-turn evidence tracking and source ordering
were working, but final synthesis could still compress deterministic temporal proof
into an inaccurate narrative.

The observed Bedroom 3 Light response said the light was on during two periods while
the deterministic history receipt proved five observed bounded intervals. The same
turn also described motion/illuminance evidence as absent even though motion history
was unverified-zero and the illuminance-capable sensor had only been read through a
generic multi-attribute history call.

0.10.463 hardens those generic evidence boundaries.

### Bounded interval proof

History evidence receipts now expose up to 12 bounded interval rows, including:

- start/end timestamps;
- natural start/end text when available;
- duration and duration seconds;
- window-clipping flags.

The current-turn evidence ledger includes the bounded interval timeline (up to six
interval hints plus a remainder count) as well as deterministic intervalCount.

### Interval-cardinality guard

Final answers are checked for exhaustive claims such as "two separate periods" or
"three intervals". When that count disagrees with deterministic intervalCount:

- a smaller list is rewritten as a highlighted subset of the full observed count;
- a larger count is rewritten to the deterministic observed count;
- listed example intervals remain intact rather than being deleted.

This check works with multi-source investigative turns, where the older single-history
duration guard intentionally did not choose between multiple history receipts.

### Attribute-scope proof

Generic device-history receipts now retain a bounded list of observed event names even
when no temporal attribute was selected.

Investigative reasoning is explicitly instructed to set the exact related-device
attribute it wants to correlate (for example motion or illuminance). A generic history
read cannot establish attribute-specific absence.

The API boundary also distinguishes:

- verified attribute absence;
- zero bounded intervals on an unverified event stream;
- generic history that contains an attribute but did not analyse it explicitly; and
- attributes that were never explicitly checked.

### Gateway/sub-tool schema rejection

Before any MCP HTTP call, ToolExecutor now validates a model-selected nested gateway
operation against the gateway tool property's declared enum/const when the schema
provides one.

Invalid combinations such as asking a diagnostics gateway for an undeclared app-list
sub-tool are rejected locally and returned to the reasoning loop. No MCP command is
sent. The new `tool_schema_rejections` metric makes this visible in technical details.

### Regression coverage

Tests cover:

- bounded interval rows and observed event-name proof in history receipts;
- correcting a two-period narrative when deterministic evidence contains five;
- preserving the listed interval examples while labelling them as a subset;
- correcting unsupported motion/illuminance absence wording;
- generic illuminance history requiring explicit attribute analysis;
- invalid gateway/sub-tool rejection before remote execution;
- the schema-rejection metric; and
- investigative prompt guidance for explicit attributes and authoritative interval
  cardinality.
