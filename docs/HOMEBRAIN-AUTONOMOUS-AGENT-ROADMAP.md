# HomeBrainOS — autonomous evidence-first agent roadmap

**v0.18.457 candidate — full returned state denominator:** Deeper replay found six OFF rows in observedEvents but only five in the boundary projection; the omitted unpaired older OFF must remain in the returned sample. Unify both verified projections and deduplicate by state/time without confusing state, command or physical effect. Local original-packet replay: 6 OFF, 2 paired, 4 unmatched, and the separately corrected 4/1/3/0 log request scope. Exact-head CI and installed v0.18.457 acceptance pending. The earlier five-OFF explanation was an adapter/review error, not changed retention.

**v0.18.456 merged — log request/focal evidence scope:** Installed v0.18.455 now passes the missing-shadow integration check. Full answer acceptance remains partial: implicit default past mode was lost from shadow counts, three since-only samples did not establish focal log coverage, and the bounded app query concerned another time. Normalize actual requests once, keep executed counts distinct from bounded and app-specific focal coverage, enforce the same source scope during synthesis/final publication, and reject unrelated historical command selection for focal issuing-app reads. Local private-packet adapter replay yields 4 reads, 1 bounded, 3 unbounded and 0 focal. Merged [PR #1518](https://github.com/ienam-smarthome/HomeBrainOS/pull/1518) after all four required workflows passed on exact head `555a77eef1545dbfb6650d20c3e3babd04f72c76`: Release assurance (**6,781 Python tests**, two nonblocking warnings, container smoke and metadata), Hubitat MCP AI tests, Validate HomeBrain OS and Answer Quality scorecard integrity. Squash merge: `2c44aa359d1e5a4c03c13c28ce4390cee7f412ae`. Installed v0.18.456 acceptance remains pending. Keep model_claims_assessed=false and the frozen cross-domain typed-claim migration direction.

**v0.18.455 merged — real-world source-attested causal routing (7 Nov):**
The first v0.18.453 live latest-OFF question returned a cautiously worded
unknown-cause verdict but no `claim_evidence_shadow` diagnostics. Its
`investigation_coverage` contained only `hypothesisComparisons` (no
`domain=causal_provenance`) and did not run the optional secondary
correlation tool. The new adapter was therefore doubly gated away from
source-real calls. Device history independently contained a unique
source-reported latest OFF and matching target ID; an actual bounded hub
past-log request covered 23:50–00:40 while direct app-specific execution
and sensor history remained unverified. General solution: infer eligible
read-only latest-OFF investigation **only** with the requested target
and host source history, preserve explicit causal-domain handling,
separate "source-history-latest-off" and "host-correlation" provenance,
share one packet for guard routing and non-publishing JSON, and never
promote a general hub log request to complete app-rule execution coverage.
Treat listener notifications as downstream observations, not proof they
could not issue a separate command. No incident device-name routing,
extra MCP/model calls or modifications. All four CI workflows passed on [PR #1514](https://github.com/ienam-smarthome/HomeBrainOS/pull/1514) exact head `33d9d911377cb76c9a8fabcec56c25deaceca132` (6,747 Python tests plus smoke and metadata), merged main `adf9e5ca1ff046ca85c8687d5b4010e9bb8c76fc`. Installed live acceptance still pending. Continue broader model-proposed typed-claim
shadow benchmarking, cross-domain evidence and final-answer usefulness
before any general publisher promotion.


**v0.18.453 merged — claim-evidence adapter and non-publishing shadow checkpoint (7 Nov):**
Do not merge Claude's parallel claim-v2.1 validator even though its 21 condensed
tests pass. Integrate into existing `claim_evidence_contract.py`: focal-time
gating for absent-in-scope, Historical Journal collector-reception typed
quarantine, host-selected all-returned-OFF sample pairing with two-second
Hubitat command matching and no inferred external controller. Build one
`claim_evidence_adapter.py` from successful existing API receipts, not from
model prose. Expose only privacy-limited diagnostics in read-only
`evidence_validation.claim_evidence_shadow`, not a modified answer:
model_claims_assessed=false, verified source and app log coverage, candidate
sensor disposition separately from successful direct sensor windows.
Evidence sample: 6 returned OFF boundaries, 2 paired, 4 unmatched within the
returned records; 4 of 10 selection-stage probed, only 2 native sensor
windows; none of four app-log requests covered the focal 00:30 OFF. This is
not a root-cause finding. Synthetic cross-domain claim semantics passed with [PR #1511](https://github.com/ienam-smarthome/HomeBrainOS/pull/1511), all four exact-head CI checks green at `1600af59001959d37e3e86b79aa7db4931b32efd` (6,738 Python tests plus packaged add-on smoke), squash-merged to main as `755635e8fb08d8f976504a3f55ef145d21a30c6c`. Installed source-real v0.18.453 acceptance remains unverified. Follow with
model-selected claim envelopes, reason-code repair and frozen held-out
cross-domain benchmarking **before** replacing live prose or retiring guards.


**v0.18.452 merged — claim-validated failed-repair publication floor (7 Nov):**
The v0.18.451 installed OFF investigation had the right top-level unknown-cause
verdict but falsely promoted a collector-received FP400 motion=inactive
Historical Journal observation to an original sensor event 19 seconds before
OFF, and claimed empty app logs around focal OFF though the queries checked
different historical times. Both verified native sensor windows returned zero
source events; the model still had 1 failed synthesis repair after 9 rounds
and 19 tool calls. The general repair is not another statement regex: for
read-only causal latest-OFF questions, when repair fails and a uniquely
host-attested focal OFF boundary is available, build a deterministic
**v2-claim-validated factual floor** from source state observations with
typed command receipts; separate sensor-source clocks from collector
reception and independently check app-log requested windows against the
focal time. No action, no extra model/MCP calls, no rewrite on successful
answers or write/confirmation paths. This is a targeted **publication
integrity** increment, not proof that the generic model-to-JSON claim-first
path is complete. [PR #1509](https://github.com/ienam-smarthome/HomeBrainOS/pull/1509)
passed all four CI checks on exact head
`07b40c87af6834e45ebcdbe22daea32d9786f629` (6,727 tests,
container smoke and metadata) and squash-merged as
`6b858876b127340cf41602fcbfe3f5ee92184510`.
Source-real installed v0.18.452 acceptance remains pending.
Next: source-real test newly installed v0.18.452,
freeze cross-domain question/evidence packets, then advance
model-selected typed claims and authoritative coverage into the general
publication path without retaining redundant prose guards.


**Claim-first migration design shipped as shadow-only module (v0.18.451, 7 Nov):** Claude's
uploaded 13-test draft correctly favors typed claims over keyword/prose patching,
but its initial schema accepted empty read scope, unverified command clocks,
listener event intervals and a model-authorized historical context bypass. The
actual v1 ledger uses `state-report`, `issued-command`,
`reported_switch_off`, `issued_on` and no event_key. The generic v2 shadow
module normalizes only verified v1 classes, rejects unsupported/undated source
claims, keeps `command-issuer` distinct from unknown upstream cause, requires
real checked zero-result windows and trusted focal/context membership, and
exposes privacy-safe offline claim verdict counts. It is NOT live publication
or model-selected evidence planning. [PR #1506](https://github.com/ienam-smarthome/HomeBrainOS/pull/1506) shipped the canonical `claim_evidence_contract.py` after all four CI workflows were green at head `c0f015ea2aeb55fd4ec1913fa01e915710269bbd` (6,720 tests), merged as `900243183915d98510a8b9f11fa51dd30328095d`. No real-install first-answer quality score has been measured. Next sequence: (1) confirm installed
v0.18.450/451 held-out acceptance, (2) bind verified native receipts and
trusted event keys to shadow envelopes without new MCP reads, (3) freeze
cross-domain evidence packets and measure factual support / useful first
answers / downgrade rate, (4) only then graduate claim-first publication
with deterministic supported-fact fallback and gradually retire overlapping
prose guards. Preserve source-role, source completeness, privacy, read/write
and confirmation boundaries throughout.


**v0.18.450 source-real acceptance correction candidate:** Installed v0.18.449
held-out natural-language OFF investigation made source queries and reconstructed
the right recorded interval, but the final response inferred external origin
from a reporting bridge, overclaimed command absence despite bounded pages,
misdescribed the exact `motion=inactive` value, and included a controller
warning from a different historical interval. Seven model rounds and failed
synthesis repair prove CI-only improvement is insufficient. General correction:
typed-source interpretation at final publication; source-bound negative claims;
strict focal clock for controller statements and independently corroborated
focal sensor attribute/value. Preserve the verified ON command and the unresolved
OFF decision. CI and post-install first-answer uplift remain pending; do not
create per-device incident templates or lift read/write safety limits.


**v0.18.449 merged — source-real v0.18.448 acceptance failed:** A held-out
read-only OFF investigation returned plausible timestamps and no repetitive
paragraphs, but promoted the reporting bridge to an unproven external cause,
made an unqualified no-Hubitat-instruction claim despite bounded receipts,
misstated inactive motion as generic activity and attached an older listener
to the focal event. The complete Technical JSON also reported a failed
synthesis repair. Merged correction: focal direction and event-bound
listener selection, read-only final publication proof checks and exact sensor
value instructions. [PR #1503](https://github.com/ienam-smarthome/HomeBrainOS/pull/1503)
passed all four required CI workflows on tested head
`dcf50f86381f959c9cde8eda5287f1da27d08a34` and squash-merged as
`5ff4c1127b54a85afc7b5c53386dd4e8e97d0980`.
Measured installed live uplift is still pending. Keep the
model-led evidence-first roadmap, never add per-device source rules, and
retain write/confirmation and resource safeguards.


**Merged general causal-answer presentation guard (v0.18.448, PR #1500, CI green):**
The user's v0.18.447 multi-source Livingroom Light 2 OFF analysis correctly
separated a Matter bridge's state-report role from a downstream SenseCap
listener, but duplicated the same long factual paragraph and reported a
command "captured" without showing the matching event/issuer. The
screenshotted answer does not include full Technical JSON, so do not assert
whether the command was independently verified or whether the unresolved
initiator could have been determined. General solution: exact long-sentence
de-duplication at the final API presentation boundary (after evidence
guards), no modification of writes/confirmations/structured timeline
rows, and generic prompt-level proof contract requiring target-matched
command-off evidence for positive command claims. Keep an audit metric,
CI-gated release complete; source-real held-out tests remain pending. No incident-specific
patch, hard time cutoff or paid-route change.

**Merged generic evidence-language increment (v0.18.447, PR #1498; CI green):**
Never confuse time spanned by selected-attribute observations with the time
spanned by all fetched raw device events. Source metadata must separately
report raw range, matched sample range, event/page counts, requested lookback,
stopping reason and unverified retention. v0.18.446 successfully fetched 204
raw events/5 pages/11 temperature samples on Bedroom 1 TRV, but the generated
answer incorrectly described the 3h36m *temperature sample interval* as the
duration of *all history retrieved*. The source-neutral v0.18.447 change
provides a deterministic narrative and explicit separate spans before model
synthesis; all four required CI checks passed; real-installed verification remains required.

**Held-out next acceptance:** Read-only investigation of most recent
Livingroom Light 2 OFF event: independently read targeted event history,
possible command-issued provenance and relevant installed app logs/settings.
Classify reported OFF transition, direct command evidence, automation trigger
and inferred cause separately; do not fabricate a definitive issuer/cause or
change devices. This live MCP test must be executed from HomeBrain Ask by the
user, not through GitHub repository editing.

**Status:** Phase 1 v0.18.443 and Phase 2 source-neutral arithmetic core
v0.18.444 merged. v0.18.445 merged through PR #1494 after four green CI checks, introducing progress-aware read-only request
timing without a fixed 180-second *total* deadline. v0.18.446 merged through
PR #1496 with four CI checks green, adding hub-local history display labels and
read-only continuation of capped device-event pages. Source-real humidity and
held-out TRV responses were reviewed on the installed v0.18.445 add-on, but
first-attempt provenance and retained history completeness are not verified.
The Phase 2 standalone temporal operator is **not yet integrated** with live
source-qualified arithmetic; v0.18.446 paging and timezone were exercised successfully on installed add-on
with a held-out TRV response; v0.18.447 separate-span answer wording still
awaits installed validation. Do not claim general-question mastery
until first-attempt, source-real tests prove it. This plan supplements
the permanent [Answer Quality Charter](ANSWER-QUALITY-CHARTER.md), whose
correctness/safety targets remain in force.

## Why the design is changing

The user should not have to train HomeBrain question by question.
In the read-only 6 Nov 2026 bathroom-threshold test, Claude reported a
last observed humidity value above 70% at 14:25 (74%) and first later value
below 60% at 18:26 (59%), yielding **4h 1m** between recorded samples.
Those historical figures are **Claude-reported, not independently verified
against pasted native MCP source rows**. HomeBrainOS v0.18.441 identified
Bathroom Meter ID 7851 via its resolver and performed six tool calls,
but all were identity/current-device/attribute discovery. It made zero
`hub_list_device_events`/`homebrain_device_history` reads; seven model
rounds then returned a truthful-but-unhelpful `device_history` missing
warning. The user requested a general solution for new unknown questions.

**Underlying generic failure:** The AI discovered a target but did not
execute the source needed for the user's original calculation. In the
repository, semantic planning was off by default. Independently, the
model-directed read budget blocked after 8/12/18 calls or 3/5/7 read
rounds by profile; some investigation types were further capped at 3 or
6 orchestration rounds, and the source checkpoint budget ended after
three offers even with fresh evidence. A fuzzy gateway discovery cap of
two could hide verified additional *exact* operations. An evidence-coverage
warning alone does not fulfill a missing evidence requirement.

## Standing architecture

1. **One model-led task and evidence planner.** It identifies the objective,
   needed source classes, expected verification checks and candidate
   read-only operations. It may propose only narrow, schema-known source
   requests. Planning is not evidence, permission or a fact.
2. **One host-enforced tool executor.** The installed MCP catalog, source
   contract, exact device resolver and effect classifier decide what is
   actually executable. Read-only auto-reads may be performed for a
   validated model-proposed request; no inferred write authority.
3. **Iterative source-aware evaluation.** After actual tool results, compare
   the answer obligations with independently returned, target-qualified
   evidence. If material evidence is missing, discover alternatives or
   continue a bounded read. If no new source/coverage frontier exists,
   stop with a specific limitation instead of cyclic retries.
4. **One grounded answer synthesis.** Preserve concrete timestamps,
   reported readings, calculations, source IDs, window/sample coverage and
   measured uncertainty. Do not invent causes or confuse zero returned rows
   with absence of historical events.
5. **Repeatable automated offline evaluation.** Record privacy-safe
   traces/outcomes. Continuously test unfamiliar held-out questions and
   safety regressions without requiring the user to reproduce each failure.
   Traces/evaluation are opt-in and never imply unattended background work.

### Phase 1 — model-planned read evidence and remove artificial soft ceilings

**Candidate v0.18.443:**
- Enable the existing general semantic task planner by default for
  non-conversational **read-only** tasks; it does not replace the native
  tool schema, source identity or user mutation permission.
- Extend its schema with optional `readRequests` for the established
  `homebrain_device_history` read-only adapter, including a model-proposed
  user-style device name, attribute and server-compatible time window/limit.
  Validate values; no numeric device ID or invented MCP operation accepted.
  Use the existing source resolver and read-only executor to fetch real
  evidence and feed the returned rows into the same model conversation.
  Works across temperature, humidity, contact, switching and other
  attribute histories; no bathroom-specific condition is encoded.
- Allow model planning for temporal `read` questions as well as causal
  `investigate` questions. History is required for last/first transition
  and elapsed-time questions; a current state inventory cannot substitute.
- In autonomous read mode remove the independent 8/12/18-call ceilings,
  3/5/7 model-read-round cutoffs, 3/6 investigation shortcuts and fixed
  three-checkpoint cap. A new checkpoint still requires a **new successful
  evidence scope**; exact duplicate calls and unavailable sources do
  not renew a source frontier. The normal operational request deadline,
  per-read timeouts, configurable outer tool-round ceiling and resource
  budget remain safeguards against runaway execution.
- Exact live-MCP operation discovery no longer drops a verified third
  gateway merely because a fuzzy top-two rule fired. The unrelated fuzzy
  hit cap remains a relevance safeguard. Installed read-view capacity
  follows the configured schema window without an extra hardcoded 32.
- Keep an opt-out configuration switch to restore the previous planner
  and read budgets if live behaviour regresses.

**Acceptance:** all synthetic repository tests and mandatory CI green;
then a source-real read-only replay of the humidity threshold task
with the same model/provider/settings and complete Technical JSON.
Verify actual device history was read before reporting a calculation,
that the threshold comparisons are strict (>70 and <60), and that
timestamps/coverage support the reported observed-sample duration.
No truth claim from the Claude screenshot alone. Repeat with at least
one held-out different device attribute and one missing/ambiguous source.
Do not publish first-answer or latency gains without matched evaluation.

**Existing-installation activation:** An upgraded Home Assistant add-on may retain its previous option values rather than adopt the new defaults. The v0.18.443 live test must check that `general_task_engine_enabled` is set to true and that `unified_mcp_max_tool_rounds` reflects the intended read-only emergency ceiling; if saved as false/9, change only these options in the add-on Configuration and restart through ordinary add-on management. The global investigation deadline, confirmation controls and tool effects must remain intact. No installation change is made by this PR.

### v0.18.446 — source-qualified history timestamps and page coverage

**Merged in v0.18.446; installed behaviour not yet verified:** Model-planned read-only device
history now requests authoritative hub timezone, preserves raw timestamps,
and adds local GMT/BST display labels only when the IANA zone is verified.
When the newest 50 mixed device events do not reach the requested lookback,
read-only native until bookmarks extend the window until the boundary or an
explicit coverage limitation. Host bounds protect memory/Hub payloads.
Source count describes fetched rows, sample bounds refer only to returned
observations, and equal samples cannot prove physical constancy between
events. This is generic across devices and event attributes. The upstream
bookmark contract and actual source coverage still need one post-upgrade
read-only Technical JSON test; no Hubitat/HA/router changes.

### Phase 2 — generic evidence obligations and temporal analytics

**First isolated increment (not deployed):** `rootfs/app/observed_time_series.py`
computes a first/last matching recorded observation followed by the first
strictly later matching observation. It supports generic numeric operators,
UTC-offset timestamps, unsorted samples and deterministic observed elapsed
seconds; rejects unparseable values and never marks provenance or complete
history verified. Offline regression cases cover strict >70/<60, DST, no later
reading, equal timestamps, invalid fields and alternate device-independent
operators. This is a **pure calculation foundation** only: the host still
needs verified source identity, event normalization, pagination/retention
tracking, a structured question-to-proof contract and orchestration wiring.
Do not present results from this module as live evidence, source-complete
history or a real physical threshold-crossing time. The original v0.18.443
source-real acceptance gate remains required before claiming any improvement.


- Replace source-class-only checks with a structured **question-to-proof
  contract**: requested facts, target identity, source read, time scope,
  temporal comparison, calculation, evidence coverage and unknowns.
  This is a host verifier, not a room/keyword-specific answer rule.
- Build reusable numeric time-series and discrete-event operators:
  strict threshold crossings, first/last after a marker, change-point,
  duration between *observed* samples, aggregation, multi-device joins.
- Explicitly distinguish exact arithmetic on observed timestamps from
  the unknown real crossing time. Add bounded pagination/continuation
  when native history supports it; prove retention before concluding
  none was recorded. If the returned source can never answer, stop
  promptly with specific retrieval/retention limitations.
- Prioritise source completeness and answer quality over reducing
  the number of tool rounds.

### Phase 3 — model-agnostic reasoning evaluation and fallback

- Compare the same frozen history/source packet under the existing
  free Gemma cloud route and other legitimately available models.
  Keep default free/local policy; require explicit user permission
  for paid provider escalation; never silently spend credits.
- Measure planning precision, source-read recall, duplicate/failed
  calls, evidence-source identity, calculation error, explanation
  usefulness and hallucinated causality across diverse held-out cases.
- Introduce an independent evidence sufficiency/claim auditor only if
  an evaluated separate pass adds measurable correctness without
  replacing useful verified observations with empty refusals.
- Improve skills/tool-schema summaries based on **aggregate** failures,
  not a growing list of per-device phrase exceptions.

### Phase 4 — release and rollback gates

- Preserve the fixed Answer Quality case manifest; add unseen
  humidity/temperature/power/energy, automation, heating, lighting,
  ambiguous device and source-absent questions.
- Measure ≥80% complete useful first answers, ≥90% grounded factual
  conclusions and **zero unsupported definitive cause claims** in the
  reviewed evaluation set; report denominators, provenance and
  unknown cases. These are targets, not established results.
- Record model rounds/read calls/wall-time without a fixed complex
  investigation latency threshold. Retain a separate routine status/
  control target. Resume/refine Phase 1 only if live evidence improves.

## Limits: remove arbitrary constraints, not safety

**Removed for autonomous read-only evidence collection:** arbitrary soft
read-call counts and short causal/telemetry round/checkpoint ceilings.

**v0.18.445 adaptive request timing:** The fixed 180-second *total* deadline
no longer applies to ordinary read-only investigations. The default
180-second **stall** watchdog resets only when a distinct, actually
successful, read-only tool/argument source scope is recorded. Duplicates,
errors, model prose, stage updates and writes do not earn new time. An
independent configurable 1800-second emergency watchdog protects against
runaway execution. A successful new scope is not necessarily complete
evidence or proof that returned history contains the requested event.
Legacy saved `investigation_deadline_seconds` is ignored on the normal
Ask path; no silent deadline-based quality target remains.

**Retained intentionally:** individual model/MCP timeouts, an independent
emergency watchdog, explicit outer tool-round ceiling (18), tool
context/result sizes, provider quotas, MCP rate/concurrency controls,
no-write/read-only enforcement, verified target identity, write
confirmation, cancellation/disconnect, duplicate/no-progress stopping and
evidence privacy. These are operational safety protections rather than
a fixed three-minute goal for answering complex questions.
Any external proxy/provider timeout still needs source-real verification.

## What was **not** done

No Hubitat/Home Assistant/router or device was changed. No model
fine-tuning, always-on agent, automatic hidden monitoring, unlimited
paid-model routing or live benchmark was performed. Phase 1 is a
finite code change subject to CI and subsequent user-run read-only tests.

## Source of truth and handoff

`AGENTS.md` → `docs/ANSWER-QUALITY-CHARTER.md` →
`docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md` →
`docs/ANSWER-QUALITY-STATUS.md`.

After merge, update the status with tested PR head, green CI and merged
SHA. Next expected live evidence is the original threshold question
plus one held-out novel history task, with full Technical JSON.
