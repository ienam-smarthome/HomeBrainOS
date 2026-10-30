# v0.18.239 — restore verified multi-device V2 explanations after named lookups

## Real live regression and verified cause

On 30 October 2026, the user asked Investigation V2 to reconstruct Bathroom Light 1 (7818), Bathroom Light 2 (7821) and Shower Light (7807). The model resolved all three names and successfully read 41, 41 and 37 target events, plus current app metadata. It nevertheless returned two unrelated command-count facts. Diagnostics showed `event_narrative_eligible=false`, `final_synthesis_skipped_reason=multi_source_factual_brief_ready`, `final_synthesis=host_evidence_fallback` and `concise_answer_source=host_verified_claim_catalog`.

The regression was a contradictory eligibility condition: v0.18.238 required `not focus_ids`, although independently resolving each named device populates `focus_ids`. Its original tests used room discovery, which left `focus_ids=[]`. This was an **integration coverage defect**, not missing event data or a failure of the MCP transport.

## Corrective architecture

- Eligibility now depends on **two separately attested device-event READs** and at least three usable, exact source events, not whether device focus IDs happen to be populated. The event packet accepts only independently resolved IDs or returned room membership.
- The host retains stricter priority for explicitly requested complete-cycle gaps, missing incident-time evidence and unattributed generic warnings. Single-device focused investigations remain on their specialised path.
- When the event evidence is sufficient, an additional no-tools model reasoning stage receives a bounded packet of exact source timestamps, values, actor IDs and READ receipts. It must return citeable structured JSON and cannot assert an unverified sensor cause.
- If the final model does not produce validated event-linked prose, publish the chronological source-backed event fallback—not a claim-count catalog—and report its actual publication authority in diagnostics.
- `event_narrative_blockers` now explains which evidence/safety condition prevented the new stage. `source_grounded_brief_published` and `claim_publication.used_for_display_answer` distinguish a displayed timeline from the unused legacy claim-catalog audit.

## Required testing

- Reproduce the live **three independent named identity lookups**, then three target event reads and a round-budget exit. Both an accepted source-linked model explanation and a rejected/unstructured model response must avoid the old command-count publication.
- Repeat with model finishing before the budget boundary; the tools-free final reasoning stage must still execute.
- Confirm one-device history does not enter the group-specific path.
- Preserve source-ID/actor/number and command-vs-state validation, no writes, and all unrelated V2 safety/regression tests.
- Run release-assurance, full pytest, add-on container smoke, import, metadata and golden-history suite before merge. CI passing cannot prove real motion-sensor trigger attribution: the live input/decision histories were not read in the reported test.
