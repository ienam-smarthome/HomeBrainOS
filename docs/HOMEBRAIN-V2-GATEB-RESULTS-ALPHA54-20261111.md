# HomeBrainOS V2 — Gate B results and alpha.54 candidate

**Reviewed:** 11 November 2026. **Source:** Twelve paired, private first-answer captures with original returned MCP/monitor receipts; no independent live-hub verification. **Candidate:** `2.0.0-alpha.54` on a V2-only branch.

## Decision after the fixed first-answer benchmark

The V1 baseline was `0.18.459`; the V2 baseline was `2.0.0-alpha.53`.
These were single-run comparisons with model-routing equivalence and installed
build SHA not independently attested. The rubric gave V1 **27/80** and V2
**53/80** available points, with V2 ahead on 9 cases, V1 ahead on 2, and 1 tie.
**These values are descriptive scores, not statistical accuracy estimates.**
The calendar-date-specific trigger requirement was not satisfied by the tested
clock-time Rule Machine example; do not claim that capability was certified.

Strong V2 results: independently finding saved histories; aligning multiple
devices on a fixed historical interval; preserving explicit-null versus valid
zero and held bins; finding actual command-issuer records; and inspecting native
app configuration and timestamped app logs.

Open general weaknesses: (1) an observed command issuer being promoted into a
verified internal controller decision, (2) full saved-value bin coverage being
promoted into verified sensor freshness/physical threshold crossing, (3) record
truncation and narrower-than-requested time intervals, (4) device lastActivity
being used as individual attribute history time, and (5) rendered rule links
being mistaken for compiled trigger registration or a calendar-date trigger.

No private device traces, access tokens, raw model responses or household
identifiers are included in this public development note.

## Scope of alpha.54 candidate

- Add a source-derived `client_monitor_evidence_scope` at the start of the
  model-visible, unchanged monitor response. For saved histories, it carries
  the exact requested and returned boundaries, metric, device ID, bin counts,
  fresh-sensor limitations, explicit-null versus absent positions, and
  observed extrema semantics. For comparisons, it keeps device coverage
  separate under a shared window. Monitor status is labelled a latest/cached
  snapshot, not past measurement.
- Annotate current native app configuration with a stored parent pointer
  separately from independently verified parent identity. No new app calls
  or rule exports are performed.
- Refine the **model-led** evidence-sufficiency prompts so observed commands,
  app execution logs, saved-bin proxies and remaining unknowns are reported
  at the level the source actually supports. Explicitly distinguish ordinary
  clock-time triggers from calendar-dated triggers.
- Preserve the original native MCP and monitor payloads, original tool
  selection, safe read-only checks and confirmation controls. No device-specific
  route, mandatory extra read, automatic answer rewrite or new tool cap.
- Add fully fictional unit/integration regressions to check the new metadata,
  positive findings and negative controls. The CI result tests delivery and
  software behaviour only; it cannot establish that the deployed cloud model
  will follow the context.

## Validation and remaining roadmap

1. Run the existing V2 Python, JavaScript, syntax and container smoke workflows.
   Do not assert success until actual CI receipts are available.
2. Install candidate only through the user's normal experimental add-on update.
   Verify API/UI versions match, then repeat original, unchanged first-answer
   questions without in-session coaching. Preserve **first answer** and
   original private receipts.
3. Run unseen, read-only holdouts with a real date-specific native rule (only
   if one already exists), a state report with no matched command, one with a
   matched issuer but ambiguous callback, freshness-unverified sensor history,
   missing/held power bins and a truncated historical source.
4. Judge per-claim grounding and coverage, not just a yes/no final answer.
   Refine further only after receipt-based evidence; no incident-specific
   patches or synthetic scenario rules added to live Hubitat.

**Safety:** No hub/device/Rule Machine changes are authorised by this work.
