# HomeBrain 0.17.32 — Preserve archived sensor observations when MCP history is empty

## Live regression: Bedroom 1 Light, 12 October 2026, 17:14:04.380 BST

Version 0.17.31 completed the targeted investigation in 11.4 s (one model round, 17 tools), with both absolute MCP sensor windows verified. But MCP returned **zero** event rows for the FP300 and Soft Sensor. The separate Historical Journal had retained **four** partial motion observations:

- Bedroom 1 FP300: inactive collector reception 17:14:05.385, active 17:15:20.971
- Bedroom 1 Soft Sensor: inactive collector reception 17:14:06.442, active 17:15:20.917

The final reply discussed only empty MCP sensor history and failed to disclose the surviving archive evidence. Verified absolute MCP request bounds do not prove complete underlying retention; the archive was designed to preserve earlier records when the native history rolls off.

## Fix

- Preserve matching focal-window journal observations as **separate, weaker source evidence** within the deterministic OFF evidence graph, alongside the verified-but-empty MCP window metadata.
- Include each sensor device ID/label, observed state, timestamp basis and *collector reception difference* relative to the selected OFF boundary, with explicit uncertainty that collector ordering need not equal actual source-event ordering.
- A narrowly targeted final-answer guard repairs a misleading global “sensor history showed no events” claim when journal observations exist, without rewriting accurate source-by-source explanations.
- Regression tests reproduce two verified empty MCP windows and four archived observations, check 1005 ms / 2062 ms collector reception deltas, verify unresolved command/timer status, and reject cross-event archive mixing.
- Add sensor labels to the journal's bounded summary for clearer source attribution.

**No changes** to Hubitat devices, automations, MCP server behaviour, continuous collection rate or your seven-day / 200,000-row Historical Journal configuration.

## Live validation

Upgrade to 0.17.32 and repeat the identical read-only 17:14:05 Bedroom 1 Light OFF question. The expected response distinguishes **0 MCP-returned sensor rows** from **4 journal-archived observations**. It must not say the 17:14:05.385 archived inactivity reception caused the OFF at 17:14:04.380; the original source-event time is unknown. The initiating OFF actor may remain unresolved.
