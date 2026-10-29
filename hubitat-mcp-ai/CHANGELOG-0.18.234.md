# v0.18.234 — incident-relevant upstream decision planning

The v0.18.233 live heating test improved to 16.954 seconds but still failed
to explain *why* the Smart Thermostat Scheduler ended heat demand. The
agent read controller configuration metadata rather than the scheduler's
execution INFO records. The resulting model hypothesis failed its source
numeric validation and fell back to a host-authored command→state timeline.

## Root causes corrected

- The upstream-decision hint had been selecting the **latest command
  on the entire requested day**, not the command relevant to the user's
  specified incident clock. The same 29 October event history now includes
  a separate 22:30 thermostat-mode command from an unrelated app. This
  could wrongly shift investigation away from the 14:54 thermostat scheduler
  decision.
- Rank attested issuer commands by proximity to the user-supplied clock,
  using UTC and BST candidates only for ordering, never as proof of hub
  timezone. Reject unrelated issuer candidates more than 30 minutes
  from all clock candidates; do not select an arbitrary controller.
- Add **one bounded, model-selected evidence-completeness challenge** when
  the model tries to finish with only an actuator action while independent
  app history is available but unread. It is a user-message critique to
  the existing model, not an executed read, a keyword router, a hard-coded
  app ID, or a tool permission. The model may choose the
  live-manifest-attested app log read, another independent read, or an
  explicitly limited answer.
- Retain the read-only effect, numeric ID, schema and historical scope
  checks on any model-chosen tool call. No new Hubitat write paths.
- General planner explains the next provenance step: from a named
  input mentioned in an attested app decision, use source-verified device
  identity and relevant sensor readings rather than inventing its ID.

## Regression coverage

The 29 October heater replay includes the unrelated 22:30 controller
command and an upstream scheduler INFO record describing radiator demand
satisfaction. Tests enforce the correct incident-time issuer, one
bounded follow-up after a mistaken app-configuration read, no unpermitted
log suggestion, and model prose only if source citations independently
match. This is still not proof of Claude-level reasoning in live use.
