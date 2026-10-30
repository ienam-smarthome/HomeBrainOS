# v0.18.240 — read beyond actuator commands to investigate upstream decisions

## Live case and Claude comparison (30 October 2026)

The user tested a 02:00–07:30 Bathroom/Shower lighting investigation on v0.18.239. V2 returned an accurate but incomplete 18-line light-only timeline. Diagnostics showed 8 successful reads: unscoped hub events, three light histories, and four app configuration pages. It made **zero input-sensor history reads and zero app execution log reads**. The model-authored narrative was rejected as invalid JSON after reaching a 14-second synthesis budget. Claude independently reported correlations with occupancy, MS605/Hi-P sensors, mode transitions and button device events, plus hypotheses of Home Assistant/SmartThings external activation; these are **not** verified by the V2 receipts. V2 must not copy these as proven facts.

## Architectural improvement

- Introduce a generic, source-attested upstream evidence frontier: detect source-reported actuator ON transitions with no matching **earlier** Hubitat ON/setLevel command in the *bounded* target history; do not claim a complete absence or a physical causal chain.
- Explicitly distinguish independent input sensor event coverage, relevant execution-log coverage and current configuration metadata. An app settings-page read with 95 keys is *not* evidence of historical controller execution.
- Feed this gap to the model while READ rounds remain. If the investigation runs out of normal rounds and adequate READ/time budget remains, allow **one additional model-chosen** opportunity to inspect missing evidence. The host never executes its own suggested read, promotes a textual device name to an authorised ID, or grants write access.
- Expand guarded device-name lookups to eight and default reasoning rounds to eight so a model can resolve the original three actuators **and** independently investigate supporting sensors. A specific caller can still use a stricter round cap; a single bounded source-evidence continuation remains available when a multi-device gap is independently verified.
- Increase the final structured explanation timeout from 14 seconds to a bounded maximum of 28 seconds while retaining the overall investigation deadline and safe, source-attested fallback.
- Expose the gap and whether a source-evidence challenge occurred in diagnostics. Tool summaries keep the missing-evidence plan ahead of distracting command counts.

## Safety and accuracy boundaries

- Absence from a returned, capped Hubitat event sample is not proof that Hubitat never issued a command.
- Close timing between sensor activation and light ON is not independent proof that the sensor caused the switch.
- Hubitat cannot by itself prove actions from Home Assistant, SmartThings, Aqara or Hue scene automations; external platform trace is needed before attribution.
- A current app config page or a static source read cannot prove what happened at an earlier incident.
- No MCP tool permissions changed; the native investigator remains a separate read-only test mode.

## Validation requirements

Replay independent historical target-light reads and source-attested app attribution; assert that current config metadata cannot satisfy controller execution evidence. Verify distinct sensor history and logs, date mismatch, one-device isolation, invalid device IDs and no write execution. Run the full suite, release metadata validation, application import checks and add-on container smoke before merging. Live correctness needs the user's next installed-version test.
