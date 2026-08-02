# Hubitat MCP AI 0.10.304

## Fixed

- Grounding refusals now finish with request outcome `refused` instead of `success`.
- Outcome classification uses the existing fixed `grounding_refusals` counter and never inspects prompt or response text.
- Ordinary returned answers remain `success`; exceptions and cancellations retain their existing outcomes.

## Tests

- Added production-agent coverage for refused and successful completion paths.
- Added direct `RequestMetrics.completed_outcome` coverage outside an active request context.
