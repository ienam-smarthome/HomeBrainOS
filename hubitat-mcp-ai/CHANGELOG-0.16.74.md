# Hubitat MCP AI 0.16.74

## Summary

0.16.74 is a narrow deterministic-language hardening release based on the 0.16.73 live performance proof. The four-tool / normally three-model-round performance architecture, source-budgeted evidence packet, bounded recent-log read, and single final provider synthesis pass are unchanged.

## Changes

- Generic scheduler-offset recommendations now require configuration evidence. Phrases that shift, move, spread, stagger, or offset `sessionTick`, `autoPoll`, or other scheduled jobs are converted to an inspection-first recommendation when the relevant app/rule configuration was not read.
- Claimed benefits from offsets, including flattening or reducing CPU load, spikes, overhead, contention, or lag, are fail-closed unless the current turn establishes them.
- App busy percentage remains a measured statistic but no longer justifies unsupported implementation claims such as `Optimize Logic`, inefficient loops, or overly frequent triggers without implementation/configuration evidence.
- Qualitative summary wording from the 0.16.73 live proof is neutralized: `significant inefficiencies`, `severe clustering`, `massive block`, and `disproportionate processing time` are replaced with measured observations.
- `most resource-intensive app` is normalized to the evidence-backed ranking `highest returned app busy percentage` when applicable.
- The complete 0.16.73 live answer is covered by regression tests, including preservation of the recommendation table and measured resource/performance values.

## Performance contract

Expected broad performance behavior remains:

- normally 4 tool calls (`hub_get_metrics`, `hub_get_performance_stats`, `hub_get_jobs`, plus one bounded `hub_get_logs` when needed),
- normally 3 total model rounds when the original agent uses two rounds,
- current metrics preserved in the final synthesis,
- no duplicate API snapshot reads,
- deterministic repairs remain Markdown/table safe.
