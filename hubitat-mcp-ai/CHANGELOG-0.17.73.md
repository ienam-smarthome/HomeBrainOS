# HomeBrain v0.17.73 — Exact incident-window evidence integrity

## Root-cause investigation

The supplied v0.17.72 live trace demonstrated that the final answer accurately quoted the SenseCap D1 Settings on() command and the 19:55:00.049 ON report but **never received the intervening 19:54:57.946 OFF record** in any persisted evidence receipt. Previously the OFF record was visible. Relative latest-N pages silently changed as new events accumulated, making a historical incident's neighboring transitions disappear even when its interval start remained available.

A model-authored producer log request also used 2026-10-14T19:50:00Z (20:50 BST), a shifted time window that did not contain the incident at 19:54 BST.

## Changes

- Source-first planner `skill_focal_window.py` anchors the historical query to the uniquely identified observed ON and same-device, same-transition preceding command.
- Before final synthesis, HomeBrain performs an **absolute-time switch history query** covering the earlier command, any intervening OFF, and the focal ON; no latest-N shortcut counts as checked for that exact window.
- Independently performs a bounded **producer app-specific native log query**, correctly converted from the recorded BST offset to UTC. An earlier log query shifted an hour or missing `until` does not count.
- Successfully returned focal switch events are separately projected into a compact, typed evidence receipt, so the OFF/ON timestamps survive even if the generic gateway receipt only contains a summary. Empty/undecodable payloads cannot create imagined events.\n- Neither read is scheduled without unambiguous matching device identity and a verified preceding command. Absent source content is not turned into a fabricated negative finding.
- Grounded answers disclose whether an exact focal history read was attempted, and describe producer app configuration/log queries as queries, not independently proven initiating settings or historical executions.
- Regression tests recreate the real incident symptom: prior OFF missing from all initial receipts, correct targeted read recovering OFF, and UTC-shifted app logs not satisfying source coverage.
- Registers aggregate `skills_focal_state_window` and `skills_focal_producer_logs` counters.

## Limits and acceptance

This release corrects **retrieval and source-window enforcement**, not physical causation. If the MCP server/hub no longer retains an older state or MQTT message, neither tool nor language model can recreate it reliably. Current configuration alone cannot prove how the touchscreen/MQTT triggered an earlier command. After add-on update, repeat the read-only Livingroom Light 1 19:55 investigation, verifying whether the exact-window source returns the previously recorded 19:54:57.946 OFF, and the producer log window is UTC-correct. No devices, settings or rules are altered by this update.
