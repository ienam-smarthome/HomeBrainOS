# v0.18.235 — evidence-source frontier and missing-history handling

## Live failure (29 October, historical 14:54 heating stop)

V2 0.18.234 executed nine reads, including a 20-second full-device list that
timed out. It correctly identified the Smart Thermostat Scheduler command
and the thermostat's corresponding idle transition, but still returned the
same host-authored control summary. The source-app INFO log queries produced
zero records in 14:40–15:00 and 45 records on the wider date, with returned
log timestamps only from **16:34 to 23:00**. None were relevant to 14:54.
This does not prove that the older records never existed or that no external
archive could contain them.

## Architecture

- Independent **historical source frontier**: relate a question's explicit
  incident clock, the device's attested controller command issuer, the
  corresponding app-log READ receipts, and the actual returned log time
  boundaries. Report when the currently returned source window does not
  include the incident. Retain unverified timezone and incomplete-history
  qualifications.
- After a same-app historical log read returned rows only *later than* the
  user's incident, decline another overlapping query against the same feed.
  The model remains free to select other verified sources, including
  independent sensor event histories, other app logs or archives.
- Show the source frontier in the model transcript before verbose source
  output, so the AI can decide whether to choose another source or give a
  specifically limited answer. Never infer a TRV's earlier state from a
  different-period scheduler log.
- A named device with a verified unique live identity and an explicit dated
  incident does not require an unbounded `hub_list_devices` inventory. Reject
  that costly fallback and allow source-scoped reads.
- When the final model's leading explanation and exact event citations pass
  verification, a malformed or numerically unsupported **optional alternative**
  is omitted instead of discarding the entire valid explanation. Unsupported
  numeric details in the *leading hypothesis* remain prohibited.
- The host natural fallback now reports when relevant historical controller
  logs were not found in the returned window, and identifies independently
  retained input-device history or archived logs as possible further evidence.

## Verification boundary

No Hubitat writes, no assumed log retention policy, no broadened tool
permissions, and no claims of source-complete historical coverage. Regression
tests replay 0-row incident app logs, 45 later-day INFO records, an unrelated
22:30 controller command, optional model alternatives, and rejection of a
named historical device's unbounded whole-hub inventory.

Passing tests does not prove that the live model can recover a retired
historical input reading. The live source has to actually supply it.
