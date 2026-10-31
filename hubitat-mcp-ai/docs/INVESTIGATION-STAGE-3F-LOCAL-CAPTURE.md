# Stage 3F — explicit, local, expiring investigation capture

Source version: **v0.18.280**, based on merged main v0.18.279.

## Purpose

Stage 3E already supports privacy-safe reporting from replay inputs, but
prior test calls were constructed, not actually observed model responses.
Stage 3F creates the first **in-process opt-in capture hook at the existing
model-call boundary**, without enabling it for the installed add-on.

A capture is possible only if an operator explicitly constructs BOTH:
- a `LocalStage3FCapture(consent="AUTHORISE_LOCAL_READ_TRACE", ...)` instance;
- a `UnifiedMCPAgent(..., stage3_shadow_mode="observe",
  stage3_capture_session=<that-instance>)`.

**Neither argument is exposed by add-on configuration, the API, the UI,
the normal production agent factory, environment variables or remote
requests.** By default the agent remains `stage3_shadow_mode="off"` and
`stage3_capture_session=None`. Stage 3C's original passive counter
observer remains unchanged. There is no deployment or installation in
this development stage.

## Information minimisation and source fidelity

The recorder is called **only after** the existing model chooses tool calls
and **before** the original executor handles them. It copies no prompts,
final responses, free-text model content, real room/device/app names,
credentials, real numeric device/app IDs, raw history values, model
reasoning, source event timestamps or original full tool results.

- Only a small supported READ suboperation catalog under explicitly
  declared read-gateway enums is recognised; unknown operations are not
  promoted to authority.
- IDs are deterministically pseudonymised for the lifetime of ONE local
  session via a random in-RAM secret and HMAC, in separate numeric device
  and app namespaces. The raw originals are not stored in the capture
  records or returned in its reports. The secret is never exported.
- Scoped history time-window equality is pseudonymised into a fake,
  stable one-hour period. The actual date, local clock, elapsed duration
  and event chronology are **not preserved**.
- Previously attempted known READ scopes and verified identity/command-
  producer links are reduced to bounded minimal projections; personal
  names, state values, actual event times and unrelated fields are omitted.
  Projection of a command issuer is for next-read scope evaluation only,
  **not a reconstruction of source-timed causation or physical ACK**.
- The reported origin is always
  `user-labelled-redacted-trace`. Even when the hook is manually attached
  to an actual model round, this is **not independently authenticated**
  trace evidence. Reported genuine-trace count remains zero.
- Only an aggregate Stage 3E report is available. There is no raw replay
  export API, network call or file-writing path in this class.

The metrics are specifically about **recognised read-choice scopes and
repeat suppression**. They must not be used to claim response-quality,
causal-verdict accuracy, actual historical ordering, source completeness
or end-to-end response speed.

## Retention and rollback

- Strict explicit consent token at construction; accept only approved
  domain categories.
- Automatic in-memory expiry within 900 seconds; configurable from 1 to
  900 seconds. A one-shot local daemon timer clears an idle session at the
  deadline, and capture/report/status also check expiry. Synthetic-clock
  tests use deterministic access-time checks.
- Explicit `disable()` clears retained rounds and drops the secret
  immediately and irreversibly for that object. Python garbage collection
  does not guarantee forensic RAM zeroisation.
- Maximum 12 rounds from ONE request identity; mixing unrelated requests
  is refused. A round exceeding 160 prior receipts, 16 proposed calls
  or 60 advertised schemas fails closed. No silent acceptance of large
  or cross-request inputs.
- No disk writes, no add-on settings, no new network endpoint, no
  scheduler/background task, no model client or tool execution, and no
  changes to the original model's actions or final publisher. Observer
  failures are exception-isolated and counted without private details.

## Validation and rollout

This PR includes cross-domain read fixtures, explicit-consent rejection,
expired and disabled sessions, no source-identifier or timestamp disclosure,
request isolation, write gateway exclusion, tool catalog validation, mocked
observation and registry metrics tests.

**Merge gate:** full GitHub Python tests, repository validation and
add-on smoke checks must all pass at the exact PR head. No live upgrade.

**Next gate:** after explicit owner approval for installation and a
supervised short read-only session, evaluate the suitability of genuine
in-process model READ recordings using local aggregate metrics. If the
declared gateway schema omits explicit suboperations, this capture cannot
infer or authorise them; schema support requires separate review.
Only thereafter consider Stage 4 model-authored publication, subject to
separate factual-fidelity regression and a rollback switch.

Revert this additive PR for source rollback. Disabling an explicitly
constructed capture drops its data without modifying Hubitat or HA.
