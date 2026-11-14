# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.18.460**.

**Recoverable source discovery and multi-part history (v0.18.459):** Autonomous history reads recover a rejected attribute by discovering actual events on the same verified device, keeping the mismatch explicit. Plans may request raw discovery instead of assuming switch. Reported heating/idle intervals use source timestamps and remain distinct from configured heat mode or physical boiler proof. The first successful interval no longer ends a multi-part autonomous question before related-device evidence can be read. No provider/paid-route or write-permission change. [Details](CHANGELOG-0.18.459.md).

**Causal claim scope (v0.18.458):** Independently asserted external-origin clauses cannot borrow uncertainty from a separate actor-unknown clause. Unverified candidate lists are presented without unsupported ranking. Log corrections distinguish an executed bounded general focal query from missing app-specific execution evidence, without inventing open-ended or misaligned reads. These checks run at existing synthesis and final read-only publication boundaries; the shadow remains host-evidence-only, with model_claims_assessed=false. [Details](CHANGELOG-0.18.458.md).

**Complete returned OFF sample (v0.18.457):** The adapter now reads both source `observedEvents` and boundary projections, deduplicating state/time witnesses. An unpaired older OFF can be present in raw returned observations but absent from interval boundaries; it must remain in the returned-sample denominator. The v0.18.455 private packet replays as six OFF reports, two matched commands and four unmatched returned records, without inferring external control. [Details](CHANGELOG-0.18.457.md).

**Focal log request coverage (v0.18.456):** Default past-log mode is recognised even when omitted. Diagnostics distinguish executed reads, valid bounded windows, open-ended samples and app-specific focal requests. The synthesis and final read-only answer checks reject unsupported focal log absence, and issuing-app decision reads cannot use an unrelated historical command for an attested latest OFF. No extra model/tool calls or permission changes. [Details](CHANGELOG-0.18.456.md).

**Latest-OFF claim-shadow routing (v0.18.455):** HomeBrain now recognises a read-only latest-OFF causal investigation using the unique targeted device and its authoritative native-derived switch history even when autonomous answer coverage omits the `causal_provenance` domain marker and the optional secondary-correlation tool is not run. The same source-attested packet feeds existing source-role safeguards and a non-publishing Technical JSON `evidence_validation.claim_evidence_shadow` receipt; `focal_source=source-history-latest-off` discloses this fallback. It distinguishes returned command pairings, actual focal past-log windows, and absent direct sensor reads without claiming unknown actors or historical completeness. If source identity is insufficient, it reports an allowlisted shadow status, not invented certainty. No new MCP/model reads or device writes. [Details](CHANGELOG-0.18.455.md).

**Memory + CPU diagnostic graphs (v0.18.454):** Combined two-axis memory
and five-minute CPU load-equivalent overlay, optional separate aligned
panels, dotted inspection guides, taller detailed charts, and observed
min/max indicators. Read-only browser presentation; no probe or hub
behaviour changed. [Release notes](CHANGELOG-0.18.454.md).

**Claim-evidence adapter (v0.18.453):** The existing typed-claim contract now has a **read-only shadow sidecar** in Technical JSON, based only on a uniquely verified focal event, successful native source receipts, and actual requested log windows. It computes source-limited OFF-to-Hubitat-command pairing across the full returned sample, separates collector-received Historical Journal observations from native sensor event clocks, and distinguishes sensors marked `probed` from verified direct history reads. Look for `evidence_validation.claim_evidence_shadow` (with `shadow_only=true`, `model_claims_assessed=false`); this is diagnostic provenance, not model truth scoring. No change to user-facing answer, provider routing, command permissions or the v0.18.452 failed-repair floor. See [v0.18.453 notes](CHANGELOG-0.18.453.md).

**Claim-validated failed-repair floor (v0.18.452):** A failed causal OFF synthesis repair now falls back to a concise deterministic response **only** when a unique trusted OFF boundary and source-reported switch history exist. It reuses the generic v2 typed-claim validator, reports bounded commands without proving global absence, does not promote collector reception to original sensor timing, and checks whether returned app logs actually overlap the focal time. The same original draft is never published on this fallback path. Successful model answers, writes, confirmations and other investigation domains remain unchanged; no extra MCP/AI requests are added. Runtime note: the v2 claim schema remains predominantly shadow-only; only host-built focal state/interval claims support this tightly gated safety fallback. [Details](CHANGELOG-0.18.452.md).

**Generic claim-v2 evidence shadow (v0.18.451):** A new isolated claim-first library translates existing `causal-witness-ledger.v1` source roles and normalizes state/command classes, requires trusted focal scope, explicitly validated source clocks, true ON→OFF interval pairs, source-matched command issuers, finite same-unit calculations and verified zero-result native history windows. It exposes privacy-limited shadow diagnostics for offline paired evaluation, **not** live answer rewriting or general model-selected claims. The existing output path, prior source-role guards, MCP read budget, write confirmation, paid routing and installed live acceptance are unchanged. [Release notes](CHANGELOG-0.18.451.md).

**Source-bound final causal verdict (v0.18.450):** The publication guard now rejects source-report-to-external-control inferences and unqualified "no Hubitat command was issued" wording when only bounded command receipts exist. A controller correction cannot import an older interval into a new focal OFF question. Verified focal sensor reports retain their exact `motion=inactive` or other recorded state instead of ambiguous "activity". Synthesiser and API serialization use the same sensor-value guard with real-source agreement requirements and Technical JSON correction flags. No device writes, extra MCP reads, changed provider selection or watchdog limits. [Release notes](CHANGELOG-0.18.450.md).

**Focal-event causal proof boundary (v0.18.449):** The final read-only API response now rechecks unsupported external-origin and command-absence claims even when model synthesis repair fails. The focal event uses the recorded ON/OFF direction rather than inventing ON, and listener claims must match the requested event instead of borrowing an app from another historical boundary. Model guidance requires exact sensor values rather than equating inactive with activity. Confirmation/write outputs remain exempt; read permissions, provider routing and watchdogs are unchanged. [Release notes](CHANGELOG-0.18.449.md).

**Evidence-first causal answer hygiene (v0.18.448):** After all factual evidence guards, the API removes repeated *verbatim long prose sentences* within the same answer section, while preserving timelines, distinct timestamps, lists, tables, code, commands and new conclusions. Write/confirmation messages remain untouched. A transparent Technical JSON counter reports removed repeats. Model guidance explicitly separates command-issued records, downstream listeners and bridge-reported state changes; only typed matching command evidence can support a positive command-record claim. This is a general quality safeguard, not a Livingroom Light 2 special case. No new tool reads, writes, paid routing or changes to investigation watchdogs. [Release notes](CHANGELOG-0.18.448.md).



**History coverage wording (v0.18.447):** Distinguishes the time span of fetched raw device events from the span between matching attribute observations. A host-generated source coverage explanation reports counts, page count, measured spans and completeness limits. Zero or one timestamped sample has no measurable interval. This corrects misleading claims such as 'only three hours of history retrieved' when many older raw events were actually fetched. It makes no additional Hubitat reads or mutations. [Release notes](CHANGELOG-0.18.447.md).


**Source-qualified history and hub-local clocks (v0.18.446):** Model-planned
read-only device-history requests resolve the hub IANA timezone to label
recorded samples (for Europe/London: GMT in winter, BST in summer). When the
newest 50 mixed events do not reach the requested lookback boundary, HomeBrain
follows read-only `until` bookmarks within a finite source-row safety budget.
The result now distinguishes fetched source rows, observed attribute samples,
page/boundary reach and independent source integrity. Equal samples do not
establish a constant physical reading between observations. Failed timezone
or bookmark reads are disclosed, not guessed. No device or paid route changes.
[Release notes](CHANGELOG-0.18.446.md).

**Adaptive investigation timing (v0.18.445):** Read-only investigations
no longer have the fixed 180-second *total* deadline. Distinct successful
read scopes renew a configurable 180-second **idle** watchdog; repeated
reads, errors, AI chatter and writes never extend it. An independent
1800-second emergency watchdog plus cancellation, per-tool timeouts,
round ceilings and write confirmations remain. Legacy saved
`investigation_deadline_seconds: 180` is ignored by the normal Ask route.
[Release notes](CHANGELOG-0.18.445.md).

**Phase 2 observed time-series core (v0.18.444):** Adds a tested pure
operator for calculations between recorded numeric readings. This is not
yet integrated into live MCP orchestration and does not change the model's
production answer flow. Source identity, history completeness and exact
threshold crossing remain unverified without independent receipts.
[Release notes](CHANGELOG-0.18.444.md).

**Upgrade note:** Home Assistant may preserve previous add-on option values. After upgrading, check `general_task_engine_enabled: true` and `unified_mcp_max_tool_rounds: 18` in the add-on Configuration; a saved `false`/`9` overrides the new packaged defaults. Do not modify `investigation_deadline_seconds`, write confirmations, provider quotas or per-tool timeouts to activate this feature.

**Autonomous evidence-first planning, Phase 1 (v0.18.443):**
The model can now plan the evidence needed for unfamiliar read-only
questions and propose typed source reads using the installed
`homebrain_device_history` adapter. The host validates source identity,
read-only tool effects, argument schema and returned evidence; the model
may then reason over actual timestamped observations rather than stopping
after device discovery. Autonomous read investigations no longer terminate
solely because short profile-specific call, round or checkpoint soft ceilings
are reached. The configurable operational deadline, write confirmations,
read-permission restrictions and resource protections remain intact.
**This is Phase 1 only**, not proof of universal first-answer accuracy.
[Autonomous roadmap](../docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md) ·
[Release notes](CHANGELOG-0.18.443.md).

**Source-scoped native past-log reporting (v0.18.442):**
Each successful historical-log page is now attributed to its own query
mode/window rather than reusing global bounded-page counts across separate
reads. An explicit unbounded `past` recent sample no longer inherits the
zero matches from a separate date-bounded request whose omitted mode defaults
to `past`. When a recent sample was already read, recommended next checks
focus on actual oldest/latest retained source times and timezone instead of
repeating the same read. Both normal Ask and dedicated incident Technical JSON
retain source-scoped page observations with no private message content.
[Release notes](CHANGELOG-0.18.442.md).

**General historical-loss claim coverage (v0.18.441):**
The shared ordinary Ask publication guard now recognises unsupported,
unqualified assertions such as "a log purge occurred" or "the diagnostic
buffer has been cleared" even when the model omits an explicit reboot
causal connector. The fix preserves independently verified source rows,
recent and bounded past-log results, and typed system/location events in
chronological order. Tentative/unverified hypotheses remain permitted;
full log retention, a purge mechanism and the original memory consumer
remain unverified. The guard adds no MCP calls or write actions.
[Release notes](CHANGELOG-0.18.441.md).

**Evidence-based historical-retention explanations (v0.18.440):**
Ordinary Ask now withholds an unsupported *cause of missing historic
messages*, not only unsupported device/reboot causes. A zero-match
past-log page and a successful recent sample cannot establish that
reboot/firmware reset purged the old messages. The guarded report
preserves independently typed Hubitat system events in time order,
a distinct sunrise/sunset location event without implying reboot
causality, actual recent native past-page counts and the bounded
zero-match result. It directs read-only follow-up to earliest/oldest
retained source times and available archives rather than inventing
retention mechanics. The generic evidence-gap footer uses actual
paragraph breaks instead of literal escaped newlines. No new
MCP/model reads, polling, writes or operational deadline change.
[Release notes](CHANGELOG-0.18.440.md).

**Empty historic past-log page coverage (v0.18.439):**
A successful past-log query with a native bounded page reporting zero matches
now produces an explicit no-returned-message result rather than generic
instructions to inspect messages that were never returned. Separately retain
the upstream pre-time-filter raw source row total, per-page match counts and
time-parse diagnostic counters (all numbers, never private text). A large
raw source-row total does not establish that the requested old records remain.
Next checks prioritise source-time/retention verification and local journal
coverage, not speculative app culprits. Synthesis still preserves verified
critical-memory reboot events independently from the unknown original
consumer; no new hub reads or latency targets.
[Release notes](CHANGELOG-0.18.439.md).

**Typed historical past-log row receipts (v0.18.438):**
Successful read-only hub_get_logs(mode="past") queries now retain
bounded, privacy-safe provenance about actual returned messages: count
of timestamped rows, app/device source markers (numeric IDs only),
page truncation and continuation status. Native Hubitat past-log times are
hub-local; the output does not invent UTC conversions or publish raw app
message text. The ordinary Ask causal-report guard, explicit incident
Technical JSON and current-turn synthesis ledger can distinguish a
successful empty/summary-only query from one that returned typed historical
rows, without treating page coverage as complete retention or a causal verdict.
No additional MCP reads, privileged actions or monitoring are introduced.
[Release notes](CHANGELOG-0.18.438.md).

**Read-only diagnostic chart readability (v0.18.437):**
The synchronized hub timeline and the resource-history chart now use denser
readable axis ticks, rounded y-axis intervals and matching horizontal/vertical
gridlines. Time label density adapts to the rendered width and displayed date
range. Both charts continue to plot only actual external or native readings,
preserve gaps, confirmed startups, provenance and independent CPU/memory scales.
No recorder cadence, Hubitat read, automation or device operation has changed.
[Release notes](CHANGELOG-0.18.437.md).


**Historical-log mode contract and chronological incident reporting (v0.18.436):**
HomeBrain checks the upstream MCP log-mode/time-filter contract before executing
model-selected historical reads. Only past/hubEvents/locationEvents tabs accept
since/until; apps/devices are current runtime statistics, hubActions is a hub
actions table. Invalid combinations are rejected without making an MCP call,
with read-only guidance to use past with an optional appId/deviceId for
historical messages. Causal log-window normalization no longer attaches dates
to runtime/operation tabs. Safe typed Hub Events are rendered chronologically,
and the explicit lowMemory/reboot warning followed by startup is distinguished
from an unverified originating memory consumer. Technical coverage separates
app runtime stats from bounded app-specific past logs. No extra polling or writes.
[Release notes](CHANGELOG-0.18.436.md).

**Shared Answer Quality and log-query receipt coverage (v0.18.435):**
When ordinary Ask withholds an unsupported causal claim, the response keeps
source-qualified, authenticated time-bounded Hubitat system-event facts if
typed rows are actually available. It also reports counts of successful and
failed requests for `hubEvents`, `past`, `apps` and generic bounded logs
without pretending that a successful mode request proves app-message content
or complete historical coverage. The dedicated incident endpoint exposes the
same mode-specific receipt metadata. No raw private log messages are placed
in the added response fields. These changes do not automatically retrieve
missing historic messages or identify the original memory consumer.
[Release notes](CHANGELOG-0.18.435.md).

**Actionable, evidence-qualified incident AI reports (v0.18.434):**
When the AI supplies an unsupported definitive cause, HomeBrain continues
to withhold the model draft, but its host-authored report now includes
tailored **Read-only next checks** based on the verified restart trigger,
historical app-log access, external probe coverage and known Journal gaps.
A failed `mode=apps` historical-log query is distinguished from any
later successful, bounded generic log query. The latter is not silently
treated as proof that app-specific messages were reviewed. Technical details
also expose these distinct source receipt states. No extra Hubitat requests,
automatic remediation or paid-model escalation are introduced.
HomeBrain continues to treat the reboot trigger and memory-consuming culprit
as separate questions. [Release notes](CHANGELOG-0.18.434.md).

**Verified restart triggers vs unresolved root causes (v0.18.433):**
The on-demand incident AI endpoint now reads the typed, successful, source-backed
Hubitat Hub Events receipts independently of the language model. A literal
`lowMemory` event stating critically low memory and rebooting, followed by
a time-bounded `systemStart`, supports the **reported low-memory reboot trigger**
but does not identify which app, driver or process consumed memory. A recorded
`update` followed by `systemStart` establishes an update-associated startup
sequence, not that firmware caused a preceding externally measured memory dip.
Both conclusions are reported alongside **underlying memory cause: UNVERIFIED**.
If AI overstates causality, the unsafe draft stays withheld while the verified
Hub Events timeline remains visible. The response includes typed trigger
evidence and source-coverage information in Technical details.
The existing incident-AI route remains read-only and on-demand.
[Release notes](CHANGELOG-0.18.433.md).

**Evidence-bound AI investigations (v0.18.432):** Hub Diagnostics now offers
**AI investigate** on each timeline event, **AI investigate selected time**,
and **Investigate with HomeBrain AI** in the bounded incident review.
The explicit request passes a source-labelled local SQLite evidence capsule
to the existing HomeBrain read-only MCP reasoning loop. The model may check
Hub Events, app logs and native performance using ordinary read-only tools.
The selected Free/Ollama, Paid or configured Claude tier is respected.
No scheduled AI monitoring, automatic model escalation, Hubitat writes,
new collectors or extra polling are introduced.

**Answer Quality correction:** A model may not publish a definitive root
cause if its typed hypothesis-discriminator evidence remains unverified.
Unresolved ordinary Ask responses and the new incident AI path withhold
overconfident causal drafts rather than incorrectly certifying firmware
or memory as the cause. Historical timestamps prove sequence, not cause.
[Release notes](CHANGELOG-0.18.432.md).

**Incident evidence drill-down (v0.18.431):** Click **Investigate** on any timeline
event or select a plotted time and choose **Investigate selected time**. The
explicitly requested ±5/15/30/60-minute read-only review combines actual
external recorder samples, native five-minute source-labelled CPU/Java values,
confirmed Hubitat systemStart markers and recorded external probe failures.
A separate Historical Journal projection shows retained device-event previews,
app-log receipt counts grouped by app ID **without log message bodies**, and
known collection gaps. The review is bounded, labels stream/retention limits,
supports copying an evidence-first report and opening a read-only source JSON.
No real-time Hubitat reads, actions or extra polling. A timestamp sequence never
proves the cause of a reboot. [Release notes](CHANGELOG-0.18.431.md).

**Unified Hub Diagnostics incident timeline (v0.18.430):** An expandable two-track
read-only timeline aligns real external free-OS-memory readings and distinct native
five-minute CPU-load equivalents, with shaded external connectivity-loss intervals
and orange confirmed systemStart markers. Hover/touch/keyboard inspection reports
source timestamps and does not interpolate missing readings. Source JSON and a
Historical Journal shortcut help investigate nearby observations without claiming
a restart cause. The new `/api/hub-diagnostics/timeline` endpoint reads the
existing SQLite recorder only; it does not request extra Hubitat telemetry.
[Release notes](CHANGELOG-0.18.430.md).

**Native contract claim calibration (v0.18.427):** Read-only runbook reviews now downgrade unverified table-level schema claims, withhold contract-shaped JSON projections, redact guide acknowledgement values, and report `readinessForMutation=false` in structured coverage. Existing installed-rule reads and authorisation protections are unchanged. [Release notes](CHANGELOG-0.18.427.md).

**Retirement of native Rule Machine inventory fast path (v0.18.426):** The installed 0.18.425 runbook review still returned a model-free parent/name listing rather than verifying the requested authoring contract, with a misleading Success classification. Remove its host-level early return, special completion/Success classification, and now-unused module/tests. Keep ordinary `hub_list_apps`, `hub_list_rules`, native read, parent preflight, and dated-trigger discovery tools available under their own evidence-scoped workflows. Native contract reviews remain read-only and cannot be satisfied by parent/name inventory. [Release notes](CHANGELOG-0.18.426.md).

**Native contract review routing (v0.18.425):** Installed 0.18.424 misclassified a read-only native dated-trigger runbook review as existing-rule verification and spent 11 model rounds/15 tool calls/78.7 seconds on unrelated app/source lookups. A source-scope-aware native authoring contract predicate now takes precedence over advisory model labels, without enabling writes or changing explicit installed-rule audits. Contract reviews require the guide and typed authoring schema, not unspecified device/controller action trees. The agent is instructed to avoid unrelated Groovy, logs and app reads; topic exclusions no longer activate motion/lockout guidance. [Release notes](CHANGELOG-0.18.425.md).

**Native proposal publication guard (v0.18.424):** A read-only runbook review in installed 0.18.423 invented HH:mm / MM/dd/yyyy date formats, an unsupported native addTrigger/addAction create payload, and declared READY despite incomplete schema evidence. It also appended an unrelated hard-coded overnight-lighting/motion caveat, and implied targeted app/device page reads when only inventory/guide calls occurred. The existing shared rule-design guard now withholds unverified executable native write JSON, replaces unverified upstream schema/readiness claims, differentiates targeted configuration reads, and scopes the feasibility appendix to the actual question. No native writer privileges or MCP calls are added. [Release notes](CHANGELOG-0.18.424.md).

**Preflight source-coverage accuracy (v0.18.420):** The installed 0.18.419 preflight read both guides and verified parent 169, but a request to report `nativeGuideContract` and its evidence gaps did not trigger the contract check. Technical JSON misleadingly called a readable guide `guide_unavailable_or_oversized`, and completion labelled the requested proof complete. The existing read-only guide response is now always inspected at no extra MCP cost; an explicit contract or guide-gap reporting objective is graded as a required source check, while ordinary version/backup/guide checks remain simple. An omitted date declaration is marked unverified, not unsupported; no change to native writer permissions or rule/device state. [Release notes](CHANGELOG-0.18.420.md).

**Non-rendering native parent preflight (v0.18.419):** Installed v0.18.418 verified parent app 169 but issued `hub_get_app_config(includeSettings=false)`, which upstream documents as rendering an app page and executing its page code. The strict read-only preflight now relies on `hub_list_apps` instance/type records plus `hub_get_app_config(summary=true)` (the non-rendering installed-app JSON identity source), and independently requires at least one distinct returned child row with `parentId` matching the root. Missing child evidence stays unverified. This eliminates one page-rendering source call without changing writer permissions, guides or backups. [Release notes](CHANGELOG-0.18.419.md).

**Read-only native parent/date-contract preflight (v0.18.418):** An installed 0.18.417 preflight confirmed MCP Rule Server 5.1.6 and two readable tool guides but did not inspect parent app 169 or explain the missing atDate# declaration. When explicitly requested, the preflight now checks the exact parent ID against Hubitat installed-app and built-in type records plus targeted summary and child-role metadata. It emits only safe typed identity/guide booleans, field names and diagnostic codes; never raw guides, passwords or unrelated app names. Missing or conflicting evidence remains unverified. Basic preflights retain their original three source calls; no authoring permission is enabled. [Release notes](CHANGELOG-0.18.418.md).

**Exact-ID dated-trigger paraphrase routing (v0.18.417):** The installed v0.18.416 live request for existing native Rule Machine dated-trigger fields incorrectly fell into the generic existing-rule agent, made two unsuccessful full reads and never attempted bounded pagination. Accept natural `dated-trigger fields` / `native Rule Machine rules` wording in the existing read-only specialist matcher, preserving explicit-ID, read-only and no-prospective-creation guards. The no-model paginated source path is now reachable for this wording; its installed behavior remains unverified pending acceptance. No rule/device changes or native writing permissions. [Release notes](CHANGELOG-0.18.417.md).

**Native dated-trigger readback diagnostics + bounded pagination (v0.18.416):** Installed v0.18.415 routing passed but exact-ID read-only retry of native Rule Machine 2967 and 3985 still returned two `readVerified=false` results. Prior code collapsed upstream errors, oversized documents and parser failures into identical receipts. A narrowly scoped fallback now uses the upstream documented `hub_set_rule(operation=read)` *single-section cursor paging* for **only explicitly requested, native-inventory-confirmed rule IDs** when their unpaged document fails. Each read is independently classified non-mutating; pagination is bounded and checks rule ID, section shape, offset, page total, revision and cursor progression. Only allowlisted stored date/time evidence and non-sensitive failure codes are published. A retry never authorises rule creation, scheduled execution, forms, device control or general inventory absence claims. This may recover large native documents, but user-hub success is unverified until installed acceptance. [Release notes](CHANGELOG-0.18.416.md).

**Automation-status fast-route correction (v0.18.415):** A v0.18.414 user-run exact-ID retry for the two incomplete existing native Rule Machine dated-trigger reads (2967/3985) incorrectly returned the entire Hubitat automation-status dashboard in ~1s, because the status matcher equated any prompt containing "rules" and the safety instruction "Keep native rule-writing authorisation disabled" with an explicit global status request. The deterministic automation-status inventory is retained **only for genuine broad list/status/count requests**; incidental words in read-only rule investigations can no longer hijack the request. The API selector also explicitly protects existing native dated-trigger discovery from the status route. Regression tests cover the actual full prompt, explicit status queries, advisory ideas and the /api/ask route. No changes to Hubitat rules, device state, native rule writer or permissions. [Release notes](CHANGELOG-0.18.415.md).

**Native dated-trigger exact-ID read retry (v0.18.414):** Four installed v0.18.412/v0.18.413 read-only batches attempted all 42 visible Rule-5.1 native children; 40 document reads verified, two incomplete (IDs 2967 and 3985), no verified enabled date-specific trigger. A narrow, explicitly requested existing-trigger retry can now look up up to four exact positive rule IDs in a freshly returned native child-app inventory before issuing their individual `hub_set_rule(operation=read)` trigger/settings reads. Missing or malformed IDs do not result in arbitrary direct reads, and the prior offset-batch path is unchanged. The response distinguishes targeted read coverage from hub-wide absence, does not reveal unrelated native settings, and never opens forms or changes rules. Read-only date-field evidence is not a Rule Machine authoring contract; writing remains blocked. [Release notes](CHANGELOG-0.18.414.md).

**Native dated-trigger answer publication (v0.18.413):** Installed v0.18.412 ran the correct read-only native date-field scanner (42 visible Rule-5.1 candidates, 12 native reads, one unavailable) and produced source-typed `native_dated_trigger_discovery` coverage, but the earlier `existing_rule_verification` calibrator overwrote its answer with an unrelated action-tree/inactivity-controller template before shared completion. The specialist receipt now has priority at the **earlier** publication boundary, and the generic calibrator refuses to overwrite an existing source-typed dated scan. The scanner additionally reports bounded partial time/date observations (e.g. rule 2710 time 22:30 with date flag value unverified and no stored atDate), labels incomplete native reads honestly, and retains the next offset. No writer gate, read permissions, rule, device or router changes. [Release notes](CHANGELOG-0.18.413.md).

**Read-only existing dated-trigger discovery (v0.18.412):** The installed 0.18.411 test asked to inspect existing Rule Machine `Certain Time (and optional date)` triggers and persisted `time#`, `atTime#`, `date#`, `atDate#`. The model instead selected arbitrary rule 4163, ran a generic action-tree/health audit and published unrelated inactivity-controller limitations after 40.751s/10 Gemma rounds. A narrow host-owned, no-model read path now scans a bounded visible installed Rule-5.1 inventory and requests only `triggers` and `settings` with `hub_set_rule(operation=read)`, which upstream documents as not opening the editor. It projects allowlisted typed date fields, dates and enable flags for an exact existing rule ID; it never inspects unrelated private settings or certifies a complete inventory from a sample. A negative bounded scan shows a continuation offset, not absence. Its own Technical JSON coverage precedes generic existing-rule verification. No rule creation, form opens, configuration writes, or relaxation of native one-time authoring restrictions. [Release notes](CHANGELOG-0.18.412.md).

**Q2 read-only native Rule Machine preflight precedence (v0.18.411):** The 0.18.410 installed readiness request finished source reads (MCP initialize 5.1.5, hub-local backup 2026-11-05 03:02:31 UTC, both native guides), but the generic shared completion misclassified the combined parent mention as an app-class identity query and erased the readiness answer. Specialist typed readiness coverage now wins before unrelated identity assessment. An explicit request to compare initialize with hub_get_info performs one extra read-only check; requested dated atDate# guide evidence and any saved-state readback are separately marked unverified unless actually attested. Core preflight completeness never authorises native one-time rule writing, backup-age validation or date-trigger creation. No new writer permissions, version threshold change, device commands or rule mutations. [Release notes](CHANGELOG-0.18.411.md).

**Q2 built-in app identity proof vs native writer authorization (v0.18.410):** An installed v0.18.409 live read confirmed app 169's exact appTypeId=18 joins Hubitat's built-in Rule Machine catalog type id 18 (system=true/isBuiltIn=true) and app 169 is a root with 42 returned child-app rows. A source-attested numeric built-in type join is positive class evidence, not another missing mapping. A type's built-in identity is now separately recognized from parent-role evidence and independently unverified Rule Machine authoring. The domain answers with positive identity when both source relationships are present; missing/conflicting/partial evidence remains unresolved. No changes to Rule Machine writers, permissions, tool calls or model rounds. [Release notes](CHANGELOG-0.18.410.md).

**Q2 exact-ID app/type inventory correlation (v0.18.409):** A live 0.18.408 read-only test called both `hub_list_apps(scope='instances',nameFilter='Rule Machine')` and `hub_list_apps(scope='types',nameFilter='Rule Machine')` but their published receipts listed only root field names. The app-configuration summary provided name/type/namespace/user without the numeric `appTypeId`. New bounded, allowlisted typed receipts now expose matching filtered instance and type rows, permit a source-reported numeric-ID join, and distinguish reported type-catalog classification from independently certified native parent identity. Missing pages, missing IDs and conflicting IDs remain unresolved; no new MCP calls, model rounds, permissions, rule writers or native class certification. Installed acceptance not yet measured. [Release notes](CHANGELOG-0.18.409.md).

**Q2 source-only native app identity publication (v0.18.408):** Installed 0.18.407 produced target-matched typed metadata in 19.139s/5 Gemma rounds/3 MCP calls but its final prose asserted an unreceipted system flag, claimed 41 child rules when the receipt captured 42 child-app rows, and inferred all children were Rule-5.1. When authoritative native-class binding remains incomplete, this narrow verification objective now publishes a readable summary assembled solely from target-matched typed receipt fields, with explicit returned-page-only child counts and native-class uncertainty. The model still selects sources; no extra MCP/model calls, no rule authoring authority, and no cross-domain incident patch. Live deployment quality/latency remain unmeasured. [Release notes](CHANGELOG-0.18.408.md).

**Q2 native app identity publication and summary receipts (v0.18.407):** A real v0.18.406 follow-up used `hub_get_app_config(summary=true)` returning a flat metadata object without `appTypeId`, bypassing the nested-only receipt projector. Its answer nevertheless declared app 169 a verified native system app even though both native-class and instance-to-type evidence requirements remained unverified. Flat and nested target-scoped metadata now receive separately scoped read-only receipts; missing type IDs remain unverified. Only affirmative, unsupported native-certification language is replaced with a concise source-grounded qualification. No extra tool/model calls or rule-write capability. The pre-update 36.567s/8-round sample is observational; post-update impact is not measured. [Release notes](CHANGELOG-0.18.407.md).

**Q2 typed app-instance metadata receipts (v0.18.406):** The first installed v0.18.405 live Rule Machine parent-identity test correctly used the dedicated `app_class_identity` objective and kept native parent certification unresolved (22.568s, 5 Gemma rounds, 3 read calls). However, its public field-name-only receipts did not independently expose the reported app ID/type, label, namespace, root/system status or child-page count claimed in the answer. A target-ID-matched `hub_get_app_config` read now records only bounded safe source-reported app metadata in a typed receipt; this verifies the observed instance/type fields when supplied but **never** certifies the native built-in class mapping, authorizes creation, or adds model/tool calls. Live post-update acceptance remains unmeasured. [Release notes](CHANGELOG-0.18.406.md).

**Q2 native app-class identity scope (v0.18.405):** Independent verification of an installed app's native parent/type relationship is now a separate read-only investigation objective from verifying a rule's action tree. Generic successful field-name reads cannot prove a native class mapping; the existing-rule publisher no longer replaces identity explanations with unrelated trigger, delay and inactivity-OFF boilerplate. No writer permissions changed. The observed pre-update v0.18.404 identity run was unresolved at 33.825s/7 Gemma rounds; an after-update live run is still required. [Release notes](CHANGELOG-0.18.405.md).

**Q1 telemetry source saturation (v0.18.404):** The installed v0.18.403 MQTT/health read-only test returned an appropriately grounded but slow 42.635s answer (8 free rounds, 13 calls), after redundant source exploration and use of a device ID as an app source ID. A general telemetry stop allows bounded answers once same-target history, scoped logs, and conflicting driver metadata establish a safe provisional status discrepancy, while a typed source-identity guard blocks wrong-namespace Groovy app reads. No new permissions, commands or MCP/model rounds are introduced. Live latency improvement is **not yet measured**. [Source review](../docs/ANSWER-QUALITY-Q1-TELEMETRY-STOP-20261104.md) · [Release notes](CHANGELOG-0.18.404.md).

**Q1 source-qualified telemetry explanations (v0.18.403):** A real 0.18.402 read-only MQTT/health answer overstated physical device failure and unverified watchdog details despite independent evidence of 566.1h versus 45.1h conflicting metadata and recorded MQTT disconnects. A general final source-claim boundary now checks all device-telemetry explanations against typed clock, device identity, positive events and verified driver-method coverage, without extra model rounds or hub reads. Installed real answer quality/latency is **not yet measured**. [Source review](../docs/ANSWER-QUALITY-Q1-TELEMETRY-SOURCE-BOUNDARY-20261104.md) · [Release notes](CHANGELOG-0.18.403.md).

**Q1 aggregate coverage (v0.18.402):** The first registered `Which lights are currently on?` response on v0.18.401 took 4.054s and used a 211-device bulk snapshot, but the Technical JSON did not expose the active-light count or ON/OFF completeness. Read-only light/non-light switch summaries now expose privacy-safe scoped counts of candidate/ON/OFF/unknown state, and a shared final guard qualifies unsupported absolute zero-active claims while preserving complete, reported ON=0 answers. No new MCP calls, model rounds or permissions. Actual post-update speed/accuracy is **not yet measured**. [Source review](../docs/ANSWER-QUALITY-Q1-AGGREGATE-COVERAGE-20261104.md) · [Release notes](CHANGELOG-0.18.402.md).

**Q1 universal typed-source grounding (v0.18.401):** After the first registered hub-health observation on 0.18.400, source evidence showed an unsupported temperature and overbroad global health/freshness claims. A cross-domain field-attestation boundary now checks model-authored status values against the actual source-reported measurements, units, and identity (hub snapshots and individual device/sensor states); missing measurements remain unverified. No new MCP reads, model rounds, or write permissions are added. Live improvement is **not yet measured**. [Source review](../docs/ANSWER-QUALITY-Q1-TYPED-REPORTS-20261104.md) · [Release notes](CHANGELOG-0.18.401.md).

**Q1 current-state comparison scope (v0.18.400):** A user-supplied two-light read-only comparison on 0.18.399 correctly reported saved OFF/level attributes but unnecessarily entered history analysis, took 19.409s (6 model rounds), and reported incomplete history although no history was asked for. The shared objective policy now distinguishes current snapshot comparisons from requested historical or causal comparisons, without changing tool permissions or overwriting natural model synthesis. Post-update real answer and latency are **not yet measured**. [Source review](../docs/ANSWER-QUALITY-Q1-SNAPSHOT-COMPARISON-20261104.md) · [Release notes](CHANGELOG-0.18.400.md).

**Timed Internet preflight optimisation (v0.18.399):** After live v0.18.398 testing verified the driver timer fired on device 6923, HomeBrain now resolves candidate Cudy Block devices with one lightweight, filtered summary inventory instead of the redundant detailed all-device manifest scan. It retains full driver identity, ambiguity and expected-ID guards, existing user confirmation, and post-write deadline verification. A partial summary fails closed. The observed prior confirmation delay was 38.16 s (37.95 s MCP HTTP); new live latency remains **not measured** until an installed comparison. [Release notes](CHANGELOG-0.18.399.md).

**Hub-resident timed Internet control (v0.18.398):** Add a dedicated, approval-required path for delayed blocks on verified Cudy Managed Device instances, using driver-provided commands, ID-scoped MCP writes and deadline read-back. The feature requires the owner to install and validate the separate Groovy driver patch before use; HomeBrain does not upload driver code or create Rule Machine rules. No live timer firing or router enforcement has been measured. [Setup and limitations](../docs/TIMED-INTERNET.md). [Release notes](CHANGELOG-0.18.398.md).

**Native one-time scheduling preflight (v0.18.397):** When MCP initialize is missing, stale or below the required native Rule Machine dated-trigger release, HomeBrain checks the installed MCP server using read-only `hub_get_info.mcpServerVersion`. Older installations return explicit HPM upgrade/reconnect guidance. If the hub version is newer than a cached connection identity, the two sources must agree after reconnect before a dated rule can be queued. Already-supported sessions retain their fast path. No rule, device or router changes are made by this read. [Release notes](CHANGELOG-0.18.397.md).

**Native Rule Machine scalar normalization (v0.18.396):** The named-rule summary now shares the privacy/field projection with the existing native section reader instead of rejecting optional `device_ids=null`. It recognizes only exact typed native boolean strings (`"true"`/`"false"`) and bounded integer numeric strings when interpreting rule Switch and elapsed-wait settings. It remains read-only, source-scoped and fails closed on ambiguous values. The raw native read mode remains available unchanged. [Release notes](CHANGELOG-0.18.396.md).

**Readable native Rule Machine configuration (v0.18.395):** Exact named-rule reads now present verified trigger times, configured switch ON/OFF device IDs, elapsed wait settings and the uncertainty about one-time dates, schedule status and execution in a short natural-language sequence. Editor form internals and privacy-redacted settings remain omitted from the default answer; callers explicitly requesting raw native sections retain the earlier detailed format. Uses the same read-only MCP request, without additional tool or model rounds. [Release notes](CHANGELOG-0.18.395.md).

**Native dated Switch schedule creation (v0.18.394):** On a source-attested Hubitat MCP Rule Server **5.1.6+**, eligible one-time fixed-time or relative-minute switch commands generate an approval-required native Rule Machine dated trigger and single Switch action; unsupported daily and compound temporary-block requests still refuse without writing. Native creation must return a matching persisted document and activated scheduled job/subscription before HomeBrain claims success. No spontaneous Hubitat/HA/router actions. Real live first-run success and device effect remain unmeasured. [Release notes](CHANGELOG-0.18.394.md).

**Exact named Rule Machine reads (v0.18.393):** A request to inspect the stored triggers/actions/settings of one explicitly quoted, named existing Rule Machine rule now has priority over global automation-status inventory routing. The host resolves a unique source-listed rule ID, then calls only the existing safe native `hub_set_rule(operation="read")` path; incomplete/ambiguous reads are stated explicitly. It never writes a rule. This does not yet unblock native timed rule creation. [Release notes](CHANGELOG-0.18.393.md).

**Problem-first automation status (v0.18.392):** Large inventories now render a bounded fault/uncertainty summary instead of hundreds of routine active configuration rows. Paused or disabled settings remain clearly reported but are not counted as evidence of malfunction. Explicit requests to list all automation rules still show the full inventory; Technical JSON continues to return every deduplicated source item. These are source-backed presentation changes, not proof of runtime execution or a completed hardware/automation health check. [Release notes](CHANGELOG-0.18.392.md).

**Q1 initial read-only tool admission (v0.18.391):** For questions with no independently recorded user mutation authority, the model's *initial* function-calling tool list omits write-capable functions even when pre-round fuzzy discovery finds them. This prunes only current declarations (not installed capabilities) and retains original read sources. Later explicit discovery can still expose a mixed-purpose gateway when its read operation is required; the existing atomic write rejection and confirmation guards remain in place. Explicitly authorised creation/control paths retain their normal writer availability. The current live v0.18.390 comparison remained ungraded (15.168s, 7 read receipts, one blocked write attempt); this release's effect on accuracy, first-answer usefulness, actual cloud rounds and latency is **NOT MEASURED** until a new controlled read-only response. [Release notes](CHANGELOG-0.18.391.md).

**Q1 generic read-only recovery (v0.18.390):** After any model-proposed write is atomically blocked in a read-only request, the remaining rounds now receive only actually installed, effect-classified read tools; rejected companion reads are not treated as executed. The read-only view persists across later discovery, so the model can continue verifying requested sources rather than repeatedly proposing an unauthorized action. No new provider round, device permission or deterministic answer template is introduced. The pre-change installed six-check receipt had only two actual reads and 25.9-second latency; installed improvement remains **unmeasured**. [Release notes](CHANGELOG-0.18.390.md).

**HomeBrain vNext consolidated verified source finalization (v0.18.351):** Final answer generation now **coalesces two overlapping read-only app-decision log planners into one source obligation**, prioritizing a precisely source-backed historical command incident when one exists and otherwise using the independently verified issuing-app method-command plan. It performs at most one app-log query per finalization rather than independently entering two planners, while keeping the same app ID, incident time and prior failed-read no-retry constraints. Device log, source configuration, command history and app-log completion now share **one lazily fetched live capability catalog** in the finalization stage, avoiding repeat tool-schema retrieval within that stage. Source effect/schema checks, existing read-only permission gates, model-authored prose and factual limits are unchanged. This is incremental generic orchestration consolidation, **not** a verified <45-second model performance result or wholesale replacement of the existing multi-round planner. [Release notes](CHANGELOG-0.18.351.md).

**HomeBrain verified focal event reconciliation (v0.18.350):** First-run Dehumidifier 1 test revealed a specific **cross-source synthesis failure**: Hubitat had returned an explicit app-issued `command-off` at 18:07:35.001 UTC in a bounded mixed-history read, but model prose said the OFF command was missing after a later filtered `command-on` read. It also described a one-hour-36-minute switch interval as 3.5 hours and treated the first returned 88W power sample as the first-ever physical dehumidifier operation, despite truncated history and earlier readings. This release adds a **domain-neutral, read-only reconciliation of all successful device-ID-scoped native and verified label-scoped event receipts** into a single model-facing evidence packet and compact Technical JSON provenance. It preserves both command directions, reported state boundaries, bounded power samples, clock order, issuer IDs only where source typed them, and the distinction between observed plug ON time and unverified appliance run time. It never assumes missing history implies a command never occurred, does not replace natural model prose, does not invoke extra tools/model rounds, and never changes device permissions. This is an offline-tested factual support improvement, not yet a demonstrated live answer-quality win or complete orchestrator refactor. [Release notes](CHANGELOG-0.18.350.md).

**HomeBrain request-local source-read reuse (v0.18.349):** The first broad (unfiltered) Hubitat location-event read and later deterministic wrapper can return the same bounded source page, costing an unnecessary MCP/model tool read and context. In read-only investigations only, once a positive native location-event receipt covers an equal or larger time window and page size, HomeBrain skips the subsequent same-window unfiltered local projection. Filtered/paginated/location-specific variations, bigger pages, device/sensor histories, application logs, evidence gaps and control operations are never suppressed. The original source events remain available in the model's context; duplicate reuse does **not** imply historical completeness, real-time reachability or verified cause. This is one source-obligation deduplication primitive, not an 11-round planner consolidation or measured speedup. [Release notes](CHANGELOG-0.18.349.md).

**HomeBrain vNext verified alias-bound source completion (v0.18.348):** First live fan-boost investigation could reliably retrieve issued ON/OFF commands and configured scheduling but did NOT read the issuing app's decision logs. Its question described the 'bathroom ventilation fan', while the read-only verified target was labeled 'Fan Boost'. Previously this alias mismatch prevented the generic typed command-source packet and bounded app-log planner from firing; the model then overstated a plausible scheduled cycle as *confirmed*. The shared source contract now permits one source-attested target from a **unique** successful targeted lookup, matching ID-scoped device event history and successful user-phrase device-resolution request. A common device-label token only rejects contradiction; it does not create identity. Conflicting or missing IDs/reads fail closed. The source packet explains why a timed app-issued command + schedule match is strong circumstantial evidence, **not an independently verified scheduler trigger**; sparse humidity history cannot rule out intervening changes. The publication path remains natural/model-authored. No new model round, no change to write controls or permissions. The new app-log read is read-only, single-attempt and subject to live tool admission. This does not claim measurable model accuracy improvement. [Release notes](CHANGELOG-0.18.348.md).

**HomeBrain typed method-command evidence (v0.18.347):** The 2026-11-02 first read-only thermostat investigation showed Hubitat had actually recorded `command-setThermostatMode(off)` from app 2710 at 22:30:02.397 UTC and mode off at 22:30:02.791, yet the source-class checker marked `command_history` missing. This general source-evidence fix recognizes any valid scoped, timestamped `command-<method>` event explicitly typed as a command, preserving provenance without claiming physical boiler actuation. For a uniquely named device in the user's question, one bounded, read-only 20-minute app-log window can be requested around the latest typed command from a positively identified application (if the gateway supports it and hasn't already been attempted). Gemma receives natural, source-qualified facts about the command, missing scheduler decisions and the difference between thermostat OFF/idle versus proven boiler activity; Technical JSON includes `observedMethodCommandEvidence`. No control changes, no extra provider round, no rigid answer replacement. This does **not** prove protection state or live boiler operation. [Release notes](CHANGELOG-0.18.347.md).

**HomeBrain cross-domain source-completeness pilot (v0.18.346):** For a uniquely verified device's **latest ON/OFF causal investigation**, HomeBrain now requests one bounded, read-only matching `command-on`/`command-off` event history when missing, even when the user did not type a numeric device ID or date. This reuses the pre-existing command-history reader and skips retries after an attempted read. A model-visible issuer-source packet and Technical JSON `recentCommandIssuerSource` distinguish actual typed command witnesses from bridge state reporters, downstream listener apps and merely contemporaneous/later app-log completion entries. The model remains responsible for natural explanations; **a reported log completion alone does not identify the cause of an earlier switch transition**. No device/automation writes, and existing model-first mode remains unchanged. Actual first-answer quality improvement is NOT MEASURED. [Release notes](CHANGELOG-0.18.346.md).

**HomeBrain v0.18.345 rollback to v0.18.343 behavior:** At the user's request after the v0.18.344 source-typed fallback made responses too mechanical, this release reverts the v0.18.344 runtime changes and restores the earlier opt-in model-first answer path from v0.18.343. The v0.18.343 source-authority packet and bounded device-configuration lookup remain; the v0.18.344 contradiction-triggered compulsory template replacement and extra driver-source read are removed. `model_first_investigations_enabled` remains off by default and never grants device write permission. Previous natural model answers sometimes overclaimed broker/physical causes; **naturalness is not verified factual accuracy**. Shift evaluation to cross-domain read-only lighting/heating/ventilation questions, not repeated Bedroom 3 Mesh trials. [Release notes](CHANGELOG-0.18.345.md).

**HomeBrain vNext typed evidence authority (v0.18.343):** When the opt-in `model_first_investigations_enabled` mode is enabled, single-device telemetry synthesis receives a compact request-local source-authority manifest separating saved Hubitat attributes, bounded state events, conflicting metadata clocks, driver-source evidence and independent broker/physical observations. After verified identity/history/scoped logs, one additional read-only device-configuration lookup may be performed, only when a configuration read was not already attempted and the live gateway admits it. This improves the model's evidence context; it does **not** certify model-authored factual claims, independently check MQTT broker state or bypass controls. Mode remains off by default, and the original publisher remains the fallback. [Release notes](CHANGELOG-0.18.343.md).

**HomeBrain vNext read-only model-first pilot (v0.18.342):** A separately switchable `model_first_investigations_enabled` option (default false) lets single-device telemetry investigations request a natural model-authored explanation instead of mandatory JSON claim IDs. The API accepts the exact original provider draft only when coordinator, author and incoming output match and bounded high-risk consistency checks pass; otherwise it retains the previous source-rendered answer. This is a **provisional, not semantically certified** pilot; it neither adds MCP/model reads nor changes controls, heating, lighting or mutation permissions. To test: install v0.18.342, set `model_first_investigations_enabled: true` in the add-on configuration and restart the add-on. Use a READ-ONLY telemetry question and inspect `investigation_coverage.answerPublicationDecision.mode` for `model-authored-provisional` versus `modelFirstRejection`. Set false to roll back without downgrading. [Release notes](CHANGELOG-0.18.342.md).

**Answer Quality Q3 cross-domain source-proof foundation (v0.18.341):** Shared claim-plan validation now supports separate source-witness adapters without enabling unrestricted model prose. An offline-only, target/time-scoped command-witness adapter tests issuer versus physical-cause distinctions. Telemetry uncertainty no longer assumes every health status is offline; existing protected runtime publication remains limited to telemetry. [Release notes](CHANGELOG-0.18.341.md).

**Answer Quality Q3 unified telemetry completion (v0.18.340):** Reconcile verified model claim plans against final source evidence even when a later host confidence guard modified the incoming answer; report fixed rejection reasons for no-claim cases. One-device status/history/scoped logs plus a meaningful read or a gap checkpoint now completes bounded tool exploration instead of stacking independent retry engines; cap single-device connectivity tool rounds without affecting lighting, heating, multi-target or write requests. No extra model/provider calls; no unverified natural prose publication. [Release notes](CHANGELOG-0.18.340.md).

**Answer Quality Q3 model-selected verified claims (v0.18.339):** For a safe, one-device, command-free telemetry source packet, Gemma can choose and order a compact proof-carrying claim plan in its existing final no-tools reply. The publisher rechecks every claim against normalized Hubitat evidence and renders only source-attested statements; arbitrary free-form prose, mismatched identities, missing caveats, altered drafts and other domains retain fail-closed source-backed output. Also suppresses an expensive hidden whole-hub attribute sweep after verified single-device resolution. This is model-directed claim selection, NOT general free-form model-prose certification. [Release notes](CHANGELOG-0.18.339.md).

**Answer Quality Q3 first-model-draft provenance (v0.18.338):** Capture the actual first no-tools model completion privately before any validator, distinguish subsequent coordinator and author-boundary transformations, and publish only fixed Boolean provenance metadata. Arbitrary model prose remains fail-closed until source attestation; no added model or MCP calls. [Release notes](CHANGELOG-0.18.338.md).

**Answer Quality Q3 verified driver-source ID (v0.18.337):** A device instance ID cannot be substituted for a driver code ID. Source reads now require a positively target-linked code ID from Hubitat metadata; unverified source lookups are rejected locally without a hub call or fabricated method interpretation. Scoped logs and independent diagnostics remain available. [Release notes](CHANGELOG-0.18.337.md).

**Answer Quality Q3 read admission (v0.18.336):** After a single named device has a verified ID-scoped history and matching targeted state, suppress model-proposed whole-home snapshots and unrelated name filters for that request. Preserve scoped driver/log/network reads and explicitly requested multi-device comparisons. This removes avoidable broad reads, not verified model rounds or claim validation. No live speed gain certified. [Release notes](CHANGELOG-0.18.336.md).

**Answer Quality Q3 source-typed answer publication:** Ordinary read-only device-telemetry investigations now produce a concise, evidence-grounded explanation by default; event-rich or truncated histories and independently correlated watchdog timing automatically retain the full report, as do explicit full-detail requests. The complete normalized events, clock/source limitations and unresolved physical-cause verdict stay in Technical details. No additional model calls or MCP reads; model prose is not falsely certified by generic synthesis validators. [Release notes](CHANGELOG-0.18.335.md).

**Answer Quality Q1 publisher shadow:** A privacy-minimal diagnostic now records when shared device-telemetry completion replaces the incoming answer, without storing the answer text or treating the incoming text as authenticated raw model output. The publication decision and all safeguards are unchanged. [Release notes](CHANGELOG-0.18.334.md).

**Answer Quality Q1 clock provenance:** A single source-clock warning now uses the existing structured assessment instead of duplicating the discrepancy in separate completion layers. Direct renderer fallback and all root-cause/source-integrity limits remain. No measured quality or latency improvement claimed. [Release notes](CHANGELOG-0.18.333.md).

**Answer Quality Q1 telemetry presentation:** Show the status distinction before a timestamp warning, keep source-code offsets and missing-depth bookkeeping under Technical details, and omit empty command sections. The model-led investigation and evidence-validity gates are unchanged; no claim of measured live accuracy, latency or Claude parity. [Release notes](CHANGELOG-0.18.332.md).

**Answer Quality Q1 dashboard simplification:** Synthetic Ollama Cloud/Stage 5/Stage 6 experiments and Live Shadow are removed from the everyday dashboard in v0.18.429; the independent read-only developer APIs remain for test compatibility. Their existing consent gates and endpoints are unchanged, and System Check remains visible. This release records an ungraded current-build bridge-reporter attribution weakness rather than asserting an accuracy increase. [Release notes](CHANGELOG-0.18.331.md).

**Stage 9.5 cross-source causal evidence:** The investigation pipeline now correlates multiple source-linked motion/presence inactive reports with app-issued OFF commands across bounded episodes, preserving clock/provenance limitations and never interpreting timing as a proven cause. The model receives a concise evidence table before synthesis, and the final result retains a scoped cross-source finding and structured coverage even if the model overlooked it. No additional MCP reads, Cloud rounds or device commands. [Release notes](CHANGELOG-0.18.330.md).

**Stage 9.4 causal answer/coverage consistency:** After model synthesis, the independent hypothesis-verification audit now reconciles claims of high root-cause confidence or completed cause investigation before final publication. Verified device commands, implementation evidence and natural analysis remain intact; a checked source class alone cannot certify a historical sensor trigger. No additional cloud rounds or hub reads. [Release notes](CHANGELOG-0.18.329.md).

**Stage 9.3 upstream app-log format integration:** Fix the Stage 9.2 verified command follow-up to recognise the MCP Rule Server's real `hub_get_logs(mode='past')` `entries` response, distinguish `in_progress` snapshots, preserve hub-local timestamps without claiming verified UTC, and maintain source-scoped privacy filtering. No new calls or device actions. [Release notes](CHANGELOG-0.18.328.md).

**Stage 9.2 multi-command selection:** Live Shadow can now select an individual recorded OFF command when bounded history contains many. On a phone, choose the UTC timestamp from a list, tick fresh separate app-log consent, then run the same fail-closed exact-time verification and four-minute app diagnostic read. Explicit target-ID provenance is tied to the matching command rather than any other command on the page. No new Cloud or device controls. [Release notes](CHANGELOG-0.18.327.md).

**Stage 9.1 mobile copy reports:** Live Shadow now includes a **Copy command results** button after Command Shadow finishes and a **Copy test results** button after the separate Stage 9.1 app-decision follow-up. The latter copies both privacy-filtered visible reports in one paste, including any error/insufficient-evidence status. The clipboard action makes no new Hubitat, Cloud or device calls and does not include raw diagnostic log messages. [Release notes](CHANGELOG-0.18.326.md).

**Stage 9.1 recorded-command issuer follow-up:** After a bounded device history identifies one OFF command with a source-reported app producer, a separate consent enables one **fresh exact-time command recheck** and one **app-ID-scoped four-minute Hubitat diagnostic log read**. Public results contain only safe decision classifications, never app-log messages or a claimed physical cause. The input cannot select an arbitrary app ID. No Cloud or device controls. [Release notes](CHANGELOG-0.18.325.md).

**Stage 9.0 recent incident report reconstruction:** Command Shadow now describes bounded ON-to-OFF state-report intervals, unmatched events and missing command provenance in natural language before the technical audit. It never calls those physical cycles, authenticated timing or identified automation causes. No new Hubitat reads, Cloud AI, device commands or production publisher changes. [Release notes](CHANGELOG-0.18.324.md).

**Stage 8.8 evidence-first historical brief:** The consented Historical Shadow response now begins with a source-bounded, natural-language account of retrieved observations, late native-history replay, available issuing-app evidence, and what remains unproven. It stops recommending repeat empty history reads when independent contemporaneous evidence is unavailable. No Cloud call, new Hubitat/journal read or production publisher change. [Release notes](CHANGELOG-0.18.323.md).

**Stage 8.7 archived command provenance:** Historical Shadow now includes source-reported native command-on/off/setLevel records already preserved in the local journal, with numeric issuing-app ID extracted only from known read-through origin markers. It distinguishes retrospective native-history recovery from fresh device-origin contact, without extra upstream reads or Cloud/production publication. [Release notes](CHANGELOG-0.18.322.md).

**Stage 8.6 bounded source-coverage diagnostics:** Command Shadow independently classifies three successful-but-empty event pages, malformed successful envelopes and filtered date/type/value/device mismatches, with bounded first/last visible times and page-cap flags. It makes the same three read-only Hubitat calls; no inferred historical absence or source completeness. [Release notes](CHANGELOG-0.18.321.md).

**Stage 8.5 command and switch evidence shadow:** A separately consented, UTC-date-scoped comparison reads up to three fixed Hubitat event pages for a selected device (`command-off`, `command-on`, `switch`). It shows source-reported command events, issuing app IDs if source records expose them, and switch reports without promoting coincidence into physical causation. Historical coverage, actual execution, source clocks and production publisher remain unverified. No Cloud AI or device commands. [Release notes](CHANGELOG-0.18.320.md).

**Stage 8.4 temporal-integrity review:** The local Historical Shadow now distinguishes source-declared event time from collector arrival time, flags apparent gaps over 24 hours and source/receipt ordering inversions, and explicitly warns that delayed archive arrival does not prove contemporary device contact. The analysis is deterministic, postrun, privacy-safe, and no more Hubitat/Cloud reads are added. [Release notes](CHANGELOG-0.18.319.md).

**Stage 8.3 opt-in archived history shadow:** A separate phone consent permits a single 30-day local Historical Journal query for one numeric device ID (50-record cap). It reports allowlisted state events, source time versus collector receipt and collection gaps, but no event absence, authenticated packet, command execution, physical state or causation proof. No new Hubitat reads, Cloud calls or production publisher changes. [Release notes](CHANGELOG-0.18.318.md).

**Stage 8.2 verified detailed shadow check:** A second, separately consented live read uses the existing verified paginated detailed-device inventory. The add-on may read multiple Hubitat inventory pages but projects only the selected numeric device's bounded current state fields to the phone. Fallback/stale/unverified source provenance is rejected, missing fields are not absence proof, and no Cloud AI, devices controls, event history or production publisher is used. [Release notes](CHANGELOG-0.18.317.md).

**Stage 8.1 context completeness diagnostics:** Live Shadow distinguishes explicit truncation/partial context and mismatched source totals (still blocked) from missing completeness metadata. When a unique target is present in a returned subset but inventory completeness is unproven, only bounded **provisional target-scoped state reports** appear; no whole-hub or historical absence claim and read-only investigation readiness remains false. The phone UI shows a safe, fixed-vocabulary reason. Cloud and production publisher stay untouched. [Release notes](CHANGELOG-0.18.316.md).

**Stage 8: consented read-only live shadow preflight:** The phone dashboard now provides a separate live context preflight for one numeric Hubitat device ID. It fetches a fresh Hubitat context through the existing read-only resource only after per-run user consent, projects only explicitly allowlisted reported state fields, rejects incomplete/ambiguous inventory, and never invokes Ollama, commands, the normal agent, or the production publisher. It cannot yet verify historical causation, physical actuation, source-clock accuracy or answer semantics. [Release notes](CHANGELOG-0.18.315.md).

**Stage 6.11 citation-shape prompt hardening:** The synthetic final-answer prompt now explicitly requires evidence_ids to be a JSON array of 1–3 distinct leaf-record strings, prefers a single record for a simple claim, and supplies one non-case-specific JSON shape example. It retains the exact leaf allowlist from Stage 6.10 and rejects malformed identifiers without repair or retry. Regression tests include malformed list shapes and all three mocked scenarios within the four-call limit. [Release notes](CHANGELOG-0.18.314.md).

**Stage 6.10 citation-contract clarity:** Explicitly lists examined leaf evidence record IDs for the synthetic final answer and distinguishes source container S* references from E*/I* record IDs. Unknown, malformed, duplicate or source-container citations still fail closed, with safe diagnostic codes and no retry or leaked authored content. Production publisher remains untouched. [Release notes](CHANGELOG-0.18.313.md).

**Stage 7.9 declared proof-target review:** Adds an optional typed proof target to the synthetic Stage 6 follow-up assessment, a separate postrun generic source-class/target compatibility diagnostic, and mobile human-review guidance checking that the author's free-text claims actually match the declaration. Matching structured types do not prove factual or semantic adequacy. Legacy v3 outputs remain accepted, malformed optional targets are withheld, and the production publisher and four-call budget stay unchanged. [Release notes](CHANGELOG-0.18.312.md).

**Stage 7.8.1 optional output recovery:** Malformed supplementary next-evidence text or declaration no longer invalidates otherwise valid synthetic Stage 6 factual sentences after four Cloud requests. Invalid advice is withheld with explicit diagnostics, not repaired or silently certified. The cited answer still undergoes strict structural validation, independent source-value checks, and human prose review. No production route, device access, or extra inference. [Release notes](CHANGELOG-0.18.311.md).

**Stage 7.8 proposed-evidence sufficiency review:** An optional, bounded v3 model-authored follow-up assessment now separates what a suggested source could establish, what it could not prove alone, and which additional verification would be needed. A separate, generic postrun source-capability review and phone UI retain independent human evaluation without certifying prose, adding Cloud requests, routing to hidden reference sources or changing the production publisher. Legacy v3 packets without the optional declaration remain accepted but explicitly unaudited. [Release notes](CHANGELOG-0.18.310.md).

**Stage 7.7 cross-question evidence completeness:** The synthetic Stage 6 planner now receives the selected scenario title alongside the original question and is asked to prioritise distinct evidence needed for unresolved contrasts rather than redundant status reports. An independent, postrun Stage 7.7 review shows report/receipt time inversions and critical reference sources the model skipped, without exposing benchmark gold labels to its selection process. Source-origin timestamps are explicitly not treated as verified clock accuracy. No changes to the production publisher, MCP routing, live devices or cloud-call budget. [Release notes](CHANGELOG-0.18.309.md).

**Stage 7.6 cross-scenario calibration:** Experimental command timelines now distinguish comparable recorded time-of-day values from physical execution, cross-day order and clock accuracy; the evidence ladder also exposes receipt-versus-source clocks and broker-versus-device connectivity. The synthetic Ollama prompt asks for evidence that could establish causal linkage rather than assuming telemetry identifies an initiating app. Mobile review separately assesses next-evidence recommendations and clarifies unverified uncertainty warnings. Mock regression tests cover all three scenarios without real Cloud/device activity or production publisher changes. [Release notes](CHANGELOG-0.18.308.md).

**Stage 7.5 independent evidence-vs-answer review:** A postrun, synthetic-only evidence layer now distinguishes host-observable evidence types from model-supplied sentence labels, original-question completeness from citation overlap, and reported state/telemetry from command-correlated physical causation. Mobile review explicitly shows these as different diagnostics; it never automatically grades Gemma's natural prose, sends extra Cloud requests, changes live Hubitat/HA devices, or enables the production publisher. [Release notes](CHANGELOG-0.18.307.md).

**Stage 7.4 epistemic scope pilot:** Experimental Stage 6 answers now declare each claim subject separately from whether it is affirmed, refuted or not established, and limit the claimed evidence scope. The host distinguishes scoped unresolved causality from an affirmative unique-cause claim, without treating the model's self-declaration or natural prose as independently proven. Stage 7 review asks humans to check that the sentence's actual wording matches the declared position. Prior v1/v2 outputs remain parseable; no production publisher, live device controls or additional cloud calls. [Release notes](CHANGELOG-0.18.306.md).

**Stage 7.3 source-value declaration coverage:** If a fictional model explanation provides `atoms=[]` for a non-relational sentence, the benchmark now preserves the explanation for **explicitly unaudited** human review instead of collapsing the whole four-request run, and clearly scores missing model-declared field proofs. Relation claims can still be supported by host structural comparisons without artificial field atoms. Oversized/malformed/duplicate assertions still fail validation; false values remain flagged as mismatched; high-risk physical and absence claims remain unsupported and no production publisher is enabled. [Release notes](CHANGELOG-0.18.305.md).

**Stage 7.2 direct-answer coverage review:** The synthetic final-answer prompt now asks Gemma to answer the original incident question explicitly, separate causal uncertainty from the event list, and scope negative claims to inspected records. After the answer, an independent source-linked reviewer rubric exposes question-specific obligations without giving those references to the model beforehand. Review judgments remain manual and do not certify or activate the production publisher. [Release notes](CHANGELOG-0.18.304.md).

**Stage 7.1 negative evidence and causal-question review:** Post-run synthetic review now distinguishes absence of physical acknowledgement in inspected records from proof of global nonexistence or nonexecution. It displays model-inspected versus full fictional source coverage, independent review of each sentence's negative-claim scope, and four generic causal-question coverage prompts. No automatic semantic certification, additional Ollama requests, live-device reads or production publisher changes. [Release notes](CHANGELOG-0.18.303.md).

**Stage 7 manual independent prose review:** Each successful synthetic Stage 6 investigation now returns a bounded, source-complete fictional review packet, with selected and unselected records plus the model-authored sentences. The phone UI allows per-sentence human factual verdicts and overall completeness/causal-caution ratings, with an explicit copy-only export. No extra cloud inference, external automatic reviewer, production publisher or live device access. The packet is not automatic semantic certification. [Release notes](CHANGELOG-0.18.302.md).

**Stage 6.6 final-answer diagnostics:** If Gemma completes fictional evidence-selection rounds but fails the strict final JSON/citation contract, the dashboard now shows a safe validation category and preserves only the completed synthetic source choices, reference-source recall and planning quality. No rejected AI prose is published and no extra cloud retries occur. [Release notes](CHANGELOG-0.18.301.md).

**Stage 6.5 question-value investigation:** The synthetic cloud planner now links outstanding incident questions to each unread source, ranks its expected information gain and audits whether the chosen source matches the model's own ranking. It continues to separate model-authored rankings from independently withheld relevance scores; no source is silently substituted and no production publisher is enabled. [Release notes](CHANGELOG-0.18.300.md).

**Stage 6.4 independent decision vs ledger validation:** Cloud-plan decoding now validates only the machine-action READ/STOP and bounded known source IDs as mandatory. A missing/inconsistent optional source-value ledger remains visibly incomplete, without falsely certifying plan quality or silently selecting gold evidence. Unsafe actions and contradictory STOP still fail, with safe diagnostic error categories. No retry, additional cloud requests, production publisher or hub changes. [Release notes](CHANGELOG-0.18.299.md).

**Stage 6.3 investigation completeness:** The synthetic adaptive cloud pilot now asks Gemma to maintain unresolved investigative questions and assess every unread source for material value before stopping. An internally contradictory STOP is rejected, while an apparently coherent but incomplete STOP remains visible against independently withheld evidence labels. This remains an evaluation-only feature; no production publisher, model-routing or live-device changes. [Release notes](CHANGELOG-0.18.298.md).

**Stage 6.2 Ollama Cloud diagnostics:** A manually-triggered, no-inference cloud connection check on the dashboard verifies the existing primary API key via Ollama's account-balance HTTP status only, without showing account balances, secrets or responses. Stage 6 now distinguishes provider HTTP 401 from 403; the Ready status remains configuration-only. No live devices or publisher changes. [Release notes](CHANGELOG-0.18.297.md).

**Stage 6.1 evidence-semantics contract:** The synthetic adaptive Cloud pilot now distinguishes a valid observation with an incorrect source-type label from a falsified field/value claim. Cloud-authored sentences use a structured v2 cited source-value atom contract; the host checks exact values independently, displays stop justifications, and explicitly highlights unread reference-relevant evidence. Full prose meaning remains unverified; no production publisher or MCP tool changes. [Release notes](CHANGELOG-0.18.296.md).

**Stage 6 adaptive synthetic cloud investigation:** New consent-gated dashboard pilot makes up to three successive fictional evidence-source decisions, optionally stopping early, then produces a sentence-linked, cited natural-language answer. Host independently measures withheld source relevance, typed citation validity and missed expected finding types across contradictory clock, controller and connectivity scenarios. Full prose semantics remain unverified, and no real devices or production publisher are affected. [Release notes](CHANGELOG-0.18.295.md).

**Stage 5 autonomous cloud pilot:** With explicit consent, the HomeBrain dashboard now asks the configured Gemma Cloud model to choose up to two fictional evidence sources and write its own source-cited investigation without candidate conclusions. The host separately scores source selection and typed cited claims; free-form prose remains unverified and requires human review. This is a two-cloud-request synthetic pilot, not a production publisher change. [Release notes](CHANGELOG-0.18.294.md).

**Stage 4O cloud benchmark diagnostics:** The existing-account test now categorises Ollama Cloud HTTP errors, timeouts, empty answers and invalid JSON without revealing credentials, accepts a single Markdown-fenced JSON document, and requests a non-thinking final response. No automatic retries or publisher changes. [Release notes](CHANGELOG-0.18.293.md).

**Stage 4N in-app Ollama Cloud benchmark (opt-in):** The HomeBrain dashboard now runs one explicitly consented, fictional evidence-classification test using the already-configured primary Ollama Cloud account. Shows model explanation, response time, independent synthetic claim verdict score and unsupported-conclusion warnings. It never calls MCP, changes devices, or enables the redesigned publisher. No new key or GitHub secret is needed. See [release notes](CHANGELOG-0.18.292.md).

**Stage 4K frozen-answer adjudication (source only):** Binds full authored draft text and re-derived source facts before independent per-sentence reference labelling, then measures omitted claims and exact host-source proof across the answer. No publication or semantic certification. [Release notes](CHANGELOG-0.18.291.md).

**Stage 4J real prose-to-atom coverage evaluation (source only):** Tests whether Qwen2.5 3B extracts all implied factual assertions, including unsupported causes, from constructed natural-language sentences, then independently checks every extracted atomic claim against Stage 4I. Full source coverage does not certify arbitrary prose or enable publication. [Release notes](CHANGELOG-0.18.290.md).

**Stage 4I host-grounded atomic proof obligations (source only):** Adds a pure offline validator requiring exact source witnesses for recorded events, issuers, clocks and coverage gaps; source commands alone cannot prove upstream causes, physical effects or absent events. This does not validate free-form prose or activate the publisher. [Release notes](CHANGELOG-0.18.289.md).

**Stage 4H complete-answer semantic reference benchmark (offline only):** Adds independently labelled multi-sentence synthetic investigations, separates unsupported causes from correct-but-incomplete findings, and tests actual Qwen/Llama reviewers on GitHub without live publication. [Release notes](CHANGELOG-0.18.288.md).

**Stage 4G actual model-authored full investigation answers (offline only):** Qwen2.5 3B generates complete source-cited explanations from constructed evidence; the host measures fact selection and separate reviewer support without granting publication approval. [Release notes](CHANGELOG-0.18.287.md).

**Stage 4F stronger GitHub-hosted model review (synthetic only):** Runs Qwen2.5 3B and Llama 3.2 3B against the fixed source-grounded benchmark with a balanced, example-free reviewer prompt. Exports per-model and consensus false accept/reject metrics, with no live system or publisher changes. [Release notes](CHANGELOG-0.18.286.md).

**Stage 4E GitHub-hosted actual small-model evaluation (synthetic only):** Adds a temporary, CPU-only GitHub Actions workflow with locally downloaded Qwen2.5 0.5B and Llama 3.2 1B, no cloud inference, and aggregate-only reviewer accuracy. Production source/publisher remain unchanged. [Release notes](CHANGELOG-0.18.285.md).

**Stage 4D offline paired-answer quality comparison (source-only):** Adds a privacy-safe, bounded evaluation of the existing answer versus a source-cited model-authored candidate. Typed claims, reviewer concordance and separately supplied human quality ratings remain distinct; no source changes to live publication. [Release notes](CHANGELOG-0.18.284.md).

**Stage 4C consent-gated local-model evaluation (source only):** Adds an opt-in localhost Ollama CLI that can run real, distinct semantic reviewer models on constructed or privately supplied offline cases, with optional separate model-authored answers. Adjudicated reference scores stay separate from unscored generated drafts; no active publisher change. [Release notes](CHANGELOG-0.18.283.md).

**Stage 4B semantic sufficiency reviews (offline only):** Adds a domain-general two-reviewer sentence-entailment protocol and independently labelled false-acceptance/false-rejection benchmark. Reviewer agreement is not proof of semantic truth; authored prose remains ineligible for active publication. [Release notes](CHANGELOG-0.18.282.md).

**Stage 4A model-authored natural-language claim contract (offline only):** Introduces a domain-general canonical source-fact packet and a sentence-by-sentence typed witness validator for draft model explanations. Typed claim success does not attest free-text semantics and cannot enable publication. [Release notes](CHANGELOG-0.18.281.md).

**Stage 3F explicitly consented local read capture (default OFF):** Supports short-lived in-memory, pseudonymised observation of actual model-tool decisions only when both constructor observation mode and an explicitly consented capture session are supplied; no add-on setting activates it. [Release notes](CHANGELOG-0.18.280.md).

**Stage 3E local-only private trace reporting (no live capture):** Adds a strictly aggregate-only report and an explicit-consent local CLI for Stage 3D replay inputs, with small-cell suppression, privacy tests and an unverified-provenance stop. The live observer and planner remain disabled. [Release notes](CHANGELOG-0.18.279.md).

**Stage 3D controlled offline model-call replay (no live calls):** Adds an independently scored pre-round replay of original model-shaped read proposals versus Stage 3A validated candidates. Uses six-domain constructed fixtures; does not claim observed live model improvements or enable any runtime planner. [Release notes](CHANGELOG-0.18.278.md).

**Stage 3C passive model-loop observer (default OFF):** Adds only an explicit constructor opt-in observation mode with source-scoped, catalog-validated counts of the original model's suggested reads; no add-on switch exposes this mode or changes model/tool/publisher behaviour. [Release notes](CHANGELOG-0.18.277.md).

**Stage 3B offline cross-domain planning validation (shadow-only):** Adds independent-oracle scorecards and diverse lighting/heating/fan/power/history/security fixtures to assess Stage 3A's next-read usefulness, duplicate suppression and safety, without any live integration. [Release notes](CHANGELOG-0.18.276.md).

**Stage 3A autonomous read frontier (shadow-only):** Adds evidence-scoped model-proposed READ validation, ranking, exact repeat prevention and no hard-coded five-call stop rule. The new module is not activated in the agent, so actual MCP calls and answers are unchanged. [Release notes](CHANGELOG-0.18.275.md).

**Stage 2.5 offline shadow parity (not activated):** Adds a bounded comparator and compute benchmark for canonical versus V3 witness evidence over retained read receipts. No runtime path imports this module and no AI, tool or publisher behaviour is changed. [Release notes](CHANGELOG-0.18.274.md).

**Stages 1/2 architectural foundation (shadow-only):** Adds an anonymised five-cycle incident regression baseline and typed immutable identity/evidence/coverage adapters for future investigation design. The adapter is not invoked at runtime; existing investigation, tools and publisher behave exactly as in 0.18.272. No AI answer redesign is active. [Release notes](CHANGELOG-0.18.273.md).

**V3 named natural incident stories and cycle timelines:** A successful scoped dependency read now preserves a verified device name, so the source-backed publisher describes the actual sensor instead of its numeric Hubitat ID. The concise answer leads with a plain-language likely mechanism, displays up to twelve independently source-qualified paired ON/OFF cycles in a compact table, and names the verified brightness-adjustment app without treating it as the original ON issuer. Evidence-limited alternative comparisons use verified sensor labels too. Mispaired event histories cannot produce a false cycle timeline. [Release notes](CHANGELOG-0.18.272.md).

**V3 stable witness aliases and source-grounded alternatives:** The final model can cite short source-bound witness aliases, which are resolved to the current request’s exact source-timed witness IDs before existing role, clock and target validation. Unknown or wrong-target aliases still fail closed. Explicit comparisons after source-verified incident publication now describe supported alternative sensor evidence instead of adding generic, unverified hypothesis checklists. [Release notes](CHANGELOG-0.18.271.md).

**V3 claim-guided natural-language publication:** For historical two-target incidents with incomplete native history, a complete and valid source-witness claim envelope can now drive a concise natural-language evidence summary rather than the repetitive legacy digest. Free model prose is never automatically certified by witness IDs; the host renders strictly from verified facts and receiver comparisons. Missing, incomplete or rejected claims first select a short source-only brief when full independent evidence supports it; otherwise the legacy historical digest is preserved. Add allowlisted rejection-reason metrics, balanced ON/OFF witness examples, and regression tests. [Release notes](CHANGELOG-0.18.270.md).

**V3 runtime frontier continuity:** A later model-selected successful dependency leaf now refreshes a verified input-relationship lead within the existing active tool rounds, rather than waiting for new Historical Journal rows. Scoped dependency receipts retain validated app IDs (not names or settings) so an independently verified shared app can become a follow-up. The current read-only model tool catalog and historical attribution safeguards remain authoritative. [Release notes](CHANGELOG-0.18.269.md).

**V3 evidence-ranked upstream read frontier:** Once the same-collector evidence establishes a complete one-to-one input/actuator pattern, the original AI investigator now receives a model-selectable suggestion to inspect that verified input’s Hubitat app dependents before lower-value repeat reads. An independently attested shared current app can become the next config lead. No new gateway permissions, host-executed reads, forced controller attribution or publication change. [Release notes](CHANGELOG-0.18.268.md).

**V3 collector-reception integrity:** When independently source-verified light state has a matching collector copy, the historical investigation now compares sensor and light *reception times on the same collector* without fabricating a sensor source time. The digest identifies complete one-to-one reception patterns, separates full archive retrieval counts from compact receipt samples, and never sums overlapping per-query gap counts as distinct outages. No changes to tool permissions, publication boundary, or control actions. [Release notes](CHANGELOG-0.18.267.md).

**V3 final-synthesis witness handoff:** A qualifying journal-backed multi-target investigation now receives the versioned shadow claim format request directly after its final synthesis instructions. Privacy-safe counters distinguish first-draft claim emission from later repair and terminal publication. Legacy digest fallback and attribution safeguards are unchanged. [Release notes](CHANGELOG-0.18.266.md).

**V3 claim pilot recovery handoff:** The optional source-witness attestation prompt is now shared between initial synthesis evidence and later recovered-journal checkpoints, with a diagnostic counter distinguishing whether the recovery offer was actually delivered. Publication safety remains unchanged. [Release notes](CHANGELOG-0.18.265.md).

**Causal Investigator V3 Stage D1 — shadow claim attestation.** A versioned witness-backed claim envelope is validated against recorded source roles and clocks. A limited optional pilot measures the model's claim references when the existing historical digest will be published; the safety fallback is unchanged. [Release notes](CHANGELOG-0.18.264.md).

**Causal Investigator V3 Stage C — read-source feasibility.** The original model now receives bounded, evidence-grounded suggestions for unqueried read-only app/device dependencies, duplicate-read counts, and explicit missing original-command capability warnings. No invented tool operations, no extra permissions and no terminal answer changes. [Release notes](CHANGELOG-0.18.263.md).

**Causal Investigator V3 Stage B:** Witness-backed, source/clock-typed coverage ledger tracks read-only historical evidence and distinguishes recorded Hubitat ON commands from unverified upstream causes. Shadow-only: no tool routing, model prompt or final answer change. [Release notes](CHANGELOG-0.18.262.md).

**Causal V3 Stage A: shadow publication telemetry.** Evidence-grounded model drafts are now measured against the existing deterministic finalization boundary using privacy-safe request counters. Published answer behaviour is unchanged while we quantify when the fallback hides valid reasoning. [Release notes](CHANGELOG-0.18.261.md).

**Reception-only historical input patterns:** Repeated sensor reception times can now be compared as tentative cross-clock co-occurrence with source-timed device transitions, while explicitly rejecting original-event order or causal attribution. Full-page pattern counts are computed before the evidence receipt's safe 20-row array limit. [Release notes](CHANGELOG-0.18.260.md).

**Archived input evidence:** Independently scoped motion, occupancy and presence histories that return no usable native events now receive a bounded Historical Journal fallback. Source timestamps, collector-only reception, and coverage gaps remain separate in the original model reasoning and final explanation. [Release notes](CHANGELOG-0.18.259.md).

**Source-linked input relevance:** Device event notification metadata is preserved as typed app relationships: app-issued target commands versus notified sensor/target listeners. The original model and final Historical Journal synthesis distinguish shared app leads, different observed app associations and unverifiable links without claiming historical causation. [Release notes](CHANGELOG-0.18.258.md).

**Cross-source sensor reasoning:** When the original agent reconciles a Historical Journal incident, the verified motion/occupancy events already read by MCP now survive into the model evidence packet and final causal explanation. Source gaps remain explicit; correlation never becomes a proven trigger. [Release notes](CHANGELOG-0.18.257.md).

**Historical gap recovery:** Independently verified target histories now retain an explicit historical coverage gap even if all surviving native events are newer than the requested period, allowing bounded Historical Journal recovery and model-directed follow-up. [Release notes](CHANGELOG-0.18.256.md).

**Evidence-driven investigation cycle:** Source-timed Historical Journal observations can inform the original model's remaining read-only investigation rounds, guiding discovery of missing input/controller evidence instead of appearing only after the final answer. Unverified causal conclusions remain explicitly unresolved. [Release notes](CHANGELOG-0.18.255.md).

**Cross-source incident reconciliation:** Historical Journal switch observations are combined with independently sourced native Hubitat switch reports for missing targets, preserving complete multi-device timelines and truthful per-target coverage. [Release notes](CHANGELOG-0.18.254.md).

**Unified native evidence graph:** Device-scoped MCP event receipts now feed source-role edges (reporter, notified listener and verified command issuer) into the existing investigation checkpoint and final-answer validator. This closes an evidence-intake gap responsible for unsupported external-controller verdicts. [Release notes](CHANGELOG-0.18.253.md).

**Target-scoped history integrity:** Device-specific historical investigations no longer treat an unscoped hub event query as proof of zero events for named targets. The original agent receives one safe, model-directed scope-completion read opportunity, and final answers preserve uncertainty when target histories remain unread. [Release notes](CHANGELOG-0.18.252.md).

**Unified investigation event intake:** the original model-directed causal bridge now reconciles typed deterministic device history with native event receipts, recognizes independently resolved input sensors and can request an additional evidence-driven controller read. [Details](CHANGELOG-0.18.251.md).

**General provenance reasoning:** A typed reporter/listener versus initiating-command contract now guides the original model-directed investigation checkpoint and final synthesis across device classes, with a multi-device causal overclaim guard. [Release notes](CHANGELOG-0.18.250.md).

**Native/journal evidence reconciliation:** Preserves independently verified native switch observations before recent-edge fallback claims; native observations are no longer erased by journal-only output. [Release notes](CHANGELOG-0.18.249.md).

**Source-attested dependency leads:** Adds a bounded evidence-only graph for verified app/device associations and distinct command/state observations. The component is not yet integrated with the original agent's live planning or publication path. [Release notes](CHANGELOG-0.18.248.md).

**Recent-window context:** When independently verified device histories all return zero switch events for a relative `last two hours` investigation, the original agent performs a bounded Historical Journal check covering that window and up to 15 minutes immediately before it. It labels the pre-window cycle separately and never promotes collector reception or proximity to a confirmed initiator. [Release notes](CHANGELOG-0.18.247.md).

**All-app decision journal:** When the Historical Journal is enabled, Hubitat app-log collection now defaults to all app IDs, with a separate 48-hour app-log retention and row cap so noisy logs do not displace device-event history. Archived app-decision metadata is checked automatically for source-verified command issuer apps in multi-device investigations; exact source emission and upstream ON attribution are still not asserted. Recent-time windows such as `last two hours` are supported for bounded journal reads. [Release notes](CHANGELOG-0.18.246.md).

**Historical Journal causal synthesis:** Multi-light investigations now use a short source-ranked explanation and grouped source-event chronology rather than displaying every collector copy and command row. Confirmed button-app OFF requests, later brightness adjustments, possible mode-related brightness changes and unverified upstream ON sources are separated. Reception-only observations remain explicitly approximate; the full technical ledger stays in read-only evidence diagnostics. [Release notes](CHANGELOG-0.18.245.md).

**Multi-device Historical Journal recovery:** Original HomeBrain Main Ask now automatically checks independently name-resolved missing switch histories against the configured, running Historical Journal using the verified incident clock window, with separate source-timestamp vs collector-reception and coverage-gap labels. The built-in journal browser now accepts start/end times and copies the full URL with the current HA ingress prefix. No V2 test UI is restored. [v0.18.244 details](CHANGELOG-0.18.244.md).

**Incident evidence/causality validation:** The original HomeBrain MCP agent now preserves verified OFF, setLevel and brightness records even when a target's historical switch-state reports are absent. It distinguishes command receipt from physical transition, asks the model to recover missing switch-only evidence, and replaces contradictory final explanations rather than appending a correct timeline beneath false claims. See [v0.18.243 release notes](CHANGELOG-0.18.243.md).

**Live-verified group chronology:** The original HomeBrain agent now reconciles its final explanation against every independently returned requested-device switch transition, including early finalization paths. A model-authored timeline that omits Bathroom Light 1/2 events is replaced with a chronological source-verified table; unsupported initiating-app certainty is qualified. The separate experimental Investigation V2 browser test, routes and add-on test-token options have been removed. V2 evidence utilities and offline regressions remain available internally. [Details](CHANGELOG-0.18.242.md).

**Unified HomeBrain investigation:** The original MCP agent remains the main read-only investigator and writes natural-language explanations. It now reuses source-attested event projections and temporal relationship evidence from the V2 library without its second planner, rigid JSON-answer publisher or command-count timeline fallback. V2 remains an experimental regression harness; no new V2-specific releases are planned. Historical upstream cause requires independently scoped sensor/automation evidence, not command counts or a successful log query. [Release notes](CHANGELOG-0.18.241.md).

v0.18.240 addresses the remaining Claude comparison gap in Investigation V2 by identifying missing independently scoped input-sensor histories and incident-time execution logs, giving the model a guarded opportunity to fetch discriminating evidence before finishing, expanding source-verified identity lookup capacity, and allowing a longer final natural-language synthesis. All MCP permissions remain read-only and root-cause assertions remain source-limited. [Release notes](CHANGELOG-0.18.240.md).

v0.18.239 fixes the live three-name Bathroom investigation regression: independently verified device focus IDs no longer disable the event narrative. Adds real name-lookup regression replay, clear eligibility blockers and correct timeline-fallback publication diagnostics, while preserving single-target incident safeguards. [Release notes](CHANGELOG-0.18.239.md).

v0.18.238 introduces an evidence-linked natural-language explanation stage for source-verified multi-device histories. It keeps read-only MCP guards, verifies exact event citations, and preserves a chronological fallback instead of command-count catalogs. [Release notes](CHANGELOG-0.18.238.md).

v0.18.232 selects the actual event chain around the user's incident time instead of newest telemetry, includes setpoint/operating-state changes and offers a natural evidence-verified timeline when model reasoning cannot produce cited JSON. [Release notes](CHANGELOG-0.18.232.md).

v0.18.231 unifies Native V2's model investigation policy, removing conflicting fact-ID instructions; sends event values and actor names to evidence-based reasoning, compares plausible causes, and reuses verified in-loop explanations. [Release notes](CHANGELOG-0.18.231.md).

v0.18.230 adds optional model-authored, short, explicitly tentative incident hypotheses in Native V2 when the AI cites at least two exact returned events from the requested date. A host validator checks read IDs, events, timestamps and claimed numbers before publication, and otherwise preserves the source-only answer. [Release notes](CHANGELOG-0.18.230.md).

v0.18.229 introduces dated-incident relevance checks, prevents later command counts from qualifying as an answer to an earlier causal question, and returns a short named-device explanation when source evidence for the period is absent. [Release notes](CHANGELOG-0.18.229.md).

v0.18.228 recovers an explicitly requested historical date and uniquely verified device scope for model-chosen read-only event queries, and shows concise likely-cause explanations without implying automation causation from event proximity. [Release notes](CHANGELOG-0.18.228.md).

v0.18.227 removes the pre-AI keyword-based rejection gate for Native Investigation V2. AI interprets every question in the normal model planning pass, with a local navigation-only handoff tool for real control requests. The server still enforces READ-only MCP execution regardless of AI intent. [Release notes](CHANGELOG-0.18.227.md).

v0.18.226 upgrades verified temporal leads to join actual device-produced `lastSeen`, `switch`, and subsequent `healthStatus` event timestamps without asserting physical action or causation; it also recognises app metadata already read. [Release notes](CHANGELOG-0.18.226.md).

v0.18.225 adds a generic, timezone-aware chronological lead for source-verified device contact metadata and individually scoped app-command events, with explicit checks for causal uncertainty and evidence limits in read-only V2. [Release notes](CHANGELOG-0.18.225.md).

v0.18.224 refines source-verified, room-first device answers: no repeated lights, explicit unread-member scope, and separate displayed-answer validation from the model's unused fact-selection diagnostics. [Release notes](CHANGELOG-0.18.224.md).

v0.18.223 preserves authoritative room names returned by `hub_list_rooms` instead of discarding the list, makes source-attested room lookup available to the V2 planning model, and rejects costly full-device enumeration once the original question has a verified room-name match and a live targeted room read is available. [Release notes](CHANGELOG-0.18.223.md).

v0.18.222 independently validates V2 fact selections and narrative findings: an unsupported explanatory segment no longer discards separate verified conclusions. This release remains V2-test-only and does not modify production Hubitat control. [Release notes](CHANGELOG-0.18.222.md).

v0.18.221 adds source-verified room-member discovery and readable natural-language answers in experimental V2; actual member states still require individual Hubitat reads and the detailed evidence report remains separate. [Release notes](CHANGELOG-0.18.221.md).

v0.18.220 fixes the V2 test page displaying the technical report instead of the complete source-verified answer; independently complete device-group investigations also skip redundant final claim-only inference. [Release notes](CHANGELOG-0.18.220.md).

v0.18.219 now composes complete, readable answers for independently verified multi-device groups rather than dropping later entities from a capped list of attribute facts; it preserves explicit room-membership uncertainty and safe fallback. [Release notes](CHANGELOG-0.18.219.md).

v0.18.218 makes multiple independently attested name-prefix matches available as safe individual READ candidates, and prevents a redundant 20-second full-device-list fallback after a bounded identity lookup. [Release notes](CHANGELOG-0.18.218.md).

v0.18.217 prevents unrelated generic health evidence from being presented as an answer to an unresolved named subject, and permits individually verified read-only exploration of small collectively named device candidates. [Release notes](CHANGELOG-0.18.217.md).

v0.18.216 reuses independently checked model-authored explanations from existing READ-loop responses, avoids an additional doomed model call on slow providers and publishes explicit planning-model latency diagnostics. The source-bound fallback remains unchanged. [Release notes](CHANGELOG-0.18.216.md).

v0.18.215 adds an optional model-authored, independently source-checked explanation and diagnostic next steps for broad Native V2 cases; unverified model text is withheld and the v0.18.214 answer remains as fallback. [Release notes](CHANGELOG-0.18.215.md).

v0.18.214 links source-attested warning groups with independently matched device telemetry by ID. The concise general V2 answer now leads with corroborated, bounded evidence even when the model finishes normally; full source limits remain available in the technical report. [Release notes](CHANGELOG-0.18.214.md).

v0.18.213 publishes a concise source-verified summary of multi-source Native V2 questions and can skip the expensive extra claim-only model call at bounded read limits, without changing read permissions or implying V1 parity. [Release notes](CHANGELOG-0.18.213.md).

v0.18.212 carries independently attested device-health staleness, unknown activity and app-reference evidence into the general V2 claim ledger and answer, even when the model returns an invalid or overly narrow fact selection. [Release notes](CHANGELOG-0.18.212.md).

v0.18.211 removes the broad production command shortcut classifier from V2 read-only admission, accepts negative action instructions and general Hubitat reasoning questions, and rejects independently affirmative write requests before tools run. [Release notes](CHANGELOG-0.18.211.md).

v0.18.210 distinguishes failed source/configuration inspections from untried paths and prioritises source-attested warning-cluster activity while retaining bounded causal uncertainty. [Release notes](CHANGELOG-0.18.210.md).

v0.18.209 describes operation-specific nested READ requirements from the live tool manifest, offers a non-executing repair shape for verified focus IDs and communicates bounded event evidence already seen. [Release notes](CHANGELOG-0.18.209.md).

v0.18.208 preserves a verified device subject across typed target WARN, runtime and event reads, and extracts only source-attested device/app performance statistics from broader tables. [Release notes](CHANGELOG-0.18.208.md).

v0.18.207 recognises Hubitat Logs device/app performance tables as cumulative, source-typed numerical evidence, rather than mistaking them for WARN lines or claiming historic incident-time CPU measurements. [Release notes](CHANGELOG-0.18.207.md).

v0.18.206 groups returned generic excessive-load warning timestamps into bounded observation clusters and prioritises independently source-attested, incident-time app command leads over remote historical command bursts, without claiming CPU causality. [Release notes](CHANGELOG-0.18.206.md).

v0.18.205 aligns causal coverage hints with previously completed target WARN reads, distinguishes host-authoritative incident publication from model-claim rejection, and corrects single-row warning wording. [Release notes](CHANGELOG-0.18.205.md).

v0.18.204 preserves independently verified device focus when the model reads the user's named target directly, and avoids discarded model-only synthesis for already source-authoritative generic warnings. [Release notes](CHANGELOG-0.18.204.md).

v0.18.203 adds bounded cross-occurrence warning/state associations, deduplicates observed warning instants and prevents unscoped event-history reads once a unique target is verified. [Release notes](CHANGELOG-0.18.203.md).

v0.18.202 keeps discrete timestamp evidence for grouped warnings, improves source-read blockers and read-contract repairs. It does not claim a measured driver cause. [Release notes](CHANGELOG-0.18.202.md).

v0.18.201 introduces a general source-backed structured claim validator for experimental Native V2 answers, withholding unverified model prose and rendering only independently supported facts and compatible numerical comparisons. [Release notes](CHANGELOG-0.18.201.md).

v0.18.200 records source-receipt factual observations beyond generic WARNs and offers model-led, separately attested driver/source follow-ups. These observations cannot verify arbitrary causal model claims. [Release notes](CHANGELOG-0.18.200.md).

v0.18.199 adds identity-verified, privacy-filtered static Groovy method-call and platform-API evidence when a complete source read is available. This never proves executed code or the cause of a warning. [Release notes](CHANGELOG-0.18.199.md).

v0.18.198 makes generic incident conclusions source-authoritative, withholding free-form model causal prose whenever incident attribution is unverified instead of relying on detectable words like “offender”. It records a per-fact evidence receipt ledger and retains model-chosen read-only investigation. [Release notes](CHANGELOG-0.18.198.md).

v0.18.197 audits model causal rankings against source-attested incident windows, command timing, observed command bursts and device-owned state transitions. Unsupported "most likely offender" conclusions are withheld in favour of source-grounded explanations; app-page reads now project safe navigation metadata rather than appearing as empty. See [release notes](CHANGELOG-0.18.197.md).

v0.18.196 distinguishes an MCP source response from verified complete source code, preserves safe lexical method declarations only when source identity/completeness are attested, and prevents duplicate broad log reads that merely increase their limits without changing scope or time filters. [Release notes](CHANGELOG-0.18.196.md).

v0.18.195 projects source-attested nested app settings-page metadata instead of empty app reports, and gives the model a concrete, read-only `hub_get_source` argument contract with independently verified app/driver IDs after malformed proposals. Source-code contents and private setting values remain excluded. See [release notes](CHANGELOG-0.18.195.md).

v0.18.194 enforces device-scoped event-history reads when a uniquely verified target has matching WARN evidence, rejects repeated invalid proposals before they waste more investigation rounds, and skips redundant final model synthesis after those failures. Explicit hub/location history remains available. See [release notes](CHANGELOG-0.18.194.md).

v0.18.193 separates known command issuers from the still-unattributed cause of a generic load warning, exposes bounded numeric memory-history measurements (or explicitly reports when history contains only timestamps), and gives the model an early source-derived coverage hint while preserving read-only tool selection. See [release notes](CHANGELOG-0.18.193.md).

v0.18.192 prioritises attested callers during slow driver-method warnings over unrelated later generic warnings, detects repeated event-history subsets, deduplicates named callers in conclusions, and provides the verified device ID when a proposed detail read omits it. [Release notes](CHANGELOG-0.18.192.md).

v0.18.191 separates independently verified app command issuers from unresolved driver-method execution. It avoids fabricating command names from internal warning methods, offers app-specific read-only follow-up, and prevents invalid device-scoped global driver-list reads. See [release notes](CHANGELOG-0.18.191.md).

v0.18.190 compares command-event history timestamps against source-attested slow-method warning windows. A newer status-only page cannot establish earlier issuer coverage. The model can choose one bounded command-filtered historical follow-up; repeated subsets of previously seen warning groups no longer crowd out evidence. See [release notes](CHANGELOG-0.18.190.md).

v0.18.189 preserves safe numeric hub metrics/trends in native read evidence, tracks repeated tool discovery and allows one bounded, model-directed causal-coverage read when a target has warnings but no issuer-event evidence. It does not automatically choose or execute a device-event read. [Release notes](CHANGELOG-0.18.189.md).

v0.18.188 adds source-typed cross-domain device/app/driver identities and preserves command issuer provenance from verified device events. Native V2 can inspect independently attested calling automations and report unverified timing coincidences with slow-operation warnings. [Release notes](CHANGELOG-0.18.188.md).

v0.18.187 preserves bounded, privacy-filtered driver/configuration/section metadata in Native V2, circuit-breaks two failed calls to the same target operation, and avoids an unnecessary final model timeout when source evidence is already sufficient for a qualified fallback at the investigation limit. It also distinguishes Logs-page summary rows from actual severity logs. [Release notes](CHANGELOG-0.18.187.md).

v0.18.186 fixes native MCP diagnostic query compatibility: the model is prevented from combining a Logs-page tab such as `devices` with a `level` filter that the server rejects. Corrected, bounded `mode=past` severity reads can use verified device IDs. Focused negative evidence now shows the actual sampled time range rather than implying historical clearance. See [release notes](CHANGELOG-0.18.186.md).

v0.18.185 prioritizes attested target evidence in native MCP reasoning, collapses repeated identical current-state snapshots, and supplies target-specific grounded fallback conclusions when the final provider times out. It keeps full source receipts and read-only safety; see [release notes](CHANGELOG-0.18.185.md).

v0.18.184 adds model-selectable verified named-device lookup (no mandatory full inventory), validates operation-required fields before executing a gateway, preserves health source fields and readable Markdown answers, and strengthens strict log source-ID recognition. Native V2 remains experimental and read-only. See [release notes](CHANGELOG-0.18.184.md).

v0.18.183 strengthens the native read agent with operation-specific argument contracts, a timeout circuit breaker to avoid repeating expensive failed full inventories, and source-backed answer fallback when the LLM synthesis fails. Read-only behavior is preserved and production Main Ask remains unchanged. [Release notes](CHANGELOG-0.18.183.md).

v0.18.182 fixes the native MCP READ agent after two live trials: log data returned as `entries` now provides severity-grouped WARN/ERROR evidence instead of noisy INFO chatter, IDs attested by structured log sources may support scoped follow-ups, a lazy identity lookup avoids forcing full device inventory, unknown gateway fields are exposed as projection gaps, and a bounded final answer attempt prevents otherwise blank conclusions. See [release notes](CHANGELOG-0.18.182.md).

v0.18.181 introduces an explicit experimental **native MCP READ agent** in V2: the configured model selects live read gateways and investigates across hub, app, rule and device domains without forced device inventory or keyword routing. Host security validates every operation/ID/schema and preserves bounded source evidence. The legacy V2 evaluator remains selectable for A/B comparison; production Main Ask writes remain unchanged. See [release notes](CHANGELOG-0.18.181.md).

v0.18.180 adds a model-selected, system-scoped **read-only** V2 audit for whole-hub health, automation and log questions. The host uses the established System Check with persistence disabled, not device-name guessing or Hubitat writes. Log sampling and source failures are always disclosed. See [release notes](CHANGELOG-0.18.180.md).

## Architecture

v0.18.158 adds an evidence-first historical read around the device-reported lastSeen (never equating it with confirmed physical contact), a schema-gated includeSettings option for event-attested controller app configuration, diagnostics for empty projections, and a longer but bounded investigation-only model planning budget. Factual questions remain unchanged and entirely avoid model planning. See [release notes](CHANGELOG-0.18.158.md).


v0.18.157 permits the verified controller-settings read when the live MCP gateway advertises a read-only `hub_get_app_config` operation with a generic open argument-object schema. Closed/incompatible schemas remain rejected; all calls still pass source-ID verification and the host read-only validator. V2 also exposes bounded per-page inventory timings to diagnose latency. See [release notes](CHANGELOG-0.18.157.md).


v0.18.156 separates a fresh identity-only V2 inventory projection from the expensive full state/capability audit, allowing uniquely named devices to proceed with independently verified labels before targeted status/event reads. Broad or ambiguous questions still retrieve full inventory; audit completeness and pagination proofs remain mandatory for the direct target route. Controller source reads now include explicit live-manifest/schema/rejection diagnostics when app configuration is not available. Gains remain to be established by live testing. See [release notes](CHANGELOG-0.18.156.md).


v0.18.155 introduces a question-bound, verified single-device factual path for current switch status and recent ON/OFF reports: host-validated reads answer those specific questions without waiting for a causal AI planner. Ambiguous and causal requests still run investigations. App configuration can now be requested for a command issuer independently verified by event history even when its name is already in the catalogue. No writes, and wider Claude-like causal reasoning remains under test. See [release notes](CHANGELOG-0.18.155.md).


v0.18.154 explicitly separates write requests from read-only Investigation V2 before inventory, model or MCP calls. It reuses the production write-intent classifier and adds a negative-only guard for compound direct commands, returning a clear message to use main HomeBrain Ask/Chat without issuing any action. Broader opt-in read-only V2 testing is documented in [V2 test readiness](docs/INVESTIGATION-V2-TEST-READINESS.md); V2 is not a replacement for production device control. See [release notes](CHANGELOG-0.18.154.md).

v0.18.153 bounds the opt-in V2 read-only investigation model-planning round to 15 seconds after verified source reads; its deterministic report preserves current switch/network state and the latest switch report even when the model times out. The compact timeline retains both oldest and newest switch events; MQTT and power disclaimers are shown only for relevant source attributes. It never promotes the reporting bridge into a verified controlling automation. See [release notes](CHANGELOG-0.18.153.md).

v0.18.152 uses a direct source-first Investigation V2 route when a provably complete, fresh Hubitat inventory uniquely identifies one named device in the question: the independent model intent stage is skipped, but strict device identity, read-only MCP tool/schema validation, and source-backed reporting remain mandatory. Broader or unverified scopes still use semantic planning. When speculative additional reads supply no new canonical evidence, V2 reports verified facts without a costly follow-up model claim-repair round or unsupported root-cause hypotheses. Production V1 and Hubitat automations are unaffected. See [release notes](CHANGELOG-0.18.152.md).

v0.18.151 improves the Investigation V2 evidence report for real source timelines: include relevant MQTT transitions alongside commands instead of hiding all but the command, summarise repeated health-status flips, accurately label UTC timestamps, and identify when the device's reported lastSeen precedes the earliest returned history. These are source-derived presentation changes, not AI-authored root causes or any additional device writes. See [release notes](CHANGELOG-0.18.151.md).

v0.18.150 retains read-time device snapshots in the canonical grounded answer when the event timeline is empty, without treating a stale power value or MQTT client connection as physical proof. An empty switch-filtered event request can trigger one bounded unfiltered history read under the same live MCP permissions and verified-ID controls. Snapshot-only investigations skip unsupported atomic-claim model rounds. V1 and Hubitat automations remain unchanged. See [release notes](CHANGELOG-0.18.150.md).

v0.18.149 repairs the opt-in Investigation V2 zero-read fallback by learning exact read-operation mappings from current-session live MCP discovery when gateway schemas omit operation enums. Every device source request remains subject to verified device-ID, schema, effect and read-only gateway policy; explicit-denial enums cannot be overridden. Diagnostics explain when discovery or reads are unavailable, and recognised BST/GMT lastSeen formats can guide bounded historical retrieval without asserting physical contact. Production V1 and Hubitat automations are unchanged. See [release notes](CHANGELOG-0.18.149.md).

v0.18.148 strengthens Investigation V2 subject resolution for long investigations containing incidental references to status, MQTT and events: an independently unique multiword friendly-name mention is used as an anchor rather than allowing later unrelated ambiguous aliases to veto it. Genuine ambiguity at the primary subject still fails closed. Errors now display sanitized matching names and the conflicting phrase (when available) instead of blank `Device` placeholders. Opt-in V2 only; existing V1 and Hubitat automations unchanged. See [release notes](CHANGELOG-0.18.148.md).

v0.18.147 resolves V2 name collisions by preferring an exact, independently verified Hubitat friendly label to another device's generic driver name when both match the same complete phrase. It still rejects genuinely duplicated friendly labels and now identifies their verified candidate device IDs for an Advanced override. The same rule applies to automatic matching, semantic fallback, and explicit friendly-name override. No live device writes or V1 changes. See [release notes](CHANGELOG-0.18.147.md).

v0.18.146 prevents opt-in V2 from aborting after a semantic intent-planning timeout: when the original question independently matches exactly one Hubitat device, V2 continues with a bounded, host-only read-only evidence pass, skips further provider calls and clearly marks the answer as partial and the intent as unverified. Ambiguous/broad questions still fail closed, without inventing a target. End-to-end elapsed time now includes intent planning. See [release notes](CHANGELOG-0.18.146.md).

v0.18.145 adds optional evidence-first V2 current-device status and adaptive switch-history preflight, with host-validated live gateway operations and limited AI replanning after tool-selection rejection. Read-time snapshots are separated from historical events; routine health-only event histories no longer render a blank timeline. This does not change production V1. See [release notes](CHANGELOG-0.18.145.md).

v0.18.144 fixes V2 device identity selection: source-grounded names in the user's question take priority over AI-proposed labels; model-only names require a unique live Hubitat match and never resolve an ambiguous user phrase. Hidden Advanced overrides are no longer submitted and errors wrap below the Run button. Production V1 and write guards are unchanged. See [release notes](CHANGELOG-0.18.144.md).

v0.18.143 adds an opt-in browser sign-in for the V2 test page. It remembers access for 30 days in an HttpOnly, SameSite=Strict, HMAC-authenticated browser cookie without storing the raw operator token in browser localStorage or chat; changing the add-on V2 secret revokes remembered sessions. A **Forget saved access** control signs out. HTTP LAN access is not encrypted—use HTTPS on trusted devices where practical. See [release notes](CHANGELOG-0.18.143.md).


v0.18.142 stages generic V2 semantic question interpretation separately from optional meter-role inference, reducing the intent prompt size and preserving a source-safe answer if meter enrichment cannot finish. Failed planning now returns stage-specific diagnostics instead of an opaque 503. See [release notes](CHANGELOG-0.18.142.md).


v0.18.141 introduces typed measurement scope to V2 inventory queries: current site totals, circuit subtotals and individual meters are separated, AI scope interpretations are explicitly unverified and device IDs must exist in the live inventory; one-time operator-confirmed role mappings can be supplied in add-on configuration. See [release notes](CHANGELOG-0.18.141.md).


v0.18.140 introduces a **semantic objective → host validation → generic evidence query** layer for opt-in V2, replacing phrase-bound current-group routing. The model can interpret novel inventory questions into typed selection, filtering, grouping, ranking and aggregation instructions, while the host verifies all fields and performs read-only computations. See [release notes](CHANGELOG-0.18.140.md).


v0.18.139 adds read-only, full-group current light state questions to Investigation V2. Device identification is no longer mandatory for an explicitly plural inventory question; V2 reuses the paginated, state-aware Hubitat reader and the same established light/state helpers as HomeBrain. See [release notes](CHANGELOG-0.18.139.md).


v0.18.138 adds host-local calendar resolution for 'today'/'yesterday', safe short-name identity matching for noun phrases, independently verified device ID completion for read requests, and deterministic switch ON/OFF duration calculation with explicit coverage caveats. See [release notes](CHANGELOG-0.18.138.md).


v0.18.137 attaches bounded, privacy-safe failure classifications to failed V2 MCP reads, displaying them in the summary and technical report without exposing raw server exceptions. See [release notes](CHANGELOG-0.18.137.md).


v0.18.136 displays V2 elapsed time as minutes plus seconds (and total seconds), retains millisecond precision in the copyable report, and makes budget-stopped outcomes visible. See [release notes](CHANGELOG-0.18.136.md).


v0.18.135 compares two bounded source-history samples, retrieves one source-attested unknown app configuration when available, and avoids extra provider calls when planning times out. See [release notes](CHANGELOG-0.18.135.md).


v0.18.134 adds compact but complete-for-planning source evidence, safe provenance-driven app identity lookup before model planning, and bounded per-round planner timing diagnostics. See [release notes](CHANGELOG-0.18.134.md).


v0.18.133 improves opt-in V2 model plan diagnostics and historical time accuracy. It verifies clock times in model hypotheses against the cited records and zone, projects nested MCP required fields to the planner, and exposes read rejection codes in the technical report. Production V1 is unchanged. See [release notes](CHANGELOG-0.18.133.md).


v0.18.132 uses app/rule lookup results as bounded current identity metadata (not historical execution proof), selects incident-relevant command interactions rather than first chronological matches, and avoids repeat model planning when reads yield no new usable evidence. See [release notes](CHANGELOG-0.18.132.md).


v0.18.131 resolves explicit device names in V2 test questions against a fresh Hubitat inventory. IDs are optional and remain as an advanced fallback. See [release notes](CHANGELOG-0.18.131.md).


v0.18.130 adds incident-first, verified-ID historical reads and a concise source-linked V2 test report, with the full atomic/technical answer collapsed below. V1 production remains unchanged. See [release notes](CHANGELOG-0.18.130.md).


v0.18.129 improves V2 test errors: HTTP status and field-level validation details display without exposing tokens, with real endpoint auth/validation/success regression tests. See [release notes](CHANGELOG-0.18.129.md).


v0.18.128 adds a separate token-gated read-only V2 testing panel, a verified-device-ID admission gate, source-checked answers and timestamp-only V1/reference scorecards. Default chat remains V1; see [test setup](CHANGELOG-0.18.128.md).


v0.18.127 adds an optional source-linked, concise explanation of chronological observations and an honest offline replay scorecard. All narratives require verified IDs, ordering and stages; **normal chat stays on V1**. See [release notes](CHANGELOG-0.18.127.md).

v0.18.126 adds strict, source-backed atomic claim verification and at most one targeted revision of rejected claims. It preserves material incident commands and never rewrites approved findings. **Opt-in V2 harness only; no default chat cutover.** See [release notes](CHANGELOG-0.18.126.md).

v0.18.125 adds an opt-in V2 AI planner using the existing ChatTransport and source-backed synthesis that preserves incident commands without declaring unverified causes. **No default chat routing changes.** See [release notes](CHANGELOG-0.18.125.md).

v0.18.124 introduces an explicitly invoked, bounded V2 read-only MCP execution loop using the existing ToolExecutor, with sanitized evidence receipts and candidate hypotheses. **It is not connected to production chat answers.** See [release notes](CHANGELOG-0.18.124.md).

v0.18.123 adds typed read-only evidence adapters and a bounded, verified MCP read-plan contract for Investigation V2. This is a **passive foundation**, not a live reasoning cutover. See [release notes](CHANGELOG-0.18.123.md).

v0.18.122 starts the bottom-up Investigation V2 implementation with a passive, typed evidence case file and 15 history/provenance regression tests. **No live investigation routing or Hubitat controls change yet.** See [release notes](CHANGELOG-0.18.122.md).

v0.18.121 adds source-typed historical window integrity. For overnight incident questions with two explicit dated clocks, HomeBrain now supplies precise UTC boundaries across local time changes and prevents later-only retained history from becoming a confident missing-event/failed-controller verdict. A verified separate focal archive can still support its own reconstruction. See [release notes](CHANGELOG-0.18.121.md).

v0.18.120 preserves the AI-interpreted answer deliverable separately from the inspected entity. A question about why an existing automation failed now remains a diagnosis rather than becoming a formal existing-rule audit with a generic partial report. During multi-round investigations, optional Groovy workbench reads cannot silently substitute an unverified app instance after exact app-target evidence was established. The model is directed to contrast successful and failed episodes and distinguish findings from missing evidence across all device/automation domains. See [release notes](CHANGELOG-0.18.120.md).


v0.18.119 prevents a real long-running motionHandler warning from becoming a proven explanation for separate light-OFF sequences when app-matched OFF commands and subscribed occupancy input events align at measured inactivity gaps. The structured logs parser also recognizes Hubitat's `method ... of child app ...` wording. Source interpretation, actual timer configuration, and physical occupancy remain unverified without direct evidence. See [release notes](CHANGELOG-0.18.119.md).


v0.18.118 corrects an evidence-erasure regression in deep existing-rule verification: a partial native Rule Machine action-tree read no longer discards *independently verified* controller OFF commands, subscribed sensor-to-OFF timing, installed Groovy source coverage, or scoped long-handler WARN logs. Typed, app-ID-matched observations remain separate from unverified compiled logic; this applies to custom controller apps as well as rule audits. See [release notes](CHANGELOG-0.18.118.md).


v0.18.117 preserves **positive causal evidence** rather than discarding it when unproven ghost-motion claims are calibrated. A generic, ID-agnostic event correlator pairs app-issued OFF commands with the light's reported OFF transition and its subscribed motion inputs' last recorded inactive edges. It reports the measured delay per OFF and any observed active interval while retaining uncertainty about real-world occupancy and incomplete event-history coverage. Clone sensors without controlling-app listener evidence are not mistaken for independent inputs. See [release notes](CHANGELOG-0.18.117.md).


v0.18.116 adds source-grounded false-motion claim verification. A model cannot use a coincident event from a cloned/virtual sensor to prove it triggered another app's OFF timer, nor may it infer empty-room ghosting without independent vacancy evidence. For unproven causal assertions the final answer preserves verified switch intervals and timestamp-aligned OFF command/state pairs and explains what remains uncertain. Investigator guidance prioritises exact configured activation/keep-on sensor IDs over arbitrary nearby event histories. See [release notes](CHANGELOG-0.18.116.md).


v0.18.115 restores **room scope** for model-selected live light and non-light switch aggregates. The tool schema now accepts an optional room, but execution additionally enforces the original question's room constraint against Hubitat's authoritative room metadata, so an AI-proposed no-argument whole-home read cannot answer a Living Room-only question as a household summary. Results retain scoped counts, exact matching room names and non-leaking unresolved scope; unrelated rooms are excluded from visible answers. See [release notes](CHANGELOG-0.18.115.md).


v0.18.114 closes a repeated root-cause failure where a diagnostic question finished as a room-device inventory despite AI-first routing. Investigations now hide the inventory-only presenter from the model's tool registry (including after discovery), allow one bounded evidence-seeking retry before an inventory-only model conclusion, and refuse to return an inventory as a completed diagnosis at the agent boundary. Host route overrides retain the effective interpreted objective. Virtual/soft sensor copies are not treated as independent proof of occupancy without verified parent/input identity. Original read-only safety and normal inventory queries remain intact. See [release notes](CHANGELOG-0.18.114.md).


v0.18.113 checks model-authored specific-sensor OFF-blocker diagnoses against sensor-specific live state and app-log timer decisions. Where both are absent, it replaces the confident diagnosis with a concise evidence-grounded, clearly tentative explanation without implying that complete Groovy retrieval proves a past runtime branch. It also corrects ON/OFF interval tables where the model's duration conflicts with deterministic recorded interval seconds, preserving the original evidence and technical JSON. No additional keyword routing and no Hubitat changes. See [release notes](CHANGELOG-0.18.113.md).


v0.18.112 gives AI interpretation precedence for open-ended read-only investigations, preserves its selected target/purpose in the actual model-led evidence workflow, and prevents the legacy room-inventory shortcut from answering a causal investigation as a device list. Read-only command permissions remain host-enforced. Incomplete source/coverage notes are placed in Technical details as structured `investigation_coverage.limitations`, not appended to the visible answer. See [release notes](CHANGELOG-0.18.112.md).


v0.18.111 restores browser request lifecycle state (`activeRequest`, `requestSequence`) accidentally removed during 0.18.110 chat-history cleanup. Without these declarations, the Ask handler throws a JavaScript ReferenceError before POSTing `/api/ask`, and New topic is also broken. The fix keeps the compact, history-free UI and adds a Node-executed click regression covering a live Ask call, follow-up context, and New topic reset. No Hubitat writes. See [release notes](CHANGELOG-0.18.111.md).


v0.18.110 removes the browser-saved multi-chat history, tabs and earlier-message transcript from the HomeBrain web UI, freeing room for the Ask/Speak controls and current response. A lightweight New topic control resets the ephemeral in-page context. Follow-up questions still receive up to eight recent user/assistant messages until the page is reloaded or reset. Legacy browser-saved chat records are cleared on first load of the new UI; no saved conversations are retained. Read-only evidence, technical JSON, model selection and confirmation safeguards remain available. See [release notes](CHANGELOG-0.18.110.md).


v0.18.109 increases the configurable default read-only investigation deadline to 180 seconds and exposes the active AI-reasoning/tool-execution phase when diagnosing a timeout. Earlier successful read receipts still produce a safe evidence-only incomplete result; no receipt still results in HTTP 504 with stage detail. Existing add-on installations may retain the previous 90-second value: update `investigation_deadline_seconds` manually in the add-on Configuration to use 180. This does not prove or change any Hubitat cause, automation or device. See [release notes](CHANGELOG-0.18.109.md).


v0.16.145 replaces the scheduler secondary bulk device-list scan with a bounded **targeted candidate probe**. When a complete `hubitat://context` response omits scheduler-key candidate device IDs, HomeBrain samples at most six IDs through `hub_get_device`, with at most two reads in flight and a 4.5-second total deadline. Only an exact returned numeric ID establishes presence in that second source; failures, not-found responses and timeouts remain unresolved. The sample never establishes job ownership, deletion, redundancy, Hubitat-wide inventory completeness or CPU savings. No Hubitat settings or schedules are changed.\n\nv0.16.144 adds a bounded **secondary device identity corroboration** stage for scheduler-key candidates absent from the primary `hubitat://context` resource, using at most four identity-only MCP device-list pages within a 4.5-second overall deadline. It reports only which IDs are present in the second returned source, never job ownership or definitive deletion. It also ranks actual no-candidate handler counts (including reminder handlers) separately from jobs with candidate IDs. The second source does not prove Hubitat-wide inventory completeness. No Hubitat settings or scheduled jobs are altered.\n\nv0.16.143 makes the first scheduler-summary table evidence-first: recognizable model-written scheduler tables are replaced by the deterministic complete-source job digest (including all top handlers), and the model's unlabeled cadence table is replaced by source-labelled recent log intervals. Those log observations are explicitly **not** scheduled-job executions. The MCP context inventory is treated as a complete response *within its own scope*, never independently verified to be a full Hubitat device census; app inventory source metadata is corrected. AI inspection commentary is retained. Entirely read-only.\n\nv0.16.142 fixes the slotted agent outcome contract used by investigation timeouts: the base `AgentOutcome` now explicitly supports `route`, and the observed metrics wrapper preserves it. Both the overall investigation deadline and AI synthesis timeout can return a safe, evidence-only `investigation-timeout` response instead of raising `AttributeError`. Regression coverage exercises production outcome classes and the `/api/ask` serializer. The code does not extend timeouts or modify Hubitat settings; live confirmation is required.\n\nv0.16.141 prefers Hubitat MCP's completeness-checked compact `hubitat://context` device identity resource instead of the expensive 450-device list in scheduler optimisation reviews. Where that resource is not complete/available, one first-page read-only device-list fallback is attempted within the same six-second total stage deadline. A partial result can verify present IDs but cannot confirm absent IDs. When an inventory read is unavailable, candidates are displayed as **not checked**, never as deleted or unlisted. Complete app inventories display exact unlisted candidate IDs for inspection without proposing deletion. Scheduler job ownership and CPU savings remain unverified. No Hubitat writes.\n\nv0.16.140 fixes an unexpected runtime error in the v0.16.139 scheduler inventory cross-check: three new request-level metrics were not registered in the strict metric allowlist. Regression tests now exercise the real request metrics collector on successful inventory and timeout paths, in addition to existing bounded/read-only inventory tests. No Hubitat devices, apps or schedules are changed.

Version 0.16.139 provides a bounded read-only comparison of scheduler-key candidate IDs with current app and device identity listings. Each identity request has a six-second deadline and does not request device states. An ID match verifies only that the entity appeared in Hubitat's returned inventory; scheduler ownership remains unverified. Inventory completeness and performance overlaps are reported, without automatic optimisation changes.


v0.16.138 corrects a presentation bias in scheduled-job analysis: app-key jobs and device-key jobs are ranked independently from the same complete structured snapshot, not via one top-10 list which can exclude all devices on ties. The report separates confirmed explicit owner IDs, unverified key-derived candidate IDs, and rows with no candidate. The final model packet retains this full numerical coverage within the scheduler size budget, and an additional presentation check marks model-generated app/device owner labels as unverified when the source contains no confirmed owner identities. Job counts still do not establish unnecessary execution or savings.


v0.16.137 supports the live Hubitat scheduled-job key formats `devNNNOnce.method` and `devNNNRecur.method` (and corresponding app-prefixed forms). Key-derived IDs remain **unverified owner candidates** until a separate identity lookup confirms the association. It also prevents AI-generated sample tables from labelling key-derived IDs as confirmed owners when the scheduler digest has no explicit owner IDs. This remains read-only; scheduled-entry alignment does not establish CPU contention or guaranteed savings.


v0.16.136 extends the scheduled-job analyser to preserve scheduler map keys and label narrowly decoded `devNNNOnce` / `appNNNOnce` keys as **unverified owner candidates**. These are never counted as confirmed owners without explicit deviceId/appId evidence. Explicit scheduler efficiency / grouping questions now use the host performance evidence route automatically instead of general model guesswork. The performance finalizer also corrects the contradiction between successful empty LG webOS scoped log reads and model text claiming no diagnostic read occurred.


v0.16.135 adds a bounded lifecycle for read-only comprehensive performance/automation investigations: a configurable 90-second overall deadline, a separate 30-second final synthesis deadline, and a safe source-receipt-only partial response if analysis stalls after evidence collection. The UI polls minimal, session/request-ID-scoped stage updates while the request runs; disconnects and superseding questions cancel the in-flight task. HTTP request URL logs redact access tokens. Configurable options: investigation_deadline_seconds (default 90) and performance_synthesis_timeout_seconds (default 30). Rotating previously exported/leaked credentials is still necessary.


0.16.134: For whole-hub optimisation requests, the scheduled-job MCP payload is analysed before the 7,500-character model packet limit is applied. Where the hub provides structured owner IDs and handlers, the app reports per-owner scheduled-entry counts and top method groups, with explicit totals, unmapped ownership and partial-return flags. This is a read-only scheduler inventory, not CPU profiling or proof of avoidable work. If the backend does not return structured job rows, the existing fallback and coverage warnings remain.

v0.16.133 adds a final consistency check for performance investigations: failed reads against deleted app IDs 2954/2597 are treated as requests that need caller provenance, not automatic stale MCP Rule Server dependencies or cleanup opportunities, unless actual configuration was inspected. A scoped log read returning zero rows is explicitly reported as an observed absence in that sample rather than falsely described as no tool read. Performance optimisations remain read-only and require independently verified configuration and dependency evidence before recommending changes.

0.16.132 adds an evidence coverage summary to broad whole-hub efficiency reports. These reports now disclose top-N performance limits, capped recent logs, the difference between shared job timestamps and actual contention, and the fact that the existing performance planner does not independently inspect every app/rule dependency. It also catches additional variants of model-generated recommendations that incorrectly infer MCP Rule Server persistent references to deleted apps from failed lookup requests. All operations remain read-only.

v0.16.131 displays model-authored Markdown tables as native, safely constructed, horizontally scrollable HTML tables in the Home Assistant ingress UI. Numbered inspection steps are rendered as ordered lists. Evidence repair also ties generic timing-only reporting recommendations to uniquely matching measured source/signal identities where possible, and avoids attributing failed queries against deleted apps to permanent MCP Rule Server configuration when no such configuration was read. Hubitat configuration remains unchanged.


HomeBrain 0.16.130 prioritizes a whole-hub optimisation intent over the narrower health-only audit when the user asks to review all devices/apps/rules/logs for efficiency. Scheduled-job evidence is requested automatically for these optimisation reviews. A Markdown presentation repair keeps recommendation rows intact when deterministic reasoning guards insert qualifications. Evidence instructions explicitly distinguish failed MCP lookup requests to deleted apps from persistent internal Rule Server dependencies. This remains a read-only, evidence-limited inspection; results must not imply guaranteed savings or silently change Hubitat configurations.


0.16.129 broadens investigative reasoning to integration/polling failure questions. A sampled/capped log window cannot establish no past outages; model conclusions receive a final evidence check. Optional AI audit commentary now ends at a coherent text boundary. If SenseCap D1 is deliberately disconnected, set \`sensecap_d1_intentionally_powered_off: true\` in add-on options so reports classify its connectivity warnings as expected. This option is per-user and is **not** enabled globally.


In 0.16.128, HomeBrain distinguishes fast inventory questions from runtime automation troubleshooting. Targeted rule failures get a bounded investigative model loop with evidence-first guidance; broad automation failures reuse the comprehensive read-only system audit with a focused model synthesis (option: `automation_diagnostic_ai_analysis_enabled`, default true, disable to avoid additional AI latency). `comprehensive_audit_ai_analysis_enabled` still separately controls generic full-system audit AI synthesis. "Active" in returned automation rows is a normalized *configuration* category, not verification that the rule executed.


0.16.127 reconciles duplicate installed-app and Rule Machine rows by canonical Hubitat ID, preventing inflated automation counts while preserving source provenance and stronger broken-state markers. This is read-only and does not verify runtime rule execution.

0.16.126 corrects deterministic Rule Machine discovery by invoking the existing supported `hub_read_rules` wrapper with `hub_list_rules` and empty args, matching rule authoring. It qualifies discovered rows as incomplete until independently validated, treats upstream success=false as a failed inventory read, and distinguishes transport success from substantive evidence. No Hubitat mutations are performed.

0.16.125 removes the repeated app-count line from the collapsible inventory UI and clarifies that empty structured Rule Machine data from `hub_read_rules` does not mean zero rules exist. It preserves read-only behaviour and requires independent verification of Rule Machine coverage.

0.16.124 provides a brief configuration-only summary for requests to show broken automations, avoiding the full healthy app list. It qualifies empty Rule Machine tool results as incomplete coverage, distinguishes tool failure, preserves exact IDs for flagged entries, and does not equate enabled apps with verified runtime success. Other automation inventory requests retain the detailed presentation.

0.16.123 clarifies the fast automation-status inventory: it separates app and Rule Machine population counts, keeps legacy status headings and summary wording, displays available app IDs, and warns that enablement or a Hubitat broken-name marker is not proof of successful runtime execution. It recommends the existing comprehensive read-only System Check for runtime faults. This release does not yet add automatic per-action target verification or retire any Roborock rules.

0.16.122 improves the fresh System Check device inventory without reusing stale identity state or weakening online evidence. It requests a lean detailed device projection (identity, capabilities, attributes, last activity) that excludes commands and does not replace the command-capable shared cache. When the gateway reports a reliable total and page boundaries, remaining pages may be fetched concurrently through the existing MCP concurrency gate. Incomplete/mismatched pages and projection errors fall back to the original fully refreshed detailed manifest. The audit separately measures fresh device data acquisition and local health classification and reports the source and verified projection status. Live performance improvement depends on upstream pagination capabilities and has not been measured in production.


0.16.121 adds an opt-in Home Assistant add-on option `sensecap_d1_intentionally_powered_off` (default `false`). Set this to `true` while the SenseCap D1 is deliberately without power, and return it to `false` when the device is powered on. The comprehensive report labels this as user-supplied context, not an MCP-verified condition; existing warnings remain visible and repeated SenseCap scoped reads are suppressed while the option is active.

The release also groups slow `/logs/json` warnings with different numerical durations into one diagnostic pattern with observed min/max milliseconds; measures System Check stages independently (MCP health, tool inventory, device inventory, automations, initial logs, and aggregation); and adds an opt-in `comprehensive_audit_ai_analysis_enabled` option (default `false`) for one short, read-only, tool-free Gemma advisory limited to evidence-based hypotheses. The deterministic source report remains authoritative and all Hubitat write confirmation safeguards remain unchanged.


0.16.120 adds conservative log time-integrity checks: timezone-less and apparent future-dated log entries cannot establish UTC incident chronology or SenseCap recovery. Sources whose timezone metadata is absent remain unverified rather than receiving an assumed one-hour BST correction. Comprehensive audits now preserve exact device label/ID pairs for unambiguous ADB incident targeting and prioritise fresh observed failures over repeatedly querying unchanged offline status. They also provide bounded Zigbee metering and ADB follow-up guidance without inferring root causes. All diagnostic reads remain non-mutating.


0.16.119 consolidates additional scoped WARN/ERROR patterns separately from the main health-alert count, with occurrence counts, available timestamp ranges, and no inference that each row is a distinct outage. It corrects the active v3 offline-device classification (rather than its overridden frozen-core variant) to retain actual source attribute, battery and last activity when supplied. SenseCap D1 follow-ups distinguish live-push and config-push failures without claiming a common cause or recovery, and scoped log receipts show wall-clock latency. After three or more scoped log reads, the redundant unsupported historical extra request is skipped with an explicit coverage disclaimer. The audit remains read-only.


0.16.118 follows up explicit offline devices by their structured inventory IDs, shows the actual offline-status attribute, battery and last-activity evidence when supplied, and makes bounded device-scoped log requests before performance-only leads. It also retains prior SenseCap D1 HTTP 408 warnings as follow-up candidates and distinguishes explicit timestamped successful live-push records from mere absence of errors. The historical log evidence receipts now separately describe tool success and whether any returned records substantiate the requested window; zero rows cannot confirm coverage. The audit remains strictly read-only and neither identifies untraced third-party callers nor executes repairs.


0.16.117 investigates health-audit-confirmed log faults ahead of generic performance outliers (up to four bounded, deduplicated scoped reads), even when performance statistics are unavailable. It verifies returned historical-log timestamp boundaries rather than treating a successful empty response as proof of historical coverage, adds explicit SenseCap D1 live-push recovery checks, captures MCP device-list schema-validation evidence without inventing the requesting caller, and labels unmatched performance-device IDs. No automatic writes or AI synthesis are included.


0.16.116 prevents INFO/DEBUG/TRACE automation messages from becoming false log-error alerts, extracts full MCP Rule Server entry messages before truncation, separates independent alert signals from unverified *BROKEN* name markers in audit headlines, adds a single bounded older-log sample when 24h logs hit the 200-row limit, and cross-checks unmatched performance-device IDs against complete live-context inventory when available. All audit activity stays read-only and no Gemma reasoning or unattended repair is added.


0.16.115 differentiates automation *BROKEN* name markers from verified failure signals in chat reports, reconciles source-specific performance/device populations by exact sampled IDs, marks 200-row log-sample saturation, extracts concise MCP structured-error messages, and emits per-source evidence receipts and targeted read-only repair checks. This does not enable unattended Hubitat changes or add a model synthesis round.


0.16.114 routes broad chat requests for hub logs, device/app statistics and issues through the existing read-only System Check (device health, automations and grouped log warnings), then adds bounded performance leaders and targeted log follow-ups. Quiet event-driven devices are shown as observations, not automatically declared offline. No changes to Hubitat devices, apps or rules are performed by this report.


0.16.113 canonicalises model-authored temporal-history interval tables whenever deterministic `observedIntervals` are available on an otherwise safe duration answer. The first On/Off/Duration table is replaced with HomeBrain's exact 24-hour clock and `sec`/`min` rendering, preventing model rounding such as `170s -> 3m` while preserving surrounding prose and unrelated Markdown tables.

0.16.112 refines temporal-history presentation for complete semantic windows. When the retained page reaches the requested window start, HomeBrain no longer appends routine source-integrity boilerplate after an already qualified duration such as `about 3 minutes`. It instead surfaces practical scope/context such as the window start and latest recorded state/event. Strong missing-history warnings remain when retained history is known not to reach the requested start. `Currently on/off` wording is reserved for separate live-state evidence; deterministic history fallback says `latest recorded state`.

0.16.111 adds `this afternoon` as a first-class deterministic history window. It resolves to 12:00–18:00 in the authoritative Hubitat local timezone, capped at the current time while the afternoon is in progress. Explicit clock ranges mentioning `this afternoon` are anchored to today. This prevents a rolling `hours_back` fetch from leaking late-morning sessions into an answer labelled as afternoon.

0.16.110 fixes duplicate temporal-history presentation when a model draft already contains an interval table and the deterministic history safety guard inserts its canonical table. The repair path now keeps the first canonical history table, removes only later duplicate On/Off/Duration blocks and their matching retention/completeness note, and preserves unrelated analysis paragraphs or tables.

0.16.109 makes user-facing temporal durations more natural without changing stored/debug units: summary prose uses words such as `10 minutes` and `1 hour 44 minutes`, while interval tables use readable compact units such as `5 min 36 sec`. It also removes a redundant second unverified-stream estimate caveat when the deterministic history guard has already supplied the complete uncertainty note.

0.16.108 improves temporal-history answer presentation without changing history arithmetic or evidence semantics. Duration questions now prefer a concise result followed by a compact Markdown interval table and a short caveat. The deterministic duration guard uses the same structured presentation when it must repair a model answer, including retained-page boundary gaps and leading unmatched inactive events, so safety corrections no longer collapse a readable answer into one dense paragraph.

0.16.107 fixes semantic history-window coverage when Hubitat returns a retained native event list shorter than HomeBrain's requested row limit. A short retained list is no longer treated as proof that the requested window start was reached; HomeBrain now requires an event timestamp at or before that boundary. When a duration answer is based on a retained page that does not reach the window start, final synthesis explicitly says that earlier in-window transitions may be missing while preserving the existing unverified-stream estimate semantics.

0.16.106 closes a final recorded-event wording gap in synthesis validation. When a model lists timestamps that are directly present in returned device-event rows and then refers back to them with the deictic phrase `These are estimates based on recorded events`, HomeBrain now repairs that wording to preserve the timestamps as recorded observations. Source-integrity uncertainty still applies to completeness and continuity, and derived duration totals may still be described as estimates when the event stream is unverified.

0.16.105 preserves semantic history intent end-to-end. Parsed time windows such as `this morning` are copied into deterministic history-tool arguments even when the model already supplied the state attribute, making the resolved `timeWindow` auditable instead of relying only on request-local context. Final synthesis now receives the original user objective: explicit duration questions cannot silently lose the deterministic temporal total, and timestamps that are actually present in returned event rows are described as recorded observations rather than estimates. Source-integrity caveats still apply to completeness, continuity, and exact physical-history claims.

0.16.104 fixes deterministic device-history duration analysis when a caller uses a small presentation limit such as `limit: 1`. The service still returns only the requested newest event rows, but interval arithmetic now uses every matching state row from the authoritative fetched page. This prevents cases where `analysisEventCount` reports many switch events while `intervalCount` and duration incorrectly collapse to zero. Temporal source-integrity caveats and bounded presentation remain unchanged.

0.16.103 fixes open temporal-history semantics. A definite observed active transition with no later inactive row now exposes its elapsed open span separately from completed-pair totals, so an ON event is no longer collapsed into a misleading `0s` / “No bounded on interval” answer. Ongoing-window analysis also distinguishes a transition observed inside the window from a verified active state that already existed when the requested window began. Event-stream completeness remains a separate caveat: observed open spans are not promoted to proof of uninterrupted physical state or an exact total when source integrity is unverified.

0.16.101 fixes one-time cleanup rule discovery on live MCP servers. Cleanup now calls the Rule Machine gateway explicitly as `hub_read_rules -> hub_list_rules`, requires an authoritative `rules` collection before considering any deletion, and extracts only rule identity/name fields for the strict `(One-time YYYY-MM-DD HH:MM)` eligibility check. Missing or malformed list structure fails closed instead of being reported as a successful zero-rule scan.

Historical note: v0.16.100 previously made one-time-rule cleanup observable and manually testable; v0.18.429 retires the UI and background job. HomeBrain exposes the effective scheduler time, next run, last run, last trigger, last result and last error; the Web UI adds a guarded ‘Run cleanup now’ control and deletion details. Scheduler start/next-run/completion events are logged explicitly. Automatic cleanup remains strict and Hubitat-local, and there is still no destructive startup catch-up.

0.16.99 aligns immediate Internet block/unblock with the authoritative Internet-room Switch semantics already used by scheduled control. Semantic `blockInternet`/`allowInternet` intent is now compiled to real `off`/`on`, target resolution stays inside the Hubitat `Internet` room, natural names such as `M6 Ultra PC` use the same conservative room-local token matching, and verification waits for literal `switch=off/on`. The model and synthetic Internet commands are no longer involved in this immediate path.

0.16.98 keeps scheduled Internet target resolution authoritative to the Hubitat `Internet` room while making that room-local identity match tolerant of natural token order and compact model labels. For example, `M6 Ultra PC` deterministically matches `Block PC-NucBox-M6Ultra` only when that is the unique Internet-group token-subset match; ambiguous controls still fail closed. The path now reuses the longer-lived complete identity cache before refreshing the detailed device manifest, avoiding unnecessary slow refreshes when structural identity is already fresh. Global device matching, Internet `on`/`off` semantics, scheduler grammar, and one-time cleanup are unchanged.

0.16.97 gives HomeBrain-generated one-time Rule Machine schedules a bounded lifecycle. A dedicated background scheduler runs at 01:00 Hubitat local time by default and soft-deletes only expired rules whose names exactly match the HomeBrain `(One-time YYYY-MM-DD HH:MM)` convention, after a 10-minute safety grace period. Deletes use `hub_delete_native_app` with `force=false` and `confirm=true`; a failed list read deletes nothing and an individual failure does not stop later candidates. Newly created one-time rules no longer append the unreliable self-pause action.

0.16.96 makes one-time Rule Machine scheduling use the authoritative Hubitat location timezone before converting relative or bare-clock requests into dated `atTime` values. This fixes UTC-container drift such as a BST request at 09:42 being authored for 08:42. The existing `HubTimezoneResolver` supplies an IANA timezone and therefore follows GMT/BST and other DST transitions without a hard-coded offset. Confirmation wording also now states that HomeBrain configured the future self-pause action rather than claiming the rule had already fired and paused.

0.16.95 adds an explicit, empty-by-default `internet_control_aliases_json` map for Internet control surfaces that intentionally are not assigned to the Hubitat `Internet` room. A configured alias such as `{'Google TV':'Block Media-Google-TV-Streamer'}` is treated as an exact deterministic identity binding only for scheduled Internet access; HomeBrain still verifies the selected device exposes the real `on`/`off` Switch command before proposing Rule Machine JSON. No global `Block ...` prefix heuristic is introduced, ordinary TV power control is unchanged, and room-based Internet controls remain the default authoritative path.

0.16.94 aligns scheduled Internet access with the authoritative 0.16.89 switch semantics. Devices in the Hubitat `Internet` room are ordinary Switch controls: `off` means Internet blocked and `on` means Internet allowed. RuleAuthoringService now scopes semantic `block`/`allow` target matching to that room first, then verifies and schedules the real `off`/`on` command on the selected control surface. A similarly named normal device such as `Google TV Streamer (ADB)` therefore cannot steal the request, and HomeBrain no longer requires synthetic `blockInternet`/`allowInternet` commands that these controls do not advertise. Ordinary TV power schedules remain unchanged.

0.16.93 fixes capability-grounded target resolution when a narrow exact-name lookup finds the wrong control surface. When a caller supplies `required_command`, targeted candidates are now strictly narrowed to devices that advertise that command; if none do, HomeBrain uses the existing authoritative identity fallback rather than accepting an exact-but-incapable device. This lets scheduled Internet requests such as `block Google-TV-Streamer after 1 min` select `Block Media-Google-TV-Streamer` instead of the similarly named `Google TV Streamer (ADB)`, while ordinary name resolution without a required command is unchanged.

0.16.92 closes the remaining scheduled-Internet routing gap exposed by the 0.16.91 live proof. The immediate Internet-access parser now uses the same future/recurring timing guard as ordinary device control, so `after 1 min`, `in 30 mins`, `2 hours later`, absolute clock schedules, and recurring requests cannot be swallowed into the Internet device name. Those requests remain available to the deterministic `RuleAuthoringService`, while a bare immediate `block X` / `allow X` request retains the existing fast path. No Hubitat command semantics are inverted.

0.16.91 extends the deterministic `RuleAuthoringService` to relative one-time schedules. Plain requests such as `block X after 1 minute`, `turn on X in 30 mins`, and `turn off X 2 hours later` are converted directly into a dated `Certain Time (and optional date)` trigger using the host clock, then use the existing one-time self-pause safeguard. They do not ask the model to invent a Rule Machine Delay action, so a relative delay cannot be double-applied or rejected by the action-list validator. Duration wording such as `turn on X for 30 minutes` remains outside this grammar and is not reinterpreted as a delayed start. Immediate controls and the 0.16.89 Internet access-state mapping remain unchanged.

0.16.90 protects scheduled routine controls from the immediate semantic compatibility path. A command containing a valid future clock, recurrence, or duration qualifier is no longer compiled into a `timing=now` switch action before Rule Authoring can inspect it. Plain clock schedules such as `turn on X at 10pm` therefore continue to the existing deterministic `RuleAuthoringService`; immediate controls remain fast and unchanged. The guard uses the shared clock parser and deliberately preserves established level wording such as `set lamp at 50%` as an immediate brightness command. This is a routing correction only: it does not change the 0.16.89 Internet access-state semantics or invert any Hubitat on/off command.

0.16.89 gives switches assigned to the authoritative Hubitat `Internet` room/group explicit access-state semantics without changing their control behavior. For those devices only, `switch=on` means **Internet allowed** and `switch=off` means **Internet blocked**. Active switch snapshots retain the literal Hubitat state for compatibility while adding deterministic presentation metadata, and the synthesis policy requires access wording rather than interpreting a `Block ...` label as blocking being active. Room/group membership, not the device-name prefix, establishes this meaning; no extra Hubitat read or model round is added.

0.16.88 tightens device-freshness semantics so activity age is not silently promoted into a failure claim. Old `lastActivity`/activity timestamps remain neutral observations unless current evidence provides an explicit freshness expectation, while direct offline/unreachable health evidence remains actionable. Similar timestamp clusters remain diagnostic context rather than inferred integration interruptions, and the synthesis contract enforces the same evidence boundary after model generation.

0.16.87 consolidates the adaptive evidence-use path on top of 0.16.86 without expanding retrieval or adding model rounds. Each adaptive device/app diagnostic receipt now preserves the exact `hub_get_performance_stats` row that selected the target, including identity and selection rationale. A final current-turn evidence-use guard keeps explicit long-running-operation evidence separate from unproven network/connectivity causes, preserves literal WARN/ERROR observations through generic semantic repairs, and keeps same-second cluster guidance inspection-first unless configuration evidence proves a safe tuning action.

0.16.86 keeps the accepted host-planned/adaptive performance architecture unchanged and closes two evidence-intelligence gaps exposed by the 0.16.85 live proof. Hubitat long-call WARN durations may contain thousands separators such as `166,621ms`; these are now normalized and classified as real `diagnostic_signal` evidence instead of falling through to neutral observations. Adaptive busy-share eligibility also uses a 15% retrieval threshold with the existing 20% value retained as a stronger priority bonus, preventing a sustained near-threshold busy leader from being excluded by a hard cutoff while an isolated high-average row consumes the only app/device diagnostic slot.

The broad performance path remains bounded: a quiet case uses metrics, performance stats and one bounded recent-log read; a strong-outlier case may add at most one device-scoped and one app-scoped six-hour diagnostic log read. The normal path still uses zero exploratory agent model rounds and one final synthesis round. Retrieval thresholds choose evidence only; they are not user-facing health/severity labels.

0.16.85 consolidated the presentation-integrity boundary. The diagnostic validator recognizes child fields by semantic role instead of exact model labels, successful scoped evidence remains authoritative, source/signal timing facts are rendered atomically from one host record, and the older shape-dependent diagnostic rewrite is no longer chained after the format-independent validator.

For complete release history, see [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).

### Core design

- **Meaning-first control:** semantic plans describe user intent; the model never owns Hubitat device IDs, gateway payloads, or verification.
- **Host-owned grounding:** device identity, capabilities, live reads, writes, and post-write verification are deterministic and evidence-backed.
- **Current-turn evidence:** live/historical factual claims must come from this request's tool evidence, not prior assistant conclusions.
- **Fail-closed synthesis:** deterministic validators localize contradictions or unsupported causal/prescriptive claims without replacing supported analysis.
- **Bounded investigation:** history, logs, scheduler reads, and causal expansion use explicit limits and stronger evidence outranks broad fan-out.
- **Privacy-safe observability:** request metrics use a fixed vocabulary and do not expose prompts, credentials, session IDs, device names, or tool arguments as metric dimensions.

### Performance analysis contract

For broad Hubitat performance/optimisation requests, HomeBrain treats resource/performance statistics as measured findings and logs as observations.

A broad performance request that also asks for recommendations uses:

1. Host-planned `hub_get_metrics` for current hub resources and alerts.
2. Host-planned `hub_get_performance_stats` for measured app/device execution statistics.
3. One bounded recent `hub_get_logs` window (`30m`, maximum `100` rows).
4. If numeric performance rows cross internal retrieval-policy thresholds, at most one device-scoped and one app-scoped six-hour diagnostic log read (`since=6h`, `limit=120`). Near-threshold busy-share leaders may enter the bounded ranking before the stronger priority threshold; these thresholds choose evidence and are not health/severity classifications.
5. `hub_get_jobs` only when the user's objective explicitly asks about scheduler/job/polling cadence.
6. Zero exploratory pre-synthesis provider rounds for the normal broad performance+recommendation path.
7. One final performance provider synthesis pass; deterministic validators handle localized repairs without another cloud-model round.

The final answer must keep these distinctions explicit:

- High execution time, call volume, `pctTotal`, `pctBusy` and `stateSize` are measured values; they do not establish an implementation mechanism by themselves.
- Adaptive diagnostic evidence is classified before a mechanism conclusion is accepted. Explicit timeout/connectivity/failure evidence or directly observed very long calls may support a calibrated hypothesis; repeated neutral activity does not prove causality; sparse/no observations remain unresolved.
- Hubitat millisecond durations may be comma-formatted; normalization must not discard an otherwise explicit long-call diagnostic signal.
- Adaptive receipts retain the exact performance-stat row that selected the scoped target; target identity and selection rationale must not be reconstructed from prose.
- Long-running operation evidence does not by itself establish a network/connectivity cause, API-latency cause, worker-thread blocking, or user-visible delay.
- A successful target-scoped diagnostic read must never be described as "no target-scoped evidence" merely because the model changed label wording.
- Host-derived timing is authoritative. `regular_cadence`, `irregular_intervals` and `observed_gap` must remain distinct, and timing source/signal plus numeric interval values must come from the same host timing record.
- Exact event/update counts require an explicit tool/host count. A one-second cluster is not a recurring events-per-second rate and is not proof of literal simultaneity.
- Literal WARN/ERROR observations remain observations; they do not automatically explain longer-window performance totals and must not be erased by generic semantic repair.
- Configuration/implementation evidence is required before prescribing exact polling, reporting, retry, timeout, blocking-model or scheduler changes. Same-second clustering alone does not prove that staggering or frequency changes are configurable, necessary, or performance-improving.
- A threshold label in an app name plus an `Event:` payload proves event processing/logging, not that the threshold condition evaluated true or an alert action fired.
- Empty/no-active health alerts support "no active alert", not categorical "very healthy" or "no optimisation needed" conclusions.

## Setup

1. Install and configure **MCP Rule Server** on Hubitat.
2. Copy its local MCP endpoint and token.
3. Create an API key in your ollama.com account.
4. Configure the add-on in Home Assistant.
5. Start the add-on and open its Home Assistant sidebar panel.

Typical configuration:

```yaml
hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
hubitat_mcp_token: YOUR_HUBITAT_TOKEN
ollama_direct_cloud_enabled: true
ollama_direct_cloud_base_url: "https://ollama.com"
ollama_direct_cloud_api_key: YOUR_OLLAMA_API_KEY
ollama_direct_cloud_model: gemma4:31b-cloud
require_sensitive_confirmation: true
morning_health_check_enabled: true
morning_health_check_time: "07:00"
pushover_enabled: false
pushover_app_token: ""
pushover_user_key: ""
pushover_device: ""
ha_tts_enabled: true
ha_tts_notify_service: ""
ha_tts_media_stream: ""
```

The add-on uses authenticated Home Assistant ingress. The direct host-port mapping is disabled by default. Do not expose the direct port unless another authenticated access-control layer protects it.

## Multiple adult household Ollama accounts (0.17.89; opt-in)

HomeBrain can be configured with **up to three secondary Ollama Cloud identities**, owned by distinct consenting adults, *only if Ollama has explicitly authorised the intended shared use*. These settings are disabled by default. They are for service resilience, **not** for bypassing exhausted usage credits or account limits. Ollama's documented shared-credit model is its Team plan; check https://ollama.com/terms and https://ollama.com/pricing before enabling cross-person key use.

New configuration:

| Add-on option | Default | Meaning |
| --- | --- | --- |
| \`ollama_household_cloud_failover_enabled\` | \`false\` | Master permission for eligible secondary accounts. |
| \`ollama_household_accounts_json\` | \`[]\` | Masked **password-type** add-on setting with up to three separately owned account entries. |
| \`ollama_cloud_first\` | \`false\` | Set \`true\` for cloud primary, authorised cloud failover and local model as a final fallback. Default continues the existing local-first behaviour. |

Example **placeholder** JSON for the masked Home Assistant option (replace the dummy token **inside Home Assistant**, never in GitHub issues, chats, logs, screenshots or source code):

\`\`\`json
[
  {
    "id": "adult_b",
    "owner_label": "Authorised adult account B",
    "api_key": "REPLACE_WITH_ACCOUNT_B_PRIVATE_TOKEN",
    "enabled": true,
    "adult_owner_confirmed": true,
    "owner_consented_to_homebrain": true,
    "provider_shared_use_authorized": true
  }
]
\`\`\`

The three approval flags are **independent assertions**, not proof of legal or provider permission. Do not mark \`provider_shared_use_authorized\` true without actual provider authorisation for the intended cross-person use. Keep it disabled while awaiting clarification. Under-18 household members must not supply accounts.

**Routing:** With cloud-first enabled, use the existing primary cloud key. On **connect failure before request submission or HTTP 502/503/504**, try each consented and provider-authorised secondary at most once. On **HTTP 429**, auth failures (401/403), post-send timeouts, invalid JSON, interrupted streaming or incomplete responses, **never rotate to another personal account**. If the configured local Ollama model is available, it can then run as an independent fallback; otherwise show the original error. Local-first remains the default when \`ollama_cloud_first=false\`.

**Privacy:** Secondary keys are kept in add-on password settings, never sent to the browser, MCP, Hubitat or evidence journal; the model request itself does go to the selected cloud provider account. The owner must knowingly consent to receiving the shared household HomeBrain prompts, which may include device names, occupancy summaries and other household information. Account IDs/labels are configuration metadata, not authentication or user-identity verification. Do not use shared cloud keys to host separate personal/private conversations. For individual user privacy, a future authenticated user-to-account routing feature would be required.

**Observability:** The per-request technical counters track eligible failover, successful secondary use and cloud-to-local fallback without exposing the keys. No long-term token accounting or account-balance API is implemented. Failure is fail-closed if configuration is invalid; verify local access and vendor terms before activation.

## Optional local Ollama fallback

If you run `ollama serve` on a machine on your LAN, HomeBrain can try that model first and fall back to Ollama Online when it is unavailable:

```yaml
ollama_local_enabled: true
ollama_local_base_url: http://192.168.1.50:11434
ollama_local_model: gemma3:12b
ollama_local_connect_timeout_seconds: 3
ollama_local_timeout_seconds: 12
ollama_local_keep_alive_seconds: 120
```

## Browse retained journal records (0.17.82)

The Historical Journal dashboard includes a **Browse historical records** section.
Enter the exact numeric Hubitat device ID (e.g. the ID shown in recent observations), choose a local calendar date and optionally an event attribute. **Search records** displays up to 50 events per page; **Previous** and **Next** move through bounded result pages. Each row shows event/value, source type, and whether the timestamp came from the Hubitat source or collector reception. Records are read-only and app-log message bodies are not shown.

The underlying `/api/evidence-journal/events` endpoint also accepts `offset` (default 0), returns `has_more` and `next_offset`, and retains the prior `truncated`, `coverage_complete: false` and `gaps` semantics. Pagination can shift when the collector adds/removes rows, so consecutive pages are not an immutable historical snapshot. No automatic whole-hub archive search or backfill is added.

Historical focal-window planning additionally requires that the source command and requested incident date match; a previous day's source cannot supply the requested day's timezone offset.

## Persistent historical evidence journal (experimental, opt-in)

Version 0.17.25 adds a bounded local SQLite journal for live Hubitat event frames.
It is **disabled by default**. When enabled it connects read-only to the
unofficial Hubitat LAN WebSocket endpoints `/eventsocket` and (optionally)
`/logsocket`. There is no full-hub polling, Hubitat rule change, app install,
or historical backfill. These sockets are **not a supported/public Hubitat API**
and may change after hub firmware updates.

Configure the add-on under **Configuration** and restart:

```yaml
historical_journal_enabled: true
historical_journal_hub_url: "http://192.168.1.239"
historical_journal_retention_days: 30
historical_journal_max_rows: 100000
historical_journal_capture_logs: false
historical_journal_log_app_ids: ""
```

For example, set `historical_journal_capture_logs: true` and
`historical_journal_log_app_ids: "4015"` to capture only app 4015's
`/logsocket` messages in addition to selected live device events. App logs can
contain private user text; capture only explicitly opted-in IDs. Connection
errors, collection interruptions, and overflow are reported as coverage gaps.
Use the local Hubitat host only. No token or password is accepted in the URL.

Live socket events are filtered to switch, motion/presence/occupancy, level,
mode and button attributes. **From 0.17.79**, verified read-only native
`hub_list_device_events` responses are additionally persisted when enabled:
switch ON/OFF state events and supported `command-on`, `command-off`, and
`command-setLevel` events with valid source timestamps. A command's producing
Hubitat app ID and label are retained separately as source identifiers; no
unrestricted command descriptions are stored. These read-through observations
are opportunistic, **not** proof that the journal has collected every command.
Raw high-volume power/temperature telemetry is not archived.
The SQLite DB is `/data/homebrain-evidence-journal.sqlite3` inside the
add-on's persistent data directory. It survives normal add-on restart/upgrades.
Old entries are purged after the selected retention period and a row-count
limit bounds growth; neither guarantees an exact disk-size limit. Back up the
Home Assistant add-on if you need long-term preservation.

Status (also included in `/api/status`):

- `GET /api/evidence-journal/status` — connected streams, received timestamps,
  dropped rows, DB row count, collector gaps and retention settings.
- `GET /api/evidence-journal/events?device_id=7774&attribute=motion&since=2026-10-12T07:13:23Z&until=2026-10-12T07:20:23Z`
  — bounded read-only evidence (max 200 rows, at most 31 days per request,
  requires an exact device ID or app ID).

**Causal replay:** When enabled and running, HomeBrain also checks the
persistent journal for exact incident-window switch events. An archived ON
can establish an observed state transition only if the journal retained
an authoritative, timezone-aware **source event timestamp**. A reception-only
timestamp may be useful as approximate context but never proves the exact
moment of a physical change. Journal gaps and truncated records are disclosed
and not treated as evidence of inactivity. Already-expired events cannot be
backfilled from the native API. Verify collection via the in-app Evidence Journal
status panel after restarting and allow time for future events to be captured.

**Evidence limitations:** Hubitat live socket event frames may lack an authoritative
event timestamp; in that case the journal records UTC **collector reception time**,
not a verified hub execution instant. Disconnects, add-on downtime, queue overflow,
filtering and unsupported socket changes can all create unknown event gaps.
No collection is retroactive, and an empty journal window **never proves
inactivity**. Archived records are presented separately from MCP command
provenance during causal investigations. They do not, alone, identify the
initiating automation or confirm a timer fired.

### Mobile Historical Journal panel (v0.17.26)

The main HomeBrain dashboard now has a compact **Historical Journal** panel,
including on the Home Assistant mobile-app ingress view. It displays the event
and optional app-log WebSocket connection states, retained device-event and
app-log counts, SQLite disk usage (main file plus WAL/SHM), total and open
connection gaps, last received event and any storage errors. Expand the details
to see the earliest/latest retained reception timestamps, selected app-ID
log counts (e.g., app **4015**), recent collection gaps and up to 12 newest
device observations. A **Refresh journal** button reloads these values;
otherwise status refreshes alongside the ordinary dashboard (every 30 s).
No app-log message text is shown in the recent event list.

**Verifying app 4015:** With `historical_journal_capture_logs: true` and
`historical_journal_log_app_ids: "4015"`, check **App 4015: N stored** under
**Recent events and collection details**. The log WebSocket being *connected*
proves only transport availability, not that app 4015 has emitted any logs.
A count of zero can be normal if logging is disabled or no relevant app event
occurred; it must not be interpreted as proof the app never ran. Use a permitted,
normal user action to trigger the existing automation before refreshing and
checking its count. No HomeBrain diagnostic should trigger device changes itself.

`GET /api/evidence-journal/recent?limit=12` returns a read-only, bounded,
**device-events-only** sample. Raw captured application log messages remain
available only through the existing exact app-ID and time-bounded journal query,
not in the overview. Journal timestamps may be collector-received and
continuous event coverage is never guaranteed. The collector still requires
explicit enablement: the new UI does not enable any live socket implicitly.

## System Check and Pushover

`HealthAuditService` performs read-only Hub/MCP/device/battery/automation/log health checks and stores the latest snapshot under `/data`. The dashboard exposes the latest result, new/resolved findings, a manual **Run system check now** action, and **Send report to Pushover** when Pushover is configured.

## Home Assistant TTS

HomeBrain can use the Home Assistant mobile-app notify/TTS path when browser speech is unavailable. Leave `ha_tts_notify_service` empty when there is only one `notify.mobile_app_*` target; otherwise configure the desired service explicitly.

## Safety and evidence boundaries

Sensitive writes use the structured confirmation policy. Confirmed actions are revalidated before execution and mutation success is reported only from verified tool evidence.

For history and causal questions, HomeBrain separates observed state/event history, direct command or execution provenance, configuration/topology evidence, temporal correlation, hypotheses and unresolved gaps. Configuration alone does not prove a specific automation caused a transition. Temporal correlation alone does not prove who or what initiated an event.

Precise-location attributes are stripped from provider-bound tool results. Current-turn evidence is isolated per request and prior chat conclusions are not treated as live proof.

## API

These endpoints are intended to be reached through Home Assistant ingress:

- `GET /api/status` — MCP/Ollama/runtime readiness.
- `GET /api/dashboard` — cached live-state dashboard counts.
- `GET /api/health-audit` — latest stored System Check and schedule state.
- `POST /api/health-audit/run` — run the read-only System Check immediately.
- `POST /api/ask` — process a request through the unified MCP agent.
- `POST /api/chat` — compatibility alias for `/api/ask`.
- `POST /api/refresh` — refresh MCP tools and device manifest.
- `GET /health` — add-on health probe.

## Development and validation

The blocking test/release gates include Python compilation, architecture-module-map drift detection, the full pytest release gate, repository/version alignment, import analysis, release-assurance contracts, and a container smoke build.

Runtime modules under `hubitat-mcp-ai/rootfs/app/` must be documented in `docs/RUNTIME-MODULE-MAP.md`. Any runtime change requires a new add-on version and matching release notes.

For release-by-release technical history, use [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).

## Experimental opt-in paid Ollama model routing

This feature is **disabled by default**. It does not purchase credits or
change Ollama billing. Start with the existing free `gemma4:31b-cloud` account
and purchase credits manually only if you choose to run the experiment.

Home Assistant add-on options:

| Option | Initial value | Meaning |
| --- | --- | --- |
| `ollama_paid_routing_enabled` | `false` | Explicit opt-in; no paid selections while false |
| `ollama_paid_routing_mode` | `hybrid` | `hybrid`, `manual`, or `paid` |
| `ollama_paid_budget_usd` | `6.5` | Estimated USD reservation ceiling (roughly £5 at an illustrative exchange rate) |
| `ollama_paid_deep_model` | `deepseek-v4-pro` | Set `glm-5.3` for side-by-side evaluation |
| `ollama_cloud_first` | `false` | Existing option; set true if paid cloud should be attempted before an enabled local model |

Hybrid uses the free configured model for ordinary questions, Flash for
automation/history questions and the selected premium model for diagnostic
investigations. Manual only escalates when the question explicitly includes
"use paid model", "premium model", or "paid investigation". Paid mode prefers
the premium model (except simple switch commands). **All modes remain subject
to the existing tool permissions and write-confirmation checks.**

A persistent conservative **estimated** spend reservation ledger is stored at
`/data/ollama_paid_usage.json`. Reservations include model rates, a pessimistic
input-token count and 8,192 output tokens per provider round. Reservations are
not refunded on timeouts or errors to avoid accidentally replaying billable
work. The ledger is not proof of charges and is not a provider-side spending
cap; actual token charges may differ, including reasoning tokens and provider
rounding. Do not enable Ollama auto-reload, and check the Ollama usage screen.
Never delete or reset the ledger to bypass the configured limit. Existing
explicit household-account consent and failover restrictions are unchanged.

For a controlled comparison, run identical **read-only** investigations against
the free baseline, DeepSeek V4 Pro and GLM-5.3, record answer correctness,
evidence/source coverage, hallucinations, latency and Ollama-reported token
charges. No automatic benchmark execution or provider-purchase action is
performed by this feature.


Quota fallback (opt-in): `ollama_free_quota_paid_fallback_enabled: true` only escalates when an official Ollama HTTP 402/429 error contains an explicit machine-readable free-tier exhaustion code. Generic 429, text-only messages, timeouts and streaming errors do not trigger paid retries. Paid credit must already be enabled and the estimated reservation budget must permit the attempt. Current Ollama error-schema support is unverified; when the vendor supplies no qualifying code, no automatic paid escalation occurs. Keep auto-reload OFF.


### Actual model reporting (0.18.10)
API `model` reports the last successful Ollama model round, not the configured default. `metrics.model_round_details` records successful request-local provider/model pairs without credentials, prompts or tool contents. Simple status/look-up queries avoid paid model escalation unless an explicit analysis/investigation requires it.
