# Hubitat MCP AI 0.16.48

## Performance diagnostics: evidence before explanation

A live 0.16.47 performance query exposed two correctness problems:

1. HomeBrain correctly retrieved hub metrics and app/device performance statistics, but then used unrelated entries from a short recent-log sample to explain multi-hour performance totals. In particular, a repeatedly-triggered TV power rule was promoted into the likely cause of the LG webOS driver's ~3-second average execution time even though the evidence did not establish that link.
2. Broad automation-improvement wording could be intercepted by the deterministic automation-status route and return a broken/disabled inventory instead of letting the reasoning agent answer the optimisation question.

### What changed

- adds an explicit Hub Performance / Optimisation evidence contract to the reasoning prompt;
- performance statistics returned by Hubitat are treated as measured findings;
- recent logs are treated as observations, not automatic explanations;
- a 30-minute log window cannot be used as causal proof for statistics accumulated across many hours of uptime;
- suspected causes must be labelled as hypotheses unless current-turn evidence directly links the measured component and expensive operation;
- high average execution time is investigated at the same app/driver first (network calls, retries, timeouts);
- high call counts are investigated through that component's schedules, subscriptions, polling, and event cadence;
- scheduled-job counts must be read from a relevant diagnostic tool before HomeBrain quotes a count or recommends scheduler consolidation;
- unrelated log chatter is separated into secondary observations instead of being presented as root cause;
- broad `improve`/`review` automation requests no longer automatically select the deterministic automation-status shortcut;
- explicit automation status/listing requests remain deterministic, while explicit new-automation idea requests retain the creative advisory path.

### Regression coverage

Adds tests for:

- advisory automation prompts routing to the reasoning agent;
- explicit status prompts staying on the deterministic route;
- explicit new-automation ideas retaining the creative route;
- the performance prompt's measured / observed / hypothesis boundary and component-local investigation rules.
