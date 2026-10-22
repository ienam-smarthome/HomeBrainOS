# HomeBrainOS v0.18.62 — Long rule-writing prompts and actionable HTTP 422

## Reproduced root cause
The user pasted a detailed **2,202-character** Rule Machine creation request in the v0.18.61 HomeBrain web UI. The UI returned `{"success":false,"route":"error","message":"Request failed: HTTP 422"}`. The FastAPI `ChatRequest` model applied `Field(max_length=2000)` to both `query` and `prompt`, so an otherwise ordinary creation proposal never reached the agent or Hubitat. HTTP 422 here is input-validation rejection, not a native `hub_set_rule` failure. The web UI ignored structured Pydantic `detail` arrays and reported only the numeric HTTP status.

## Fix
- Raise bounded `query` and `prompt` text ceiling from **2,000 to 12,000 characters**. Keep a finite limit; do not change model routing, authorization, rule execution or confirmation.
- In the web UI, reject text over 12k **before HTTP submission**, without truncating it, and show current/max character counts.
- Interpret FastAPI 422 `string_too_long` response details without echoing request content; display actionable guidance instead of `HTTP 422`.
- Regression tests cover 2,202-char `query` and `prompt`, accept exactly 12k, reject 12,001, verify `/api/ask` returns 422 on oversize **before** agent side effects, and assert web UI diagnostics.

## Safety
This is an API transport/UI fix only. It does not automatically create a Hubitat rule, grant write permission, skip the confirmation process or solve RM disable-at-create/complex logic support. User's requested disabled-first Rule Machine test **must still fail closed** if the connected native gateway cannot guarantee inert rule creation. Do not rerun blindly until actual Hubitat state is checked if any prior write attempt may have occurred.

## Release validation
All GitHub CI workflows required before merge. Live add-on retest needed after updating to 0.18.62.
