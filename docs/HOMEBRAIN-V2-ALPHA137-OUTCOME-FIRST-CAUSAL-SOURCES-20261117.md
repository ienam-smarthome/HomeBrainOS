# HomeBrainOS V2 alpha.137 — outcome-first causal source opportunities

**Status:** code PR candidate; exact-head CI and installed live acceptance pending.

## Private benchmark motivation

An uncoached installed alpha.136 first answer recovered the correct reported output transition but returned zero command rows, queried no historical controller application logs or participating input histories, and could not identify the source of demand. The original three native reads succeeded; independent qualitative review scored the incomplete response **4/8**. Separately supplied controller logs resolved the owner’s event-specific question, but were **NOT** original first-answer MCP receipts and are not counted as HomeBrainOS evidence. No private device identifiers, raw logs or household configuration are committed.

## General V2-only change

- Extend the existing causal_read_opportunity.py module, reusing the original_device_event_history identity validator. It accepts bounded, timestamped categorical state observations (across devices) when selected event-history filters return no command issuer. Arbitrary/numeric readings, failed histories, mismatched source identities and invalid timestamps do not become leads.
- Keep reported output state, recorded native command issuer, notified triggered[] listener, controller execution decision and physical outcome distinct. For state-only evidence, expose listener IDs only as *notified listeners*, never command issuers; do not choose an app or presume a room.
- Expose genuinely offered read-only log/event/config tools and exact safe schema field contracts in the existing causal review and optional follow-through rounds, **including no-command state-only cases**. An offered schema does not prove historical log availability. The model chooses or declines any proportionate read.
- Do not add a forced native read, a new model round, a host source planner, new approval, changed write eligibility, V1 change, scheduler change or new provider. Keep all original receipts unmodified.
- Fictional state-only HVAC, light/ventilation issuer, invalid/mismatched source, untrusted input, gateway and chosen/declined model read regressions protect the separation and write boundaries.

## Acceptance

Run focused Python tests, full V2 suite, release-validation and UI/screenshot checks on the **exact final PR head**. Then gather new private, uncoached first-answer Technical JSON samples across domains and independently score source completeness and causal accuracy under the permanent 53-case benchmark. Check the actual controller execution/input read, output identity, time chronology, receipt limits, issuer versus listener, unresolved physical effect, rounds and token costs. An attractive partial answer, passing fabricated tests or a tool advertisement does not establish improved live model reasoning. Roll back to alpha.136 without migration if source-real acceptance fails.
