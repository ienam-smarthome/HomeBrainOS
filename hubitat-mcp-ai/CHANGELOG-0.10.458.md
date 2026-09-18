# Hubitat MCP AI 0.10.458

## Device-history source integrity

Live 0.10.457 validation showed that a Hubitat device-event page can be complete
as an API page while still omitting physical switch transitions visible in the
device logs. Hallway Light 1 was reported by HomeBrain as continuously on for the
entire 18:00-08:00 window even though Hubitat logs showed repeated on/off changes
around 07:00-07:51.

0.10.458 separates those two concepts:

- page coverage means only that the returned event page reaches the requested time
  boundary;
- event-stream integrity means that every physical transition needed for exact
  state reconstruction is known to be present.

HomeBrain currently marks device-history event-stream integrity as `unverified`
unless a future independent cross-source verifier explicitly proves otherwise.

## Conservative interval reconstruction

When event-stream integrity is unverified, semantic history no longer:

- extends a predecessor state to the beginning of the requested window;
- upgrades first-transition inference to complete coverage;
- synthesizes a predecessor from a transition after the window;
- extends an unclosed active state to the end of the window.

Only spans bounded by recorded state rows are paired. Their total is labeled
`unverified-event-stream`: it is an estimate, not an exact total and not a
mathematical lower bound, because omitted transitions can make a recorded on-to-off
span either too long or too short.

## Grounded answer protection

The API serialization boundary now rewrites unsupported history claims when source
integrity is unverified. This covers:

- exact duration claims;
- continuous/all-night claims;
- claims that no activity occurred or that a device stayed inactive.

The corrected answer explicitly states that the device-event stream has not been
independently verified as complete.

## Evidence and diagnostics

History receipts expose bounded source-integrity diagnostics including page
coverage, source-integrity status, duration reliability, source/analysis row counts,
first-window state evidence, predecessor state evidence, and inferred-boundary
context. No full raw event dump is added to the technical receipt.

The generic evidence-review and final-synthesis contracts also tell the model not
to confuse page completeness with event-stream completeness.

## Regression coverage

Tests cover page-complete but source-unverified history, removal of post-window
synthetic predecessors, exact-duration rewriting, continuous-history rewriting,
absence rewriting, explicit-vs-inferred attribute consistency, and the existing
ambiguous-target-before-timezone optimization.
