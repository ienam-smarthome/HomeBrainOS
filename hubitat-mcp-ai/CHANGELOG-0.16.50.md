# Hubitat MCP AI 0.16.50

## Performance-causality response boundary

The 0.16.49 live performance retest exposed a production finalization bypass. Ordinary non-investigative `live-read` completions can return provider prose directly from the unified MCP orchestrator instead of entering `FinalAnswerCoordinator`, so the new performance synthesis validator did not run even though the turn had both performance statistics and recent logs.

0.16.50 adds the same fail-closed performance/log causality guard to the `/api/ask` serialization boundary. This is the final shared boundary used by unified-agent responses, so an unsupported model draft cannot escape merely because a particular orchestration path skipped final synthesis.

The guard continues to preserve measured performance statistics while treating recent logs as observations unless current-turn evidence directly links them to the measured cost. In particular it:

- demotes log-only `Root Causes` headings to recent observations;
- rejects a recent-log pattern being described as the cause of measured busy percentage, load, latency, response time, or execution time without direct linking evidence;
- recognizes live wording such as `fluctuating slightly (e.g. 77W → 82W → 81W)` when the actual rule-log sample proves all observed trigger values stayed on the same qualifying side of the threshold, and replaces the unsupported threshold-oscillation interpretation;
- blocks exact trigger/threshold/debounce/`stays that way for` prescriptions when the current turn did not read the rule/app configuration.

A regression test reproduces the exact 0.16.49 live failure at the API response builder. It deliberately supplies a direct provider draft containing `Root Causes`, `fluctuating slightly`, `likely driving the high busy percentage`, and an ungrounded one-minute rule edit. The serialized response must remove or qualify every unsupported claim before it reaches the Web UI/API client.
