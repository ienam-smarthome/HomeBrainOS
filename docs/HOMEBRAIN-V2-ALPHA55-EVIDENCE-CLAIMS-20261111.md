# HomeBrainOS V2 alpha.55 — source-to-claim verification refinement

**Date:** 11 November 2026  
**Starting version:** 2.0.0-alpha.54  
**Candidate:** 2.0.0-alpha.55 (V2 only)  
**Scope:** source presentation and model-led read-only evidence sufficiency; no Hubitat writes.

## Evidence motivating the change

Five private first-answer reviews of alpha.54 yielded **26/34** rubric
points compared with **25/34** for the selected alpha.53 reference captures.
This +1 difference is descriptive, not a reliable model accuracy estimate.
The largest open issue is a semantic mismatch between **what the source
actually reports** and **what the model calls verified**:

- A rendered interface control is not a directly reported state flag.
  The presence of a Pause button and `disabled=false` cannot by themselves
  prove the separate paused property.
- The identity/type reported for an app is directly available, but a parent
  app ID is a stored reference rather than independently verified parent
  identity.
- A query returning its maximum number of event rows has a material scope
  limit; older or alternative events remain unobserved.
- Saved measurement bins can support a bin-timestamp difference, while
  proving the requested physical duration requires fresh-report evidence.
- A recorded command issuer should be retained even if the originating
  controller decision and potential competing actors remain unknown.

The earlier calendar-dated native trigger requirement remains independently
unverified; a time-of-day control is not equivalent.

## Alpha.55 implementation

1. **Typed current-app field inventory:** The generic config-source map reports
   only boolean flags actually present in the returned app record, plus the
   returned app type identity. Flags absent from this record stay unknown.
   UI controls and their labels are explicitly *not* treated as typed status
   observations. The original MCP response is preserved intact.
2. **Front-loaded, source-derived evidence headline:** Before lengthy original
   native receipts, the model sees a compact index of app typed fields or
   bounded returned event rows, including row limit reached, filtered scope,
   oldest/latest returned timestamps, and recorded command-row count. This
   is a presentation aid, not an independent corroborating source.
3. **Autonomous verification checkpoint:** A broad technical inspect/verify
   intent can receive one extra model-led, read-only sufficiency review.
   Read source selection remains with the model, not deterministic routing.
   Ordinary short current-status queries continue without this checkpoint.
   Queries with a generic "was caused by" shape qualify for causal review.
4. **Strict interpretation of proof conditions:** Existing historical review
   guidance now explicitly distinguishes a saved-bin timestamp proxy from
   a user-requested verified physical duration when freshness is unknown.
5. **Fictional regressions:** Positive and negative controls cover direct
   typed flags, missing typed flags alongside tempting UI controls, capped
   event history and preserved issuers, optional model-selected typed followup,
   no mandatory followup, and no writes.

No new fixed tool-order, hard-coded device names, restrictions on normal model
reasoning, automatic answer rewrite, or incident-specific MCP heuristics have
been introduced. Confirmation and source access checks are unchanged.

## Verification and next acceptance

- Complete the existing V2 Python, JavaScript, browser, metadata and container
  smoke workflows; record actual CI results before release claims.
- Verify UI/API/add-on all show alpha.55 before collecting installed evidence.
- Repeat the five existing alpha.54 questions as **fresh first answers**.
- Add independent fictional and live read-only holdouts: explicit typed status
  versus UI-only control, a missing field despite unrelated flags, a capped
  history, a directly recorded issuer with no internal callback, and a
  conditionally requested duration with unverified sensor freshness.
- Keep user-supplied Technical JSON private. Publish only anonymised aggregate
  scores and source-agnostic development conclusions.
- Assess factual grounding, source completeness, causal calibration and
  usefulness per original successful MCP receipts, not the model's tone.

**Non-claims:** CI cannot verify how the installed cloud model will reason.
This change does not independently validate a connected native rule parent,
prove a calendar-dated trigger, or cause any appliance/automation action.

## Separate baseline CI maintenance

Full-repository release assurance exposed an unrelated, wall-clock-dependent
October replay test in the pre-existing V1 suite after its historical lookback
crossed the source's maximum. The test fixture clock was frozen via **PR #1604**,
merged independently from alpha.55. No V1 runtime behaviour changed. The
alpha.55 candidate requires fresh CI against that corrected baseline before
merge or live installation.
