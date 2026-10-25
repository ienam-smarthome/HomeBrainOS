# HomeBrainOS 0.18.111 — Restore Ask / New topic after history cleanup

## Confirmed cause
The 0.18.110 compact web UI still calls `activeRequest` and
`requestSequence` in the Ask and New topic handlers. Removing the former
multi-chat code also inadvertently removed their declarations. On Ask,
`if(activeRequest)` therefore throws `ReferenceError` before POSTing
the question to the HomeBrain API. The dashboard can still load because
it does not exercise this click path.

## Fix
- Restore `let activeRequest=null,requestSequence=0;` above the Ask and
  New topic handler definitions, retaining cancellation and stale-response
  protections.
- Keep the 0.18.110 compact UI and temporary in-page follow-up context.
  No saved-chat panel or browser-persistent history returns.
- Add regression coverage executing the **real generated JavaScript submit
  handler** in Node with stubbed network/DOM, verifying Ask POST, contextual
  follow-up, and New topic reset. This protects against future syntactically
  valid but nonfunctional UI refactoring.
- No Hubitat device, setting or automation changes.

## Live acceptance
Update the Home Assistant add-on to 0.18.111 and reload the page.
Press Ask with a question: it should display “Starting request...” and
progress, then show the current answer. Test New topic, then another Ask.
