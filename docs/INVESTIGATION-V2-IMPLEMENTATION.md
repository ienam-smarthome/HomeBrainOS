# Investigation V2 — staged evidence-first implementation

The merged RFC remains authoritative: [RFC-INVESTIGATION-V2.md](RFC-INVESTIGATION-V2.md).
This implementation is an **explicit opt-in evaluation library** that can use
existing MCP execution and model transport when directly invoked. It is not
connected to production HomeBrain request routing or final synthesis.

## Implemented through 0.18.127

- A single canonical case file from timestamped device events and app-log rows.
  Source clocks and offsets are preserved, observations deduplicated by typed
  identity, and separate command versus state stages are maintained.
- An allowlisted adapter for the existing host-produced
  `typed_existing_rule_partial_settings` projection. Its `config_stored`
  records have `time_basis=read_observed_at`: they are values read **now**,
  not proof of installed code's effective semantics on an incident date.
  Credentials, unapproved fields and UI text are never copied to the case.
- Prepared, opt-in schemas for `typed_app_execution` and
  `typed_transport_ack`. These produce distinct epistemic stages **only**
  from successful, explicit, read-only host receipts with verified IDs and
  offset-bearing timestamps. Current production may not yet emit these
  exact types, so the adapters cannot claim unavailable execution evidence.
  Untyped or textual app logs remain mere log statements.
- A bounded *model-proposed* read-plan validator. The model is responsible for
  naming a missing discriminator, information gain and candidate tool. The
  host verifies the tool exists in the current MCP manifest, that its
  operation is explicitly advertised or learned from trusted discovery,
  the arguments match advertised schemas, the target ID was independently
  resolved, and the call is classified as read-only.
- Per-request read caps, exact duplicate prevention, and limited suppression
  of unproductive `hoursBack` growth for already capped history pages. The
  engine **does not execute** these proposals or decide which hypothesis is
  correct. No word-based investigative path or named-device exception is used.

### Contract boundaries

`review_model_read_proposals(...)` accepts `MCPTool` objects returned by
trusted live discovery, `verified_entity_ids` from host resolution and
`learned_operations` only from actual trusted discovery results. **Never**
feed values from an LLM assertion into these host-authority parameters.
Execution must still use the existing MCP executor's permissions, actual
schemas and write confirmation boundary. This library is preflight only.

`source_complete` requires independent, explicit integrity and completion
proof. Pagination reaching a requested date or requesting more hours does
not establish an uninterrupted physical-state timeline. The case remains
useful even when the actual cause stays unverified.

## Acceptance / smoke tests

```bash
python -m pytest -q tests/test_investigation_v2_evidence.py
python -m pytest -q tests/test_investigation_v2_adapters_planning.py
python scripts/run_release_gate.py
```

The October overnight fixture is a sanitized representative subset, **not**
the entire device history. Additional tests cover current-versus-historical
config values, log-versus-execution, ack-versus-physical state, malicious or
unknown tool calls, hallucinated targets, duplicated/capped reads and other
device classes without text-route heuristics.

## Phase C: explicit bounded MCP read harness (0.18.124)

`investigation_v2.read_loop.run_read_only_investigation` now accepts an
explicit model-proposal callback, an existing `ToolExecutor` and its matching
live MCP client, plus independently verified entity IDs. It bounds model
rounds, approved reads, the wall-clock deadline and per-read timeout. It does
not add any background work or automatically intercept user requests.

Each approved read is executed by the existing host executor. The raw MCP
payload is not passed into V2's case file: the `receipt_projection` module
only admits ID-matched dated device events, the existing validated partial
app-settings projection and strictly timezone-aware log timestamps. Unknown
source shapes remain unverified. No user-supplied or source-supplied free-form
description or credential is forwarded to the model.

Model hypotheses are *candidates*, accepted with supporting or conflicting
case-file record IDs and a discriminator. The host validates those references
and never upgrades the model's proposed root cause into an independently
verified fact. The original user question is preserved at every round.

This stage is a **manual/test integration seam**. A real proposal-model adapter
and carefully measured V1/V2 read-only shadow comparison are subsequent PRs.
No live HomeBrain routes, automation writes, confirmation or production
final-answer validators are altered.

## Phase C/D: opt-in model-led evaluation (0.18.125)

`V2ModelProposer` reuses the currently configured
`ChatTransport.chat(messages, [])` provider, asks the model for structured
hypotheses and discriminating read proposals, and supplies only host-projected
read tool names/schema (not unmanaged tool descriptions). All JSON plans remain
untrusted and are validated by the existing V2 planner; no native model tool
call grants permissions.

`evaluate_v2_with_model(explicitly_authorised=True, ...)` is an explicit
integration entrypoint combining model planning, a bounded authorised MCP read
loop and a model-backed evidence selection / ranking round. **It is not wired
into the production agent, feature toggles or normal user conversations.**

`assemble_grounded_answer` renders observed event types and source times from
the case file rather than treating the LLM's narrative as verified facts.
All material command events survive even if the model omits their IDs. Possible
explanations remain clearly marked as hypotheses and incomplete historical
coverage stays explicit. The checker exposes model omissions/invalid IDs
without discarding independently supported observations.

The acceptance tests use mocked Ollama HTTP through the **real** ChatTransport
and fake Hubitat MCP reads; no physical devices or hosted providers are called.

## Phase D: atomic claim verifier and targeted revision (0.18.126)

`atomic_claims.review_atomic_claims` treats each model-proposed factual
observation as **one typed claim**. Its asserted stage, action, value, device
target, actual producer, UTC time and observation time basis must all match
the canonical record exactly. Source IDs alone do not certify what an event
means. Unknown records, swapped actors, command-to-physical-state promotion,
fabricated completion or additional unverifiable free-form prose are refused.

`apply_targeted_repair` may accept replacements **only for claim IDs
that failed the first audit**. It cannot change an already approved claim or
introduce unrelated IDs. `synthesize_atomic_with_chat` allows at most one
no-tools model repair response, then uses the existing host evidence renderer
to retain every material command and explicitly qualify hypotheses.

`evaluate_v2_with_model(enable_atomic_claim_validation=True)` activates
this path **only when the caller already supplied explicit V2 experiment
authorisation**. The option defaults to False, so no legacy evaluation or
production response behavior changes. The current renderer intentionally
does not accept arbitrary model-authored narrative as a verified factual
claim; a broader causal prose capability requires separate clause-level
evidence checking and objective quality validation.

## Phase D / early E: source-linked explanation + replay metrics (0.18.127)

`narrative.review_links` validates model-chosen links using immutable source
record IDs, UTC instant ordering, matching device targets and the specific
command/state stages. `render_evidence_narrative` adds a concise narrative
about what these verified pairs show **without asserting physical execution
or causality**. If no link passes, bounded host-selected adjacent command
evidence remains available. No named app or device route is embedded.

`enable_evidence_narrative=True` is accepted by the explicit V2 evaluation
seam only when `enable_atomic_claim_validation=True`. Model links are
collected with the existing atomic claim model turn, without adding a new
provider round. Neither feature is enabled in normal production chat.

`replay_scorecard` reports type-grounded V2 command/state retention, valid
source IDs, validation flags and optional measured reads/latency. For supplied
V1 or external reference text it can only count **literal source timestamps**,
not semantic correctness; missing baseline answers remain unsupplied instead
of guessed. This is measurement infrastructure, NOT a completed Claude/V1/V2
quality evaluation. Independent human/semantic scoring and performance runs
are still required.

## Manual test access (0.18.128)

A disabled-by-default V2 test panel is available at `/v2-test` once an operator
enables the add-on option `investigation_v2_testing_enabled` and sets a
unique `investigation_v2_test_token` of at least 16 characters. The panel
requires the token on each request (it is not cached), an explicit run opt-in,
and exact device IDs verified against fresh Hubitat inventory. It invokes the
existing opt-in evaluation seam with atomic claims + source narrative turned on,
returning an actual read/latency scorecard. Captured V1/Claude text is optional
and its score is **only literal timestamp presence**, not semantic equivalence.

The general chatbot remains V1; V2 test requests neither reuse production
chat tasks nor gain Hubitat write privileges. Do not expose the optional direct
port to untrusted networks, and switch the test option off when done.

## Browser error diagnostics (0.18.129)

The V2 test page now retains HTTP status and safely summarizes structured FastAPI
422 field errors and ingress/server error objects instead of rendering
`[object Object]`. The UI rejects blank questions, malformed device ID lists
and too-short tokens before submitting, without storing the token.
Endpoint-level tests exercise the actual FastAPI route with a fake live Hubitat
inventory and fake evaluation, plus disabled, mismatched-token, invalid-ID and
body-validation cases. This does **not** claim a live Hubitat model test passed.

## Incident-first forensic report (0.18.130)

For explicit dated investigations, V2 now proposes a host-gated bounded initial
device-history read for the verified target before asking the model to
investigate hypotheses. An insufficient page can trigger one enlarged read, and
both must pass the same MCP/ToolExecutor read-only safety checks. The read
adapter scans a bounded returned page before time-window filtering, avoiding
the earlier failure where unrelated recent events consumed the retention cap.
The evidence schema records source oldest/newest timestamps and whether a page
reached the requested start; it never equates page reach with source integrity.
The operator test page displays a compact chronological report, tentative
competing-controller lead when independently linked issued commands exist, and
next checks. Full source-ID transcript remains available under Investigation
details. Normal Ask and writes are unchanged.

## Device identity resolution (0.18.131)

V2 test users can now ask a question naming a Hubitat device without knowing its
numeric ID. The admission layer matches full names or labels using the freshly
read Hubitat inventory, gives longer overlapping aliases priority and rejects
ambiguous/absent identities without executing a read. Optional advanced device
name or exact ID override uses the same host-verification boundary. The model
never invents or grants device IDs; all downstream MCP read-only checks remain.
Normal V1 is unaffected.

## Source provenance and qualified explanation (0.18.131)

The V2 receipt adapter also recognizes the existing structural Hubitat
`producedBy` representation as a relative `/installedapp/configure/<id>`
link; only the app ID survives projection (neither HTML nor unverified label).
Reports avoid an all-empty source column, explain UK autumn DST transitions
and interpret dimmer `setLevel` as probable ON intent, not physical proof.
Planner timeouts remain explicitly flagged and are not silently treated as
successful multi-source reasoning.

## Relevant causal focus & typed app identity (0.18.132)

The V2 planner's live `hub_list_apps` and `hub_list_rules` reads now project
strictly validated *current* app ID/name pairs into the canonical case and
model evidence brief. These are descriptive identity metadata only, never
historical runtime logs or proof that an app executed. Conflicting IDs and
untrusted label shapes cannot be treated as identities. The primary possible
controller-interference pair is selected by temporal relevance to the user's
incident window, not by first position in a broad chronology. An unproductive
follow-up read is explicitly recorded as `no_new_usable_evidence`, preventing
an identical expensive next model planning call. V2 remains opt-in read-only.

## Hypothesis clock integrity and read-plan diagnosis (0.18.133)

The V2 host now validates model-authored hypothesis clock strings against
actual *linked* record timestamps. Every displayed HH:MM must explicitly
identify its timezone (BST, GMT or UTC), and match at least one source
record cited in that hypothesis. An ambiguous or unsupported clock claim
does not enter the user-facing hypotheses; raw timestamped evidence remains.
The model receives the same requirement as a planning instruction.

The planner's read schema projection now includes nested required fields and
additionalProperties=false, reducing invalid model tool requests. Test details
now expose bounded, non-sensitive host rejection codes, current app identity
mapping, planning rounds and read counts. This allows diagnosis of
no_approved_discriminating_reads without revealing raw MCP responses.
This release does not claim the underlying app config/execution tools are
available; that remains a live MCP manifest and history question.

## Planner reliability and measurable preflight (0.18.134)

In opt-in testing, host-retained source command IDs enable a single read-only
app-identity lookup *before* model planning, through exactly the same MCP
manifest, schema, entity and ToolExecutor safety gates as model-proposed reads.
There is no device-specific keyword routing or fallback hallucination. The
planner now sees a compact projection containing all canonical event IDs,
command-versus-state stages, explicit UTC/local timestamps, actor IDs, and
coverage metadata; exhaustive original evidence remains unchanged for claim
verification. Timed AI rounds report safe input length, timing, budget, and
status without collecting private model text or tokens. A planning timeout is
not interpreted as a host read rejection. The test UI exposes these metrics.

Only the opt-in V2 evaluator enables identity preflight by default. V1 and
actual Hubitat writes are unchanged.

## V2 history consistency and planning-failure fallback (0.18.135)

Explicitly dated V2 investigations take two distinct, bounded, permitted
history snapshots (smaller and larger pages) before reasoning. The returned
historical command and state sets are compared as source projections; missing
from one response never proves the event did not happen, and even identical
samples do not establish full source integrity. Bounded filtering-drop counts
explain rows excluded for scope, invalid metadata or retention limits.

The operator test also attempts one read-only current app configuration when
command-history evidence independently verifies an issuer ID that is missing
from the app-list identity catalogue. All calls pass the live manifest/schema,
entity scope, read-effect and ToolExecutor safety checks. A current setting is
never presented as historical execution evidence.

When the LLM planner times out or errors, host-only synthesis preserves
canonical evidence without further costly provider selection/repair requests.
The explicit V2 model planning time budget is 60 seconds, and diagnostics
retain source sample counts and planning elapsed time. Production V1/writes
are unaffected.

## Human-readable measured duration (0.18.136)

The test dashboard displays elapsed API-reported wall-clock duration in
minutes plus seconds (three-decimal precision), and in total seconds. Both
are derived from the same elapsed_ms measured by the backend; exact original
milliseconds remain in the copyable technical report. Invalid/missing times
fail gracefully. The command-retention label now says *retrieved*, not that
Hubitat history is complete. Budget-limited/timeout experiments explicitly
report their incomplete status instead of the ambiguous 'Test complete'.

## Host-classified MCP read failures (0.18.137)

V2 read failures now expose a narrow local reason-code enum (timeout,
transport, HTTP, MCP protocol/tool result, missing authoritative result,
read-executor failure, identity mismatch). This information is derived solely
from host-known exception **types** and ToolExecution shape, never server
messages, raw MCP bodies, URLs or credentials. Errors appear on the typed
coverage receipt, in bounded technical `read_failures`, and briefly in the
human report. A failed tool read is not proof that the requested source data
doesn't exist, and an operation that only returns coverage does not become
a verified historical state. Live tests should compare cause codes from
previously opaque app/source calls while retaining unchanged write gates.

## Relative time and interval-answer mode (0.18.138)

V2 resolves explicit 'today' and 'yesterday' periods from the hub's IANA
calendar zone and a server-side, timezone-aware request clock. This mode
retains timezone ambiguity guards and never infers historical coverage solely
from page reach. Single-word device labels shorter than six characters are
admitted from an unambiguous, complete noun phrase ('the TV', 'my fan'), not
from incidental short words. Tool proposals missing deviceId can be completed
only from exactly one independently verified Hubitat device ID, without
changing a supplied/contradictory target and without bypassing normal
manifest/schema/effect gates.

For explicit state-duration questions, the host reads bounded history then
calculates ON/OFF sessions from actual state-reported 'switch' transitions,
not command intentions or model-generated timestamps. No event means no
numeric duration, and an open final session is projected only to the request
time with explicit unverified-current-state and incomplete-source caveats.
This generic pathway is not tied to TV IDs or product-specific terminology,
leaves production V1 intact and never executes a device command.

## Not yet implemented

1. More verified MCP source adapters; never infer naive native-log timezones.
2. Measured hypothesis usefulness and objective stopping policies beyond
   initial round/read limits.
3. Trustworthy checks for model-authored cross-source causal explanations
   beyond verified timestamp relationships and atomic observations.
4. Capture actual V1/V2/Claude outputs and latency, blind-grade usefulness
   and correctness, then controlled cutover and retirement of V1 guards.

Do not claim Investigation V2 already outperforms Claude or changes the live
answer until measured shadow replays and cutover gates are passed.
