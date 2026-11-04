# HomeBrainOS v0.18.404 — Q1 telemetry evidence saturation

- A real installed 0.18.403 single-device MQTT/health
  answer improved grounding but took **42.635s**
  (8 Gemma rounds, 13 calls) after unnecessary source
  exploration using a device instance ID as an APP ID.
- General single-target status-discrepancy source-saturation
  condition uses already verified status, bounded event
  history, scoped logs and a material source-clock conflict
  to offer one bounded answer without repeated investigation
  loops. Unverified physical/driver cause stays unverified.
- Optional unsuccessful source calls within a round
  do not erase an otherwise sufficient successful read
  and trigger an extra model-planning round.
- Prevent target device IDs being substituted as Groovy
  app/config IDs unless the same-device dependent-app link
  is explicitly verified in typed source evidence.
- Generic synthetic checks cover completion safety and
  source ID namespace separation; read-only by design.

**No post-update live runtime or accuracy measurement yet.**
See `docs/ANSWER-QUALITY-Q1-TELEMETRY-STOP-20261104.md`.
