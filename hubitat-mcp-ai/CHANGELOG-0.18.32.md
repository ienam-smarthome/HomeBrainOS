# v0.18.32 — Real-world Claude evidence completion and command-dispatch proof boundary

## Live regression after v0.18.31
The user's read-only historical app 3950/device 7103 OFF investigation succeeded through Claude Sonnet and Hubitat MCP: seven paid Anthropic model rounds, ten read tool calls, 69.9 seconds total (64.8 s provider). It recovered the hub-recorded switch-off at **2026-10-12 01:30:01.914 BST**, but named **no verified commanding app**. The response wrongly asserted "command dispatch is established" and the shared source assessor still declared `command_history` unchecked despite the v0.18.27 completion hook.

## Verified architectural defect
`pending_historical_command_read` demanded that `homebrain_device_history.arguments.name` be the target's *numeric ID* (7103), even though the actual local MCP adapter resolves by the verified *label* ("Bedroom 3 Mesh"). The planner therefore never obtained a verified label and returned None, silently skipping its required `command-off` read. The prior mock fixture used name=7103, so CI could not reproduce the live failure.

## Fix
- Resolve the target ID/label through the successful `hub_list_devices` targeted-device receipt's `details.reportedDeviceState.deviceId/label`, combined with the exact numeric ID in the user's objective and the same request's verified device-event history.
- Accept `homebrain_device_history` requested by the resolved label or numeric ID, but only when its returned label matches the verified target; a mismatching/local unverified history cannot expand the command history horizon. Never guess a device from an ambiguous label or another sensor's events.
- Derive the command lookback from bounded same-turn verified `switch` read history (168 hours in the live trace), not a new guessed date range; retain no-duplicate/rejected-write constraints.
- In the pre-synthesis existing generic read-only completion hook, execute **exactly one** corresponding `hub_list_device_events(attribute=command-off, deviceId=7103)` when the installed read gateway is available, and return the read result to the model before it states a conclusion. An empty result marks a source read attempt, **not** a verified absence of historical command execution.
- Apply a typed historical claim guard at the final shared API boundary: without a successful relevant command event, do not publish unqualified "command dispatch is established/confirmed" claims based on a `switch=off` state event. A device-originated state event and a downstream `triggered[]` listener are not proof of an automation command or a physical acknowledgement.
- Preserve default **Free** routing, explicit separately billed Claude choice, Hubitat safety gates, no writes, and the investigation deadline/cancellation mechanism.

## Regression coverage
Fixture modelled on the successful **v0.18.31 Claude response**: targeted ID+label receipt, 168-hour switch event page, label-based local history, no app logs, no command stream. Tests cover exact read planning, direct+legacy ID references, label conflicts, failed/unrelated reads, prior failed command-attempt deduplication, final-answer one-pass command read, and safe handling of unsupported claim text.

All three GitHub CI workflows must pass before merge. This is code-level validation only: after update to v0.18.32, repeat the read-only live investigation once; do not claim that app 3950 issued an OFF until an actual relevant command/execution record establishes it.
