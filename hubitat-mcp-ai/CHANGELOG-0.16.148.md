# HomeBrainOS v0.16.148 — scheduler-probe recommendation-table guard

The v0.16.147 live run proved the historical-probe guard did not execute against the model's actual output shape. The unsupported MCP Rule Server cleanup claim was emitted as a Markdown recommendation-table row rather than under a per-target heading, so the section-state guard missed it.

v0.16.148 extends the deterministic guard to self-contained MCP Rule Server recommendation rows. When scheduler secondary-source metadata records that targeted probes may emit expected not-found rows, a missing-device cleanup row is rewritten to preserve only the unresolved lookup observation and require independent request provenance/configuration evidence before cleanup.

Regression coverage uses the exact v0.16.147 live table shape.

No Hubitat state, device, app, rule, schedule, or configuration is changed.
