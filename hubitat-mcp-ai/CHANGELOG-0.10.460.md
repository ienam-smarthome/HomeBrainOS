# Hubitat MCP AI 0.10.460

## Evidence sufficiency and request-local target reuse

Live 0.10.459 validation showed that history correctness was now conservative, but
simple temporal questions could still spend several extra model/tool rounds on
unrelated context after the deterministic history result already contained the
material answer. The same live run also resolved Bedroom 3 Light once through
`homebrain_resolve_device` and then performed another targeted device lookup when
`homebrain_device_history` resolved the same label again.

0.10.460 tightens both paths without adding device-specific question routing.

### Request-local resolved-device cache

Successful deterministic device resolution is now cached only for the active
observed request, keyed by the opaque request identity. The target is indexed by
the user's successful wording and by the resolved id/name/label.

A later local adapter in the same request can therefore reuse that exact target
without another `hub_list_devices labelFilter=...` call. The cache:

- stores only successful resolved targets;
- does not cross request boundaries;
- still checks a requested command when command capability is required;
- returns explicit `requestCacheHit` metadata;
- increments the privacy-safe `resolution_cache_hit` request metric.

### Evidence-sufficiency stop

After a native tool round has executed every call the model requested, a successful
non-causal `homebrain_device_history` result with deterministic
`temporalAnalysis` is considered sufficient to move to final synthesis. HomeBrain
does not open another tool-selection round merely to gather unrelated location,
motion, rule, or diagnostic context.

Causal `why` requests remain eligible for further evidence gathering. The stop
also happens only after the complete native round executes, so independent tools
the model requested alongside history are not dropped.

The history synthesis hint now follows the 0.10.458+ source-integrity contract:
`unverified-event-stream` durations are estimates, not exact totals, continuity
proof, or mathematical lower bounds.

### Observability

Two new counters are exposed in request metrics and the technical-details panel:

- `resolution_cache_hit`
- `evidence_sufficiency_stop`

## Regression coverage

Tests verify request-local resolution reuse across separate service instances,
history reuse without a second targeted lookup, synthesis with tools disabled after
sufficient non-causal temporal evidence, and continued tool availability for causal
history requests.
