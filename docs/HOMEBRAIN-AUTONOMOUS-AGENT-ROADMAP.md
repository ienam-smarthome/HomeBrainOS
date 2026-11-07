# HomeBrainOS — autonomous evidence-first agent roadmap

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
