# HomeBrainOS v0.18.147 — V2 friendly-label precedence and actionable ambiguity

A repeat V2 test (after .146) failed with HTTP 422 despite naming "Bedroom 3
Mesh" in full: "Ambiguous device name: multiple Hubitat devices match the
same phrase." The previous host matcher treated a live user-assigned device
label and the distinct device's generic `name` as equally authoritative.

This release changes **identity resolution**, not question-specific keywords:

- For the *same complete phrase*, a unique, exact Hubitat **friendly label**
  has priority over a different device's underlying/generic `name`.
- Longer whole-name matches still take precedence over shorter embedded
  phrases, regardless of label/name source, and multi-device questions may
  retain independently identified separate targets.
- If two separate Hubitat IDs genuinely share the same best friendly label,
  or neither has a stronger trusted friendly-label identity, matching remains
  ambiguous and **no device is selected automatically**.
- Authenticated V2 users now see bounded, sanitized, independently verified
  matching candidate labels and IDs in this error. Select the intended ID
  under Advanced rather than being told to enter a name already present.
- Automatic question matching, the .146 single-device timeout fallback and
  manually entered device-name matching use the same rules. Explicit numeric
  IDs remain independently checked against refreshed Hubitat inventory.

Synthetic regressions cover label-over-generic collisions, name-only
devices, duplicate friendly labels, duplicate generic names, longest-match
precedence, multiple distinct targets, and model-name injection attempts.

This is a read-only opt-in V2 improvement. No production V1 route, Hubitat
control, permission policy, device setting, or automation was changed. The
release does not claim the live inventory actually contains a label-vs-name
collision; it repairs that general collision class and makes genuine duplicates
actionable when they occur.
