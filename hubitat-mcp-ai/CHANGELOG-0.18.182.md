# HomeBrainOS v0.18.182 — Native read-agent source recovery

## Evidence from live testing (28 October 2026)
- A whole-hub audit took 12.38s but model read only 80 INFO log rows
  covering roughly a minute, then incorrectly interpreted an app label
  containing "Low Memory" as a triggered alert and implied the hub was clear.
- A device investigation spent 42.15s, including a 20s full-inventory timeout.
  The model received very little useful source detail from successful mesh/
  health reads, failed to recognise the structured Bedroom 3 Mesh WARN log,
  and ended without a conclusion despite seven successful tool calls.

## General fixes (no question phrase router)
- The native source adapter understands actual `hub_get_logs` result
  `entries`, `time`, `type`, `name` and structured source prefix, as
  well as alternate `logs` schemas.
- INFO rows are counted but not promoted to problems; WARN/ERROR groups
  are normalised by source and message. Changing watchdog counters collapse
  into one group. Counts, returned timestamp range and sampling limits
  are explicit, never "24h coverage" inferred from a requested lookback.
- Structured logs may attest an app/device source ID only when the message
  prefix agrees with source metadata. Log-row IDs are never entity IDs.
- A targeted read with a non-attested device ID may attempt one lazy,
  deadline-limited lookup through the existing complete identity cache/live
  context. A failed lookup leaves the call denied. No mandatory cold device
  inventory before the model interprets a question.
- Previously silent projection gaps now return a bounded list of safe
  source field names and a `projection_empty` flag. Existing typed health,
  mesh and status projections have broader safe field vocabulary.
- When the model exhausts its reads/rounds without producing a conclusion,
  a final bounded tool-free synthesis tries to produce a calibrated answer
  from the retained source evidence. Fallback remains source-only.
- Answers prominently flag INFO-only log samples, missing source projections,
  model claim validation gaps, and known source incompleteness.

## Verification and limitations
Regression fixtures cover both live response structures, source-ID spoofing,
device identity lookup, evidence source redaction and truncated samples.

This release does NOT prove causal accuracy or fully handle arbitrary upstream
tool schemas. Model assertions are still separately labelled as unverified;
physical state and historical completeness remain unknown unless their source
evidence supports them. Existing production Main Ask remains unchanged, and
native V2 still has no write permission. Full Claude-equivalence requires
further cross-domain live comparison and claim-evidence verification.
