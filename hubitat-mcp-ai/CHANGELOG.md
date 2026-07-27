## 0.10.167

### Add the answer guard registry foundation

- Adds an ordered `AnswerGuardRegistry` primitive for same-tier terminal routes
  and answer guards.
- Publishes one request wrapper while keeping small route and guard functions
  independently testable.
- Preserves deterministic registration order and rejects duplicate names,
  late registration, and untracked `application.ask` mutation.
- Adds focused ordering, delegation, catalogue, and safety regression tests.
- Does not migrate existing guards yet, so runtime routing behaviour is
  unchanged in this release.

## 0.10.166

### Instrument the complete request-layer stack

- Captures every live `application.ask` assignment in a typed runtime registry
  without changing wrapper order or request behavior.
- Records the terminal answering layer, tier and traversal count in request
  performance diagnostics.
- Adds `/api/request-layers` for the ordered live layer catalogue.
- Classifies all 51 raw assignment sites across 38 production modules into
  the documented safety-preserving routing tiers.
- Confirms every request layer shares the indexed MCP state broker rather than
  constructing an independent client.

## 0.10.165

### Scale dashboard power units

- Displays dashboard power below 1,000 watts in W.
- Converts dashboard power at or above 1,000 watts to kW with compact
  precision, so 3,190 W is shown as 3.19 kW.
- Preserves decimal precision for sub-kilowatt monitored-device totals.

## 0.10.164

### Add active-room and power dashboard summaries

- Adds an Active rooms tile driven by authoritative motion activity and
  light-on state, with deduplicated room names.
- Adds a Power tile comparing the whole-house meter with the aggregate of
  actively monitored device readings.
- Keeps room and power data independently fail-open so one unavailable source
  does not suppress the rest of the live dashboard.
- Rebalances the six summary cards for desktop and mobile layouts.
- Adds API, room-classification, fallback and rendered-dashboard regressions.

## 0.10.163

### Complete the final layer consolidations

- Folds capability-catalogue safety and duplicate-aware spoken-name resolution
  into `device_intelligence_catalogue.py`.
- Folds conservative per-session follow-up handling into
  `conversation_context.py`.
- Removes three superseded sibling modules while preserving their behavioral
  coverage through the canonical classes.
- Distinguishes ordinary same-family function composition from subclass
  accretion in `scripts/analyze_clusters.py`.
- Reduces the maintained application from 118 to 115 production modules with
  zero import-graph orphans.
- Updates repository documentation for Hubitat MCP AI as the sole add-on.

## 0.10.162

### Recognize intentional analyzer layers

- Adds a narrow, family-scoped cluster-analysis allowlist for the documented
  `ollama_agent_fast` and `ollama_agent_inference` layers.
- Reports those live sibling layers as intentional instead of suspect.
- Keeps unlisted sibling-only modules suspicious and allowlisted modules with
  broken imports visible as failures.
