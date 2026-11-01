# Q1 real-response review: event reporter confused with causal initiator

**Date:** 2026-11-01. **Add-on reported:** v0.18.330.  
**Assessment type:** source-bounded, **provisional qualitative review**, NOT a frozen-prompt baseline score, independent device execution verdict, or model comparison. This document contains no verbatim private log payload.

## What was available

The user provided a v0.18.330 read-only investigation with a complete technical trace for a hallway light, and a separate natural answer for a living-room light without its corresponding technical trace.

For the hallway example:
- A sensor inactive report and a second derived sensor inactive report preceded a light OFF state report by approximately **15.246** and **14.231 seconds**, respectively.
- The motion-sensor report identified the relevant lighting app among its **notified listeners**. The bridge was the **producer of the resulting switch-state report**, not independently identified as the action's upstream initiator.
- The response's own `investigation_coverage` reported **`rootCauseVerified=null`**, **`questionResolved=false`**, **`missingSourceKinds=["command_history"]`** and proposed external-initiator hypothesis unverified. There were no verified focal app-command decision records in the supplied evidence packet.
- The model nonetheless asserted **high confidence** that a physical interaction or external bridge command caused the OFF transition because the event was typed `physical` and produced by a bridge. **That inference is not established.** A bridge reporting the state change does not mean the originating automation could not be in Hubitat.
- The model retrieved relevant motion history and accurately reported the corresponding timing, but **did not integrate those facts into its causal preference**.
- Reported full request: **65.9 seconds** wall time (approximately 64.3 seconds agent phase), **17 tool calls**, **10 model rounds**, free Ollama Cloud Gemma. This exceeds the preferred 45-second complex-investigation target, but the sample is too small to establish a performance distribution.
- The answer contains a visible raw `\\n\\n` and crowded markdown heading. These are presentation-quality defects, not the underlying evidence error.

For the living-room example:
- The model also asserted high confidence in an external/physical trigger from the bridge's event-report classification.
- **No complete source trace was supplied for this answer**, so the timestamp, “most recent” scope, true command history and application-issuer alternatives cannot be independently reviewed. Do not count this as a fully source-graded first-attempt benchmark result.
- A benchmark run can only be considered exact if the registered question and actual response are both saved and verified; that is not established for both reported answers.

## Cross-domain failure class (candidate Q2 improvement)

**Reporter/handler/initiator separation failed.** Needed conceptual contract:

1. Event `producedBy=device/bridge` → who reported a state event to Hubitat, **not** who originated the decision.
2. Event `triggered=[app...]` → apps receiving the state report, **not** the issuing app of the original action.
3. `command-off producedBy=app` → recorded app **command issuer**, but not physical execution or the upstream decision.
4. `type=physical` is a source event classification, not a verified mechanical switch press or proof that all Hubitat apps were uninvolved.
5. Missing app/command history, even if queried, is bounded lack of evidence rather than confirmed absence.
6. Positive temporally related input history should be evaluated before asserting a competing explanation; time association alone also does not prove the internal timer.

This is a **cross-case semantic constraint**, not permission to introduce room-specific hardcoded wording. Before code changes, check an independent non-light example (e.g., MQTT device/broker or heating readback) and run controlled before/after evaluation.

## Current measurement status

- **31** benchmark case definitions.
- **0** independently source-graded, frozen-question current-build answers with verified build SHA.
- **One** complete current-build incident trace reviewed qualitatively and one answer-only trace reviewed cautiously.
- Q1 baseline score remains **not_measured**. These examples are *diagnostic evidence of weaknesses*, not validated benchmark denominators.

## Next steps

- Keep advanced synthetic benchmarks available only for engineering, without distracting from ordinary HomeBrain Q&A.
- Capture the exact registered read-only `causal_light2_off` question and its full JSON, or record prompt deviation explicitly. Preserve source evidence only in the private conversation; use the metadata-only extractor for repository-friendly comparisons.
- Compare later fixes on **the same input/evidence**, and measure answer clarity, causal grounding and latency before approving a production reasoning change.
