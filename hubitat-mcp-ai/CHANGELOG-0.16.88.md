# Hubitat MCP AI 0.16.88

## Evidence-safe device freshness semantics

This release fixes the false stale/offline reporting path tracked in #687. Device activity age is now treated as an observation unless the current evidence contains an explicit freshness contract or a direct offline/unreachable signal.

### Quiet devices are not failed devices

Capability heuristics such as temperature or power measurement no longer imply that a device must report on a fixed cadence. An old `lastActivity`/activity timestamp by itself therefore does not justify claims that the device is stale, offline, unreachable, interrupted, or has stopped reporting.

Age-only findings remain available as neutral diagnostic context where useful; they are not promoted into failure warnings.

### Explicit offline evidence remains actionable

Direct health evidence is unchanged. Explicit `offline`, `unreachable`, or equivalent current health-state evidence can still produce an actionable device warning. The correction only removes unsupported failure conclusions inferred from timestamp age alone.

### Freshness warnings require a contract

An overdue/freshness warning is now reserved for evidence that carries an explicit freshness expectation or reporting contract. This separates a measured age from a proven expectation that a new report should already have arrived.

### Timestamp clusters are observations, not incidents

Groups of devices with similar old activity timestamps remain useful diagnostic observations, but the health-audit path no longer turns those clusters into an inferred integration interruption or stopped-reporting incident without corroborating failure evidence.

### Synthesis contract reinforced

The final synthesis policy now states the same boundary as the deterministic producer: old timestamps can describe activity age, but they cannot be upgraded into offline/stopped-reporting claims unless current-turn evidence independently supports that conclusion.

### Regression coverage

The release gate covers:

- quiet capability devices remaining neutral when only activity age is old;
- timestamp clusters remaining non-causal observations;
- explicit freshness contracts still being able to produce overdue warnings;
- direct offline/unreachable evidence remaining actionable; and
- health-audit schema migration advancing with the new freshness semantics.

The normal HomeBrain retrieval and MCP execution architecture is otherwise unchanged from 0.16.87.
