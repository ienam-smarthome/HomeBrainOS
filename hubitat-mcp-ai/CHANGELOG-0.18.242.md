# v0.18.242 — original HomeBrain: complete multi-device timeline and retire standalone V2 test

## Live failure that triggered this fix

On 30 October 2026, HomeBrain v0.18.241 successfully read independently scoped Bathroom Light 1 (7818), Bathroom Light 2 (7821) and Shower Light (7807) event histories in the requested 02:00–07:30 GMT window. Its final prose and timeline nevertheless omitted Bathroom Lights 1/2 ON/OFF transitions at 03:04, 03:40, 03:46 and 07:12, claimed one ON was caused by the 07:15 brightness/mode adjustment, and attributed ON initiators to Hubitat automation without matching preceding commands. The source data was present; the final synthesis path skipped or discarded it. Claude's 02:18 OFF and 02:52 ON are *log-only events*, not present in those device-history receipts, and must not be invented.

## Repair in the original agent

- The original HomeBrain agent's **terminal request boundary** now checks independently read, name-resolved, multi-device event receipts, including answers returned early without going through the normal FinalAnswerCoordinator.
- The reusable V2 source-projection library remains in place, but its *sampled* event narrative packet no longer gates preservation of the complete returned ON/OFF facts. Every returned requested-device switch transition is sorted together by source timestamp and presented under a verified timeline, with a visible display cap if the source has more than 60 transitions.
- The host replaces a model-written, incomplete chronology rather than endorsing omissions. It reports immediate confirmed app-issued OFF commands separately from sensor correlations and brightness adjustments **after** reported ON, and it qualifies unsupported automation-initiation claims.
- A successful read of recent logs is explicitly **not** historical incident-time coverage. Device-state reporting, app-issued commands, physical actuation and external-controller provenance remain distinct.
- This is source-grounded output reconciliation, not a new keyword tool router, new model answer engine, new permissions or additional write capability.

## Retired V2 test surface

The dedicated `/v2-test` browser panel, `/api/v2/test` experiment, `/api/v2/auth/*` access endpoints, V2 test UI shortcut and its add-on enable/token options are removed. The separate browser test page and legacy authorization-cookie implementation are deleted. Retired HTTP-only V2 test suites are replaced by a positive check that these routes now return 404 and a normal original HomeBrain Ask route remains available. V2's evidence adapters, typed provenance, timeline sampling comparators and retained internal regression tests remain for source verification and analysis.

## Live-test acceptance

The full Bathroom question must show ON/OFF state reports for all three lights, with 03:40 and 07:12 both Bathroom ON pairs; 03:04 and 03:46 both Bathroom OFF pairs where available; 07:15 a brightness adjustment, **not** an ON. Events not returned by the device histories are noted as missing unless independently supported by incident-time logs. Natural-language cause assessment remains uncertainty-qualified. No mutations.

Run full pytest, metadata validation, Hubitat MCP AI tests and add-on container smoke. CI confirms implementation contracts, not an actual home-Hubitat deployment. Use HomeBrain Main Ask for live testing after update.
