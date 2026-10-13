# HomeBrain 0.17.46 — Deterministic app settings and explicit historical anchors

## What the 0.17.45 live tests exposed

- A direct request to read **app 4019 current persisted lockout settings** spent three provider rounds with zero executed live tools, then inaccurately reported an undeclared configuration tool. The same add-on's host-side prefetch could retrieve the setting through the installed `hub_read_apps_code` gateway.
- A nearby response investigated a newer 13 October OFF and could not independently prove manual provenance. A separate explicit user question named **23:49:27 BST on 12 October**, physical button device 746 and controller app 1251. Reconstruct/correlate wording must activate the historical lockout path and never silently select the newest state if its requested event is absent from the returned history.
- The actual living-room button label contains an emoji and writes *Living Room* with a space, whereas the light is named *Livingroom*. Naïve starts-with matching excluded the relevant push-capable controller.

## Changes

1. **Current configuration:** A narrow named-app lockout-settings request invokes the already-advertised, permission-gated `hub_read_apps_code/hub_get_app_config` tool directly with `includeSettings=True`. No model discovery or fabricated tool name is needed. Return only typed lockout settings; if trigger/controller fields are not included, say unverified rather than guessing them. Spell-out three-minute expectation is compared separately with today's persisted minutes.
2. **Historical objective recognition:** `reconstruct` and `correlate` now enter the same source-grounded manual-lockout path as `investigate`.
3. **Canonical user-labelled clock:** When the user explicitly supplies BST/GMT with a complete dated clock, validate the offset for that date using the Europe/London timezone. Retain the UTC anchor even if a newest-N device-history page no longer includes that earlier state. Reject mismatched BST/GMT seasonal labels. An unlabeled historical time still requires a supported source-day offset.
4. **Evidence anchoring:** If the requested state transition is missing, preserve `selectedOff=null` and `requestedEventStateObserved=false` while querying **app logs and the Historical Journal around the requested UTC instant**. Do not call a later OFF the requested OFF; lack of old state evidence must remain explicit. Only calculate named post-OFF motion correlations when an OFF was actually observed.
5. **Controller identification:** Normalise room-name spelling and emoji while correlating native push-device identities. An explicitly named controller ID must match a live identity; a unique name-based candidate is marked as *candidate, not persisted-config proof*.

All changes are read-only. No stored setting of app 4019 is modified, including the verified 300-minute value. No settings or journal retention changes.

## Validation

Regression tests cover failed/unavailable app gateway, no hallucinated mode/button fields, three-minute expectation, direct orchestrator provider bypass, exact 12 October BST-to-UTC conversion, missing historic OFF state without substituting a newer event, and app 4019 log window anchored to 12 October. CI must pass before merge.

Following installation, rerun the current app 4019 configuration question and separately the precise **12 October 23:49:27 BST** reconstruction. Compare tool calls, provider rounds, selected focal event, app log bounds, and missing evidence. The stored duration and historical lockout effect are distinct claims.
