# HomeBrainOS 0.18.97 — Keep AI interpretation ahead of keyword reports

## What changed

- Clearly scoped whole-hub and aggregate-performance requests keep their established fast read-only presenters. However, a negated report example (such as "this is NOT a comprehensive audit of my entire Hubitat system") is no longer interpreted as permission to launch a broad report. Such ambiguous or negative requests are instead sent to the bounded no-tools AI objective interpreter. The exact standalone `Run system check` remains immediate.
- Natural connectivity questions such as "Why is Bedroom 3 Mesh offline when MQTT reports connected?" are eligible for that single interpretation even without the older pair of "investigate + logs/source" trigger words. Eligibility only starts the AI choice; it never selects a domain or authorises a command.
- Specialist routes now require a consistent structured objective (`system_audit` with `system_audit`, `performance_report` with `performance_report`). An absent, unknown, or contradictory model objective falls back to interactive MCP investigation, not a broad report.
- Missing or malformed model objectives receive a conservative `general_investigation` fallback, preventing later keyword-driven rule-authoring or historical-command classifiers from silently changing the task. Task identity is retained in request-local context, with independent host-side write detection and read/tool evidence validation unchanged.
- Regression tests cover a negative mention of an entire-system audit inside a named-device investigation, a short MQTT/offline question, mismatched/malformed AI objectives, genuinely whole-hub and aggregate performance fast requests, and the explicit System Check command.

## Safety and remaining limits

No live Hubitat settings, drivers, apps, rules, devices, or paid model preferences were modified. This is a routing and objective-consistency improvement; source selection, tool availability, per-request time limits, and the model's own reasoning can still limit forensic completeness. Validate on the installed add-on using a read-only named-device question, then check evidence coverage and response quality before claiming better diagnostics.
