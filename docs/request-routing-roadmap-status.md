# Request-routing roadmap status

## Thread 1 — request routing

### Step 1: typed capture and tracing — complete

- Every maintained `application.ask` assignment is captured by the typed request
  layer tracker.
- Request diagnostics report the terminal answering layer, tier and traversal.
- `/api/request-layers` exposes the live ordered catalogue.
- Maintained layers share the indexed MCP state broker.

### Step 2: routing-tier documentation — complete

The deterministic write, deterministic read, semantic evidence, AI synthesis,
terminal-route and answer-guard boundaries are documented and covered by tests.

### Step 3: same-tier registry consolidation — structurally complete

The maintained public entrypoint now publishes four ordered registry wrappers:

1. Hubitat health display guard.
2. Semantic home summary and semantic home query terminal routes.
3. Thermostat live-state route, home-summary consistency guard and thermostat
   summary guard.
4. Named-rule status route, climate extrema route and execution-contract guard.

Named-app control remains a separate control installer because it is not an
answer-guard or read-only terminal-route concern. Runtime HTTP route rebinding is
also deliberately separate and runs only after request composition is finalised.

`scripts/audit_request_registry_migration.py` is a blocking structural audit. It
fails when registry order changes, a migrated legacy installer is reintroduced,
the wrapper count changes unexpectedly, or runtime route setup occurs before
composition finalisation. The blocking release gate runs the complete `tests`
suite, with only the explicitly listed historical baseline quarantined as xfail.

#### Required live performance proof — pending measurement

Structural consolidation alone does not prove reduced Hubitat load. Before this
step is called performance-validated, capture equivalent live request-trace sets
from the pre-consolidation and consolidated releases and compare:

- request count;
- total and mean MCP calls;
- total and mean MCP busy duration;
- mean end-to-end elapsed time.

Use the same prompts, order, cache warm-up and sample count for both runs. Export
the trace JSON as `before.json` and `after.json`, then run:

```powershell
python scripts/summarize_request_trace_metrics.py before.json after.json --output request-routing-live-metrics.json
```

Commit the resulting measurement artifact or record the values in this document.
No improvement is claimed until real live data has been collected.

### Step 4: optional planner redesign — deferred

No planner redesign is required to close the deterministic routing consolidation.
Planner work should begin only as a separate milestone with its own behavioural
and safety scope.

## Thread 2 — Device Health Monitor state bloat

A state-pruning migration has been prepared for the Hubitat Device Status Notifier
app. Live Hubitat app-statistics evidence is still required to confirm the state
size after the migration runs.

## Known debt outside this milestone

- Historical quarantined tests remain expected failures until individually fixed.
- Compatibility adapters remain for external callers, but the maintained runtime
  does not reinstall their legacy wrappers.
- Changelog history predating 0.10.162 remains incomplete.
