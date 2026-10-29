# Hubitat MCP AI v0.18.232 — Explain the actual incident, not the newest telemetry

## Failure reproduced

On 29 October at 14:54 the user asked why heating stopped. Native V2 had
source-attested heating setpoints and thermostat operating states showing
scheduler-driven demand changes, but published battery status and counts of
12 historic commands. The incident relevance packet included only the six
newest **temperature** readings (at 15:18–15:23), excluding the actually
decisive 14:48 heating and 14:54 idle transitions. The final model returned
unstructured prose, the eight-second second pass failed, and the host showed
the command catalog. A generic whole-hub inventory read also wasted 20 s.

## Architectural changes

- Extract explicit clock references (e.g. `2:54 pm` or `14:54`) and rank
  material verified source events by proximity to the user's incident time
  without pretending the hub timezone is verified. Limit repeated noisy
  telemetry so control changes and state transitions reach the reasoning
  model. Without an explicit clock preserve the original source order.
- Include source-attested thermostat setpoint, thermostat mode and other
  actuation command types, not only simple on/off/dim commands. This works
  by evidence type, not question keywords or device identities.
- Increase the bounded reasoning packet from six newest observations to
  a diverse, chronological selection of incident-proximate events, each
  with its actual value and producer. Prioritise this packet in the tool
  transcript ahead of raw source summaries, retaining the unchanged full
  read receipts in the diagnostic report.
- Give the final reasoned synthesis up to 14 seconds within the *existing*
  overall deadline, rather than forcing a slow model to produce a complex
  JSON proof in eight seconds and publishing battery/command counts.
- If model-authored evidence-anchored prose fails verification, a narrowly
  source-grounded **operating-state/control-sequence** explanation can show
  the actual setpoint changes, heating-state transition and controller
  name without publishing device IDs or asserting unverified TRV causation.
  This is a factual fallback, not a substitute for independent AI reasoning.
- Preserve separate read-only permission/identity guards, receipt matching,
  model hypothesis verification and full technical diagnostics.

## Verification and limits

The regression test uses the observed 14:48 26°C heating target, 14:48:36
heating transition, 14:54 12°C target and 14:54:36 idle transition together
with 24 later temperature observations. Tests demand recovery of those
relevant events, an understandable source-bound reply when the model emits
ordinary prose, and no invented radiator-specific cause. Cross-domain
model explanations still require live tests and comparison against
independently sourced answers.

No Hubitat writes or live Home Assistant installation are performed by this
release.
