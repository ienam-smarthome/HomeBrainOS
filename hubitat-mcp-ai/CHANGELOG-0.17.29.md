# HomeBrain 0.17.29 — Approximate event-time anchoring for causal investigations

## Live regression

HomeBrain 0.17.28 correctly routed the Bedroom 1 Light question through the unified agent, but did not invoke journal-first historical sensor correlation. The user asked about **approximately 17:14:05** on 12 October 2026. Hubitat's actual OFF transition was **17:14:04.380 BST**, a 620 ms difference.

Previously, the focal boundary selector required the *integer second* to match exactly for all HH:MM:SS queries, even when the user explicitly said “approximately.” It therefore returned no focal interval, and the prefetch handoff exited before local journal and bounded MCP sensor reads. The model subsequently claimed exact OFF producer evidence was unavailable despite its presence in the returned `correlationEvents` and repeated a listener caveat.

## Changes

- Only when a request explicitly uses **approximately**, **around**, **about**, **roughly**, or **approx.** immediately before a specific clock time, permit a narrowly bounded ±2-second focal match.
- Preserve strict second-level selection for requests without approximate wording.
- Require a single matching observed interval. Multiple candidates near the requested time, a mismatching named date or a missing event remain unresolved; never silently substitute a newer OFF.
- Reuse the existing deterministic focal-event→producer→secondary-correlation handoff so the journal-first reader introduced in 0.17.27 is actually reached when the time is approximate.
- Add regression tests for the original 08:18:23 OFF, the real 17:14:04.380 observation queried as 17:14:05, strict timestamps, wrong-date/ambiguous matching, and end-to-end secondary handoff.
- Keep the journal event stream, seven-day retention, 200,000-row capacity and all Hubitat devices/apps unchanged.

**Live test**: Upgrade to 0.17.29 and repeat the *same* question about approximately 17:14:05 on 12 October. Confirm `route=unified-mcp-agent`, an exact `stateBoundary=17:14:04.380+0100`, and `historicalJournal` / `focalWindowRetrieval` / `journalFirstPlan` evidence in the technical trace. Do not claim an initiating automation or a motion timer without matching time-scoped proof.