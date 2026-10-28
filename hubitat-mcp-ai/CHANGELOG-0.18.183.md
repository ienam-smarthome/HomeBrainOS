# HomeBrainOS v0.18.183 — Native MCP read protocol and evidence-first completion

## Live failures addressed

Two native V2 runs showed (1) an upstream `hub_get_logs` request with
`level=WARN,ERROR` failed because that operation accepts only one level, and
(2) a device investigation repeated `hub_list_devices` three times, each
timing out after 20 seconds. The latter run already had source-backed evidence:
Bedroom 3 Mesh driver `healthStatus=offline`, `lastSeen=12 Oct 2026`,
`mqttStatus=connected`, and an approximately 45,945-second stale-data
watchdog warning. However, the final model pass failed after 15 seconds and
HomeBrain did not explain any of those observations.

## Structural improvements

- A shared read-operation contract validates the concrete MCP operation args
  *before* invoking the gateway. For logs, a level must be a single value from
  trace/debug/info/warn/error/all. The model receives precise, fixed guidance
  to request warn and error separately rather than retry malformed requests.
- Read-only metrics cannot persist a snapshot with `recordSnapshot=true`.
  This is a safety boundary separate from inferred MCP readOnlyHint metadata.
- A per-investigation circuit breaker prevents another request to the same
  gateway operation after a timeout, even if the model changes its arguments.
  Rejected attempts do not spend the MCP read budget.
- After one fully rejected round the model gets a bounded opportunity to
  repair its arguments or choose another source. Repeated rejected calls stop.
- A source-first summary prioritizes typed device status, lastSeen, health
  attributes, representative events and WARN/ERROR observations. This much
  shorter evidence set is passed to final model synthesis.
- The final model synthesis deadline is reduced from 15 to 8 seconds. If the
  model is unavailable, times out or returns no answer, a deterministic,
  source-referenced factual fallback is returned instead of an empty
  investigation. The fallback never declares a physical root cause verified.
- Source highlights and timed-out operation identities are captured in
  diagnostics to support performance analysis and future benchmarks.
- Evidence coverage challenges are not repeated after a successful
  severity-filtered log read.

## Verification

New regressions cover invalid combined severity values, read-side-effect
flags, timeout circuit breaker across varied arguments, invalid-argument
recovery, provider failure with a WARN log retained, and device lastSeen/
healthStatus/watchdog summary preservation.

The work does not claim complete historical coverage or full Claude-level
autonomous reasoning. Production Main Ask, its write approval path, and
Hubitat devices and automations are unchanged. Live testing is still required
to validate the configured provider/tool gateway.
