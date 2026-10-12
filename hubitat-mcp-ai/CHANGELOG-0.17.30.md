# HomeBrain 0.17.30 — Focal causal evidence reconciliation

## Background

The 0.17.29 live test for Bedroom 1 Light OFF on 12 October 2026 at 17:14:04.380 BST confirmed journal-first investigation, two verified absolute MCP sensor windows and a one-round 11.4-second response. The final answer still contained inconsistent coverage fields, over-attributed a near-synchronous physical-button event, left app-log archive evidence disconnected from native-log evidence, and rendered literal LaTeX math status markers.

## Changes

- Reconcile each sensor-history coverage assessment with **actual absolute-window verification results**. When the MCP server confirms `since` and `until`, publish `upstreamHistoricalWindowAvailable=true`, verified device IDs and counts; still retain `historicalCompletenessVerified=false` and `unobservedIsNotInactive=true`.
- For an explicit historical OFF, compare a bounded native `hub_get_logs` response with local archived logs for **only the already-allowlisted app ID** and the same focal time window. This local SQLite query never sends additional requests to Hubitat. Report separate source counts, timestamp bases, collection gaps and limitations without exposing private log-message content.
- Attach `archivedAppLogReconciliation` to the focused OFF evidence graph when the log-window and app identity match. Zero rows never prove an app did not execute, and archived logs do not independently prove an OFF command issuer or internal timer.
- A final-answer guard downgrades an unsupported claim that a button press **initiated** ON to a close association, preserving the named controller. Confirmed direct command evidence remains untouched. This is especially important when Hubitat recorded the button event *after* the ON state.
- Translate literal `$\\times$`, `$\\checkmark$`, `$\\sim$` table status syntax into plain-text glyphs suitable for HomeBrain's Markdown renderer.
- Regression tests check contradictory coverage, positive/negative archived app-log counts, privacy and source strength, button causality, historical graph integration and status rendering.

## Safety and limitations

Read-only. No changes to Hubitat devices, rules, automation settings or local journal capture policy. The 7-day / 200,000-row retention configuration is untouched. Verified absolute MCP windows are **not** proof of full underlying event continuity. Reconciliation is implemented for this focal OFF evidence path, not a global replacement for all historical readers.

## Live verification

After upgrade, repeat the same 17:14:05 approximate Bedroom 1 OFF question. Inspect the technical trace for `localSensorHistoryCoverage.upstreamHistoricalWindowAvailable=true` when the two MCP windows are verified, `archivedAppLogReconciliation` for app 4015 (when allowlisted), and correct differentiation of ON button timing versus OFF actor. Compare model rounds/tool calls and check that rendered table statuses no longer show raw `$\\times$`.
