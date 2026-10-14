# HomeBrain v0.17.62 — Focal event provenance and source-derived diagnostic summaries

## Historical causality
- Fix a historical ON investigation in which the prefetch established the
  19:55 ON correctly, but a later producer selector omitted the requested
  boundary and silently selected the newest 22:45 ON event.
- Ensure reporting-source classification, downstream sensor correlation,
  and optional physical-response follow-up all share the explicitly
  requested ON/OFF focal boundary.
- For a deep why-ON investigation, the auxiliary OFF inquiry prefers
  an adjacent observed OFF **within ten seconds before** the ON, where
  the events form an immediate OFF/ON bounce. Otherwise, it retains the
  older independent investigation of the ON interval's later closing OFF,
  explicitly separate from the initiating cause of the ON.
- Keep explicitly requested why-OFF support anchored to the stated OFF.
  No substitution if the requested boundary cannot be independently found.

## Command-only telemetry
- The request-wide finalisation gate now constructs a source-derived
  diagnostic summary from typed event receipts when a bounded device
  history contains only Hubitat command invocations.
- Group recorded commands by their attributed app, retain separately
  reported state attributes, and distinguish returned event-page absence
  from complete physical transport silence.
- Explicitly leave last actual physical telemetry, MQTT session status,
  command acknowledgement, power state and history integrity unverified.
- This removes unsupported root-cause and communication-failure claims
  elsewhere in the model's original answer instead of chasing individual
  wording variants with further phrase-specific corrections.

## Scope and safety
- Read-only; no device control, app/rule mutation or confirmation changes.
- The source-derived projection is applied only where typed, successful
  command-only event evidence is present. Other diagnostic investigations
  keep their existing synthesis and evidence-completion checks.
- The retained reported-state block originates from the model's targeted
  device read and should still be treated as reported state, not independent
  verification of physical health.
- CI tests are synthetic. Verify in the running HomeBrain add-on after update.
