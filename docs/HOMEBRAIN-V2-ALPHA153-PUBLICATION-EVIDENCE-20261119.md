# HomeBrainOS V2 alpha.153 — source-grounded answer publication candidate

**19 November 2026. Candidate, not promoted.** This is prospective development
after the privately reviewed, intact alpha152 original ten-case cohort.
Do not edit or replay the alpha152 originals. The alpha152 advisory score was
3/10 useful/complete, 5 partial, 2 failed, and at least one unsupported
definitive explanation. A formal atomic-claim grounding denominator was
not computed; neither CI nor the next capture alone establishes quality.

## Prior source failures and general interventions

1. **Review overwrote the answer (alpha152-09).** The first model draft
   included returned OPEN, CLOSED, oldest and newest event timestamps; the
   second round published review-only prose instead. New
   `review_answer_preservation.py` can preserve the previous user-facing
   candidate only when >=2 *original event source timestamps* occur in the
   draft, all are lost in the revision, no new successful read occurred,
   and the prior draft is not rejected by the historical publication guard.
   Both drafts remain original private trace data. It is not a correctness
   oracle; causal/history publication guards still run afterward. Native
   actions are excluded. Tool-free source review remains optional.

2. **Publication fallback discarded log groupings (alpha152-10).** When
   the model's historical prose is unsafe or incomplete and no supported
   device history is available, source-only fallback can now group up to
   250 returned rows in a single validated native `hub_get_logs(mode=past)`
   receipt by its safely displayed reported `name`. It publishes counts,
   reported `matched`, `count`, and aggregate `total` with an explicitly
   unknown scope. It never copies log message bodies, combines overlapping
   pages, proves retention, fetches more data or initiates a write. Other
   bounded state-event fallbacks no longer imply that command rows were
   returned when none were. Both paths preserve positive evidence even
   though the model's unsupported prose is withheld.

3. **State/event and actor provenance (alpha152-04/06/07).** Additive
   shadow typed facts now label the source roles of inventory/device-stored
   attribute values, device-wide `lastActivity` (not an energy timestamp),
   genuine dated native event rows, recorded command issuers, notified
   listeners, device-reporters, app inventory/config snapshots and native
   past logs. These labels do **not** enforce arbitrary prose claims or
   constitute independent physical/decision evidence. The base skill
   explicitly distinguishes these roles and consistent KB/MB/MiB units.

4. **App-vs-device identity (alpha152-06/08).** A general read-only
   `app_execution` review category is eligible for requests that
   explicitly ask to investigate application/automation execution.
   The existing model-owned review can inspect currently offered
   app inventory/config/log tools; no tool is automatically selected or
   executed, and no new write/approval path exists. A device label search
   cannot establish installed app identity. Zero current inventory matches
   cannot prove historical nonexistence, nor can a nearby device event
   identify an unrelated requested app.

## Changes that are NOT claimed

- No local/cloud model change, no live source availability test,
  no actual hub/device command, no new native approval or bypass.
- No proof that the app will select the correct read, that every unsupported
  causal assertion is detected, or that review retention fixes every draft.
- No completed alpha153 source-real quality, grounding percentage,
  first-answer usefulness, latency gate or promotion status.
- No alpha152 cohort, seal, permission proof or old benchmark is rewritten.

## General tests and prospective protocol

Fixture tests cover: loss of two original event-time anchors with no new
read, preservation of a legitimate revision, rejection of an unsafe old draft,
native WARN source grouping and log privacy, no cross-page count merge,
stored `lastActivity` vs dated energy event, command issuer vs listener,
app identity source categories, app-execution eligibility and approval safety.

Version `2.0.0-alpha.153` uses a completely distinct
`alpha153-prospective-v1` ten-case pack and private
`/data/homebrain-v2-alpha153-acceptance` directory. A real operator must
first use currently installed, exact labels for both an APP and a DEVICE;
if the old target label is absent, select another **currently available**
device with health/measurement history. A test target not found in
current inventory must be classified as target-unavailable, not
treated as proof of any past absence.

After exact-head GitHub CI green, install alpha153, verify the dedicated
MCP token source-reports Read ON / Write OFF, privately seal new questions,
run each first answer ONCE, export ten original JSONs and capture report,
then independently score claim-level factual grounding, source completeness,
causal calibration and usefulness. Promotion requires >=90% backed atomic
claims, >=80% complete useful first answers, zero unsupported definite
causes and zero native write/approval regressions. Read-only permission
must be source-reported; it is not enforcement-tested independently.
All previous alpha151/alpha152 files remain intact. No synthetic success
or scripted fixture counts as source-real quality.
