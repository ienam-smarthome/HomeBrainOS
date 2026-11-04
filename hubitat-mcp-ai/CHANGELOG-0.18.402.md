# HomeBrainOS v0.18.402 — Q1 aggregate source completeness

- The first live `Which lights are currently on?` Q1 response
  on 0.18.401 returned `No lights are currently on.` in 4.054s
  using a complete-looking 211-row bulk context, but the Technical
  JSON exposed only *field names* of the active-light count and
  scope results, so independent completeness/zero verification
  was not available. The answer is not known to be incorrect.
- Add cross-device, source-driven ON/OFF coverage counts for
  recognized light devices and non-light switches, separating
  complete device inventory from missing/unknown switch states.
- Add privacy-safe typed aggregate coverage to ordinary source
  receipts: actual on count, eligible candidate count, unknown
  state count, scope verification, inventory and switch coverage.
- Require matching source-complete evidence before publishing
  unqualified zero-active results; qualify ambiguous, missing,
  conflicting and partial receipts while leaving supported
  no-active answers intact. No new model rounds or Hubitat reads.
- Synthetic tests cover ON, OFF with retained level, unknown
  switch state, label-only Light Sensor, room scoping, false zero
  claims, non-light switches and source receipt integrity.

**No live 0.18.402 post-update verification yet.**
All observations are driver/Hubitat reported states, not independent
physical connectivity proof. See
`docs/ANSWER-QUALITY-Q1-AGGREGATE-COVERAGE-20261104.md`.
