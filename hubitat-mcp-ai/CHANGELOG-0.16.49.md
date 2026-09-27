# Hubitat MCP AI 0.16.49

## Performance diagnosis: enforce the evidence boundary after synthesis

The first 0.16.48 live retest proved that prompt instructions alone were not a
sufficient correctness boundary. HomeBrain again measured LG webOS TV at about
16.6% busy / 3 seconds per call, then promoted repeated TV-power Rule Machine log
entries into the likely cause of that driver statistic. It also described repeated
68-79 W qualifying reports as fluctuation around a 65 W trigger threshold and
prescribed an exact debounce-style rule edit without reading the rule configuration.

### Root cause in HomeBrain

`FinalAnswerCoordinator` only ran `validate_synthesis()` for history/investigative
requests. The performance request was an ordinary `live-read`, so the model-authored
draft bypassed every deterministic synthesis validator and was returned unchanged.
The 0.16.48 performance contract therefore guided the model but did not enforce the
boundary when the model ignored it.

### What changed

- adds a host-owned `performance_causality_guard`;
- detects turns that combine `hub_get_performance_stats` with `hub_get_logs`;
- routes those non-investigative answers through the same validate -> one no-tools
  repair -> validate-again pipeline used by evidence-heavy investigations;
- scopes final performance synthesis to the current real user turn so a previous
  assistant conclusion cannot become evidence on a follow-up;
- includes a bounded current-turn tool-evidence packet in performance synthesis;
- relabels log-only `Root Causes` sections as recent observations when causation is
  not established;
- removes unsupported claims that recent log activity is driving measured busy %,
  load, latency, execution time, or resource use;
- recognizes the live regression's one-sided trigger sample: repeated qualifying
  reports do not prove oscillation/crossing of the trigger threshold;
- refuses to prescribe an exact trigger/threshold/debounce/duration edit when the
  turn did not actually read rule/app configuration;
- preserves safe answers that report measured performance and recent log activity
  separately with an explicit evidence boundary.

### Regression coverage

Tests reproduce the 0.16.48 TV answer verbatim enough to exercise all three failure
modes. A provider that ignores both the original prompt and the repair instruction
is deliberately simulated; the final host validation must still prevent the bogus
causal answer from escaping.
