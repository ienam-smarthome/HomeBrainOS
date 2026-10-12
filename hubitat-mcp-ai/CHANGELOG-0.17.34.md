# HomeBrain 0.17.34 — Historical source disclosure and grammatical claim correction

## Live regression — Bedroom 1 Light OFF, 12 October 2026

HomeBrain 0.17.33 completed the investigation in 12.1 seconds with **one model round and 17 tool calls**. It correctly retrieved **4 Historical Journal motion observations** and **2 verified absolute MCP sensor windows returning 0 events**. The answer disclosed the Journal and collector timestamps, but omitted the actual source counts. A string-level command-history guard also corrupted the app paragraph, leaving text similar to `command.by this app`, and the UI showed raw `$\\approx$` syntax.

## Correction

- Require *all* source-coverage elements when archived rows exist: the Historical Journal, its numeric retained observation count, verified MCP window count, MCP returned event count, and an explicit timestamp-basis caveat. Generic references to “Historical Journal” plus “collector-received” no longer count as complete evidence reconciliation.
- Preserve existing source-aware answers rather than duplicating them. An incomplete source-aware answer receives only a concise, evidence-backed **Historical source coverage** paragraph, without inventing new events or an OFF actor.
- Narrow the command-provenance claim guard to actually global Hubitat assertions. A scoped phrase such as “no command issued by this app was found in bounded history” is no longer partially rewritten into a standalone sentence with dangling text. Explicit global negatives are replaced by a grammatically compatible, source-bounded clause.
- Render `$\\approx$`, `$\\rightarrow$` and `$\\to$` to readable symbols, along with existing status-notation repairs.
- Regression tests reproduce the exact missing source-comparison pattern and the malformed command paragraph, plus correctly complete answers and one-pass formatting corrections.

## Safety

All changes are limited to deterministic final-answer validation and provenance wording. **No new Hubitat reads, device/rule actions, automation edits, journal polling or retention changes.** Existing Historical Journal settings (7 days / 200,000 rows) remain unchanged.

## Live verification

Upgrade to 0.17.34. Repeat the exact Bedroom 1 Light OFF question at approximately 17:14:05 BST, 12 October 2026. A passing answer must identify **4 partial journal observations** versus **2 verified MCP windows returning zero events**, with collector-reception caveats and no false OFF causality. Check for grammatically sound app-command claims, readable approximate symbols and the one-round performance target.
