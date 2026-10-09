# HomeBrainOS 0.16.131 — Better optimisation answers and tables

## Fixed
- The Home Assistant web UI now recognises Markdown tables in HomeBrain's answer text and renders accessible native HTML tables, safely constructing all cells as text (not provider HTML). Tables scroll horizontally on mobile.
- Numbered recommendations use HTML ordered lists rather than literal lines. Markdown horizontal rules also render.
- Final optimization-answer validation fixes a "Device Reporting" recommendation that contains only observed interval numbers. Where exactly one matching host-derived source/signal is available, it identifies that device and provides an inspection-first action. Without a unique source match, it explicitly says the target remains unverified.
- Failed app configuration lookups for deleted apps (e.g. 2597 and 2954) do not by themselves prove MCP Rule Server keeps permanent references to those apps; the investigation instructions now distinguish caller errors from actual persisted dependencies.
- Regression tests cover web renderer safety, raw Markdown table presentation, named and ambiguous cadence attribution, and cautious configuration-error interpretation.

## Safety and limitations
- Read-only. No Hubitat automations or settings are modified.
- The broad optimiser still needs deeper per-app scheduler and event-volume analysis under issue #733. Results from 100 capped log rows cannot establish a complete reporting history.
