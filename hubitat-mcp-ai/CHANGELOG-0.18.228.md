# Hubitat MCP AI v0.18.228 — Historical read recovery and concise incident answers

## Live failure, 29 October

The actual user asked *why* a named device stopped communicating on
12 October. Native V2 resolved the target but read just **ten** recent
29 October watchdog events, repeatedly proposed device-event reads without
deviceId, and attempted a different rule-engine API
(`hub_get_custom_rule`) after the live rules inventory had returned
`Rule-5.1` apps. It concluded only "No independently verifiable claim was
recovered" — not an answer.

The operator then supplied **external ground truth**: the plug socket was
physically disconnected by a user. This overrides causal speculation that
the power-saving rule was the physical cause. Historical timing alone cannot
prove unplugging, automation actuation or an independent Wi-Fi failure.
The app must respect that distinction; its MCP evidence cannot infer a fact
only a person has supplied.

## Architecture changes

- Preserve the model-led tool choice from v0.18.227: no lexical route
  for questions, no new inference calls, and no automatic read selection.
- For a **model-selected** `hub_list_device_events` READ, normalize its
  arguments using an *already independently verified unique device focus*.
  An omitted deviceId is inserted only for that unique exact ID; ambiguous,
  unverified, hub-wide and app-scoped reads are not rewritten.
- If the question explicitly names a calendar incident date and the model
  omitted an event-history time scope, provide `since`/`until` bounds.
  Pad the requested calendar day by a full day on either side because the
  hub's timezone is not independently proven here. Preserve explicit model
  time scopes and never claim source history is complete. Increase a low
  sample limit to 100 without exceeding the normal host read budgets.
- Re-validate each normalized READ against the independently verified live
  MCP manifest and effect/ID/argument guards. No model or host writes.
- The model receives a source-based Rule Machine vs custom-rule hint
  **only when the live rules list actually describes Rule-5.1 apps**.
- Show a **short most-likely connectivity/power explanation** when device
  status and independently attested command chronology support that
  possibility. The answer keeps physical unplugging as a competing
  explanation, rather than asserting a timed OFF command caused a disconnection.
  Detailed event receipts and uncertainty remain in the *technical report*,
  not repeated as boilerplate in the main answer.

## Regression

`pytest -q tests/test_investigation_v2_historical_window_0_18_228.py`

The replay recreates the real bug: a uniquely resolved device with
`hub_list_device_events(limit=10)` and no `deviceId` for a
date-specific question. Tests ensure that one guarded READ uses the
verified ID plus padded historical time scope and that real device events
produce a concise answer, without asserting the operator's physical-unplug
confirmation was found in MCP.

Additional cases reject unknown IDs, multiple target IDs, non-device
event modes, app-scoped calls and proposed writes. The full repository
suite must be green before merge.

## Remaining scope

This is a targeted general source/acquisition and user-facing answer
quality improvement, not full AI causal reasoning parity. If the source
does not retain the requested historical events, HomeBrain should say
the cause could not be established from that read, without substituting a
large source-validation report or guessing the physical cause. A further
development stage is needed for model-directed multi-step source discovery,
rule action execution history and explicit human-verified context in
the final cause assessment.
