# HomeBrainOS v0.18.142 — staged V2 semantic planning

A valid whole-home power question returned HTTP 503 in v0.18.141. Source review exposed
a design issue: the *first* AI interpretation step contained the meter identity
catalogue and an optional role-classification job, all behind a generic 503
catch. The user's screenshot alone cannot distinguish a timeout from invalid
model JSON or provider failure.

- Stage 1 produces only a compact typed objective from actual supported
  Hubitat fields and rooms. No meter identities, passwords or device-specific
  routing phrases are sent as part of primary intent selection.
- Stage 2 is an optional, independent, bounded model pass for measurement
  scope on actual meter IDs. All model suggestions require exact live ID/label
  equality; they remain unverified and cannot generate device commands.
- A timeout/invalid classification in stage 2 **does not discard the answer**.
  Unknown scopes are disclosed. For an explicitly individual-load ranking,
  meters with unknown scope are listed *outside* the top-load ranking rather
  than treating a potential whole-house total as an appliance.
- First-stage failures now report a safe diagnostic response with a classified
  outcome and inventory/planning duration, instead of a generic HTTP 503.
  This does NOT assume the answer when no valid semantic plan exists.
- Existing command safety, role precedence, current inventory evidence, V1
  behaviour and API opt-in remain unchanged.

**Test:** run the original whole-house vs individual power ranking from
26 October, inspect semantic plan, enrichment status, and verify that unknown
meters cannot be misrepresented as confirmed individual loads.
