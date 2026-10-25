# HomeBrainOS 0.18.110 — Compact single-answer UI

## Live investigation review (25 October 2026)
The read-only Livingroom Light 1 test on v0.18.109 finished in 45.87 seconds
with six Gemma cloud rounds and sixteen reported successful read receipts.
It identified app 4019, sampled Linptech Kitchen events and light history,
but did not retrieve the installed Groovy implementation or verify the
30-second inactivity / five-minute backup OFF branches. Its assertion that
a setLevel(50) command *directly caused* a 12:13:54.150 ON is unsupported
by a command timestamp of 12:13:54.193 (43 ms later). The investigation
reported partial coverage. Further reasoning work is still needed; this
release does not claim to have solved the lighting cause.

## UI change
- Remove saved chat tabs, collapsed historical turns, expand/collapse controls,
  chat-storage warnings and the surrounding chat toolbar.
- Render just the current answer directly below Ask/Speak. Keep technical
  JSON, copy, audio, outcome badges, live choices and confirmations.
- Replace the old New chat list with a compact New topic control. Reset
  cancels any pending browser request, clears in-page context and creates
  a fresh session ID. The backend's normal read/write confirmation protections
  are unchanged.
- Keep a maximum of eight recent user/assistant text messages in memory in
  the current open tab for contextual follow-up, without persisting them.
  Refreshing or reopening starts fresh. Existing saved browser transcripts
  under the previous local/session storage keys are retired and cleared
  on loading the new UI.
- No Hubitat automation, settings, or device modification.

## Verification
UI structure, prior regression contracts, bounded follow-up context,
session-reset safety and full inline JavaScript syntax are covered
by release tests and the existing CI gate.
