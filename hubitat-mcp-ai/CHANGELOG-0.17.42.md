# HomeBrain 0.17.42 — Scoped app-decision evidence handoff

## Live verification and remaining gap

The 0.17.41 historical manual-OFF investigation correctly preserved the
source Hubitat BST offset and established the OFF command producer app 1251.
The journal recorded FP400 Computer Desk active ~6.3 seconds after OFF and
Linptech Kitchen active ~102.4 seconds after OFF; neither source was proven
eligible to turn on the light. The app 4019 log request succeeded and returned
**two rows** but the historical collector handed the model **only the number
two**, not the messages. This made any supposed review of their lockout
decision content impossible.

The native OFF state also lists app 4019 handlers
`lightSwitchHandler` and `motionLockoutOffHandler` as triggered.
These references indicate the Hubitat state event named those handlers,
but are not standalone proof that any handler completed a decision or
inhibited motion.

## New source-aware evidence architecture

- New `scoped_execution_evidence.py` provides bounded, labelled, read-only
  log excerpts directly to the reasoning context: up to 12 rows, up to 240
  characters each. Each includes source-row ID, available source clock,
  offset-verification flag, app-ID verification basis and log level.
- **Public technical evidence remains count-only:** raw log message bodies
  do not enter the API's persistent receipts. Source metadata separately
  reports rows explicitly matching app 4019, those relying solely on the
  requested backend filter and any mismatched rows excluded. Basic
  secret/email redaction is performed before passing excerpts to the model.
- The model must cite source-row IDs for positive claims about a lockout
  decision and distinguish handler-entry evidence, lockout activation,
  inhibited motion ON, and unrelated messages. A log query succeeding does
  not prove complete log capture, while a zero or ambiguous result does not
  prove no decision occurred.
- OFF-state `triggered` handler references are now extracted as
  `associatedAppEventHandlers`, with explicit fields that neither handler
  execution nor lockout decision is verified. Source offset and focal match
  are required.
- This is an **evidence acquisition/handoff** improvement. It does not
  hardcode text markers as conclusive indicators of lockout; it leaves
  causal interpretation to source-grounded synthesis and retains the
  shared `investigation_coverage` distinction between checked and proven.

## Scope and limitations

No new MCP calls or journal queries; the already retrieved bounded app
logs and device history are reused. No device or rule writes, changes to
activation settings, background capture rate, or Historical Journal retention
(7 days / 200,000 rows).

Current app 4019 settings still do not provide authoritative activation
eligibility for the FP400 Computer Desk or Linptech Kitchen sensors. A
handler named in an OFF event is not proof that the three-minute motion
lockout engaged. These limitations must remain explicit.

## Live validation

Repeat the same 0.17.41 manual-OFF lockout question on 0.17.42.
Check the public technical output for counts of actual app-4019 excerpts and
`associatedAppEventHandlers`, but **no raw private log message contents**.
The answer should reference or distinguish any relevant app-log excerpts
rather than declaring a log-content search from a numeric row count.
If the log rows are ambiguous or filtered with unverified source identity,
the final verdict remains *execution unverified*.
