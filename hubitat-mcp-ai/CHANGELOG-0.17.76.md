# HomeBrain v0.17.76 — Recover missing historical focal events

## Live regression

The v0.17.75 historic Livingroom Light question returned 22 tool calls, eight model rounds and a contradictory answer. Its command-on history still contained an app-issued SenseCap D1 Settings `on()` at 19:54:46.691 BST, but its latest-N state-event pages had evicted the 19:55 ON and the earlier 19:54:57 OFF, and no `skills_focal_state_window` or producer log metric fired. The v0.17.74/75 bounded-read planner had a circular prerequisite: it required the missing focal ON state to be present in an interval before it could query for that state.

## Corrections

- In `skill_focal_window.py`, when a particular dated ON is missing from the interval history, recover a **read plan only** from a single, verified same-device command-on with a source app, an unambiguous device ID and the historical date and minute provided by the user. Read the entire named minute plus prior command margin; derive UTC bounds using the matched command event's offset.
- Preserve full minute-specific ON candidates and the nearest earlier OFF when projecting state events; report `sourceVerifiedOn` only when exactly one ON is observed.
- `causal_evidence_graph.py` now permits a source-typed, successful exact-window ON receipt to establish an incident focus even if all generic recent intervals have evicted that event; it never synthesizes an event from a command alone. If multiple ONs appear in the requested minute, the focus stays ambiguous.
- Fix an unrelated historical safety issue: an explicitly timed query must never silently select the only surviving newer interval as its event.
- After source reads, if the named ON remains absent, undecodable or ambiguous, issue a calibrated fail-closed summary from verified command evidence and source outcomes. Do not expend more AI model rounds trying to reinterpret unrelated later events as the requested cause.
- Add source-level regression tests for missing and recovered ON/OFF, empty and multiple ONs, incorrect dates, UTC conversion, strict device identity, and read-only failure communication.

## Other result

The separate v0.17.75 Tab S9 FE Internet-blocking Rule Machine proposal and confirmed creation were reported successful (appId 4227, one-time `off` scheduled for 2026-10-15 20:14:08 BST). This release does not modify that workflow or any live Hubitat devices, settings or rules. Scheduling success is not proof that the rule fired; the device was already reporting `off` before the rule was created.

## Live acceptance

After installing the updated add-on, repeat the read-only Livingroom Light question. Require the `skills_focal_state_window` metric and a `hub_list_device_events` call for device 7805 with absolute `since`/`until` around 19:54:46–19:56 BST. If the source still retains both 19:54:57 OFF and 19:55:00 ON, the final answer should preserve their timing. If no state data remains, the final answer should report historical uncertainty without claiming SenseCap definitely caused the physical ON. The producer-log read should also be scoped to app 4129 with UTC-correct bounds.

## Limits

The upstream Hubitat MCP gateway may have discarded or truncated old event history. This release cannot reconstruct absent historical records or verify touchscreen/MQTT source actions without surviving upstream logs. Automated validation is separate from live acceptance.
