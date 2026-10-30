# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.18.262**.

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

0.16.100 makes one-time-rule cleanup observable and manually testable. HomeBrain exposes the effective scheduler time, next run, last run, last trigger, last result and last error; the Web UI adds a guarded ‘Run cleanup now’ control and deletion details. Scheduler start/next-run/completion events are logged explicitly. Automatic cleanup remains strict and Hubitat-local, and there is still no destructive startup catch-up.

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
