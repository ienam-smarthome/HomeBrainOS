# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.32**.

## Architecture

0.16.32 tightens and speeds the deterministic reporting-source causal path. Boundary answers now say that no command producer was **aligned with the requested transition**, avoiding the misleading implication that the device has no command history at all. Secondary controller/sensor candidate discovery now reuses a fresh authoritative identity snapshot when it contains sufficient capability and occupancy-attribute shape, avoiding a redundant whole-home live-context read; sparse occupancy metadata falls back to the existing live room filter. Event histories remain live and bounded, and causal attribution rules are unchanged.

0.16.31 removes the unnecessary provider round from initial causal room/group clarification. For an explicit switch-causal question such as `Why did hallway lights turn on?`, HomeBrain now checks the authoritative cached identity world before model routing. If the exact room + device-kind phrase maps to multiple concrete devices, it returns the same clarification choices locally, records deterministic resolver evidence, and preserves the causal objective for the existing 0.16.30 post-selection continuation. No event history is read until a concrete device is chosen.

0.16.30 preserves causal intent across device clarification and adds a hard triggered-listener attribution guard. When a causal room/group question such as `Why did hallway lights turn on?` resolves to several concrete devices, selecting one now resumes the same deterministic causal switch investigation instead of starting a generic model-led history request. Final synthesis also treats an app present only in a physical event's `triggered[]` list as downstream whenever structured `producedBy` names a bridge/device, unless separate direct producer evidence independently proves that app issued the transition.

0.16.29 adds authoritative room + device-kind recovery for history target resolution. Natural plural references such as `Hallway lights` are no longer treated as literal labels and then reduced to a generic `lights` lookup. HomeBrain now checks the exact Hubitat room against authoritative identity metadata and filters by real device kind. One matching device resolves directly; multiple matching devices are surfaced as concrete alternatives without silently choosing one or claiming the group does not exist.

0.16.28 tightens reporting-source secondary evidence selection and downstream level-recovery parsing. Motion/presence candidates must now expose the concrete live occupancy attribute that will be queried, preventing bridge child devices such as humidity/lux measurements from consuming bounded causal-history slots merely because they inherit broad capabilities. The recovery detector now recognizes both external ON -> level -> app setLevel and external ON -> app setLevel -> resulting level orderings, keeping resulting levels distinct from initial bridge levels.

0.16.27 fixes authoritative boundary provenance for short switch intervals. The generic causal timeline still uses its five-minute materiality threshold for weaker contextual reasoning, but direct structured switch-boundary `producedBy` evidence is no longer discarded merely because the observed ON/OFF interval lasted under five minutes. This prevents brief externally reported Hue/Matter transitions from falling back to slow model investigation when the boundary itself already identifies the reporting source.

0.16.26 improves bounded reporting-source candidate selection. External bridge/device cases now inspect up to two ranked controller candidates and two ranked occupancy sensors, while direct command/app-provenance cases remain unchanged. Exact Hubitat room assignment outranks label affinity; label-affinity candidates are never described as same-room, PresenceSensor outranks MotionSensor within the same basis, and derived/soft/virtual sensors lose a final tiebreak to physical-looking sources. The secondary pass also performs one bounded unfiltered subject-event read so deterministic analysis can identify external ON -> level 100 -> downstream setLevel recovery patterns and explicitly classify those app commands as post-ON recovery rather than the initiating cause.

0.16.25 adds bounded secondary correlation for external bridge/device reporting-source provenance. When a requested switch boundary has no direct command producer and is reported through a non-self device/bridge, HomeBrain now reuses several switch rows from the already-fetched subject history, performs one exact-room discovery pass, and checks at most one highest-ranked controller plus one motion/presence source. Controller and sensor histories run concurrently. The deterministic answer separates direct reporting-source evidence, controller/sensor temporal correlation, repeated upstream-compatible patterns, and unresolved hypotheses; it never upgrades timing correlation into proof of a specific automation or hub. App-produced boundaries and direct command-producer cases retain the 0.16.24 immediate fast path.

0.16.24 adds authoritative switch-boundary provenance for real integrations where a direct command row is absent or event timestamps are recorded a few milliseconds out of order. A slightly later command is accepted only when the requested switch boundary independently names the same app producer, preserving the strict anti-correlation rule otherwise. When no command row exists but a non-self boundary producer is available, HomeBrain can finalize deterministically while distinguishing an app producer from a bridge/device reporting source; device/bridge provenance is explicitly not presented as the exact initiating action. Long causal durations are also formatted as hours/minutes instead of large minute counts.

0.16.23 formalizes the direct causal-provenance fast path as capability-generic for ordinary switch devices such as lights, sockets and fans, and expands only unambiguous switch-state language. Phrases including `turned itself on/off`, `switched itself on/off`, `powered itself on/off`, `came back on`, `went back off`, `shut itself off`, and `started/stopped running` can now seed the same deterministic two-read path when one known device exposes switch state. Ambiguous non-state wording such as `stopped responding` remains on the normal reasoning path.

0.16.22 reduces the direct causal-provenance critical path without increasing Hubitat concurrency. Explicit ON/OFF causal questions now start switch history and only the requested `command-on` or `command-off` provenance read together, using the existing two-call MCP semaphore. The opposite command source is no longer fetched just for narrative context; the deterministic renderer keeps the observed interval duration from switch history. General history callers without an explicit causal transition retain the richer two-direction provenance behavior.

0.16.21 adds explicit compatibility with MCP Rule Server 4.4.1's structured device-event provenance. HomeBrain now safely accepts `producedBy` objects such as `{name, appId}` / `{name, deviceId}`, infers app/device producer type when the upstream row omits a separate type field, and preserves the new structured `triggered` list without treating list metadata as a scalar. This activates the 0.16.17/0.16.18 direct command-producer causal fast path against the upstream fix for issue #458 while retaining raw-HTML compatibility for older MCP servers.

0.16.20 keeps the 0.16.19 zero-model inventory retrieval path but makes its presentation compact and drillable. A plain `list devices` request now returns only the total plus group counts, while scoped phrases such as `list Bathroom devices`, `list unassigned devices`, or `list devices in Living Room` return names from that group only. Exact group matches win; unique partial matches are accepted; ambiguous names return deterministic group choices rather than guessing. Live-state/device-kind phrases such as `show active devices`, `list offline devices`, and `show light devices` are deliberately excluded from this structural inventory fast path.

0.16.19 makes the ingress UI substantially more compact and mobile-friendly: live summary tiles and quick actions move to the top, low-value Open sensors/Recommendations shortcuts are removed, and a local Hubitat backup shortcut is added. It also adds a zero-model whole-home device-inventory fast path. Plain requests such as `list devices` now use HomeBrain's authoritative identity cache/live-context resource and render the complete inventory grouped by room instead of making Gemma page `hub_list_devices` 50 rows at a time.

0.16.18 completes the authoritative command-producer fast path for explicit switch OFF questions. When the observed OFF boundary has an adjacent `command-off` event with `producedBy`, HomeBrain now treats that direct metadata as sufficient, renders an OFF-focused deterministic explanation, and skips historical native-log reads and provider synthesis. The matching ON producer and run duration are retained as context when available. This activates automatically once the upstream Hubitat MCP server preserves native event provenance; otherwise the existing native-log fallback remains unchanged.

0.16.17 promotes Hubitat command-event `producedBy` metadata above historical log correlation. Explicit switch-causal prefetch now reads scoped `command-on`/`command-off` event rows alongside switch history, preserves their producer identity, and can finalize a turn-on explanation directly when the ON command names its producer. This avoids slow/empty historical `hub_get_logs` queries after live logs have rolled over. Native-log provenance remains the fallback when command producer metadata is unavailable.

0.16.16 extends the zero-model causal fast path to currently-open switch intervals. A physical controller/input immediately preceding the observed ON command is sufficient start-boundary provenance for a still-open run; HomeBrain does not wait for an OFF event that has not happened yet. The answer explicitly says the interval is open and that no end-boundary corroboration or duration exists. The prefetched device identity is also persisted as the investigative subject key so later controller histories cannot be mistaken for the causal subject or trigger an empty-subject stop.

0.16.15 removes the last provider round from the strongest explicit switch-causal path. The causal prefetch now reuses its already-grounded structural device identity inside DeviceHistoryService instead of paying for another targeted device lookup. When the existing START/END native-log correlator proves the same physical controller/input immediately before both subject commands, a narrow deterministic renderer produces the final answer directly with the same provenance and mapping/person caveats. Partial or ambiguous evidence still falls back to the 0.16.14 model synthesis path. Set `causal_deterministic_final_enabled: false` to keep the prefetch but restore provider-authored final synthesis.

0.16.14 adds an identity-grounded causal subject prefetch for explicit known-device ON/OFF questions. When one authoritative device identity and a switch transition are unambiguous, HomeBrain gathers the same deterministic history and dual native-log provenance before the first provider call. Strong repeated native provenance therefore reaches the existing final synthesis in one model round instead of spending an initial model round merely choosing the history tool. Broader causal questions remain model-routed, and `causal_subject_prefetch_enabled: false` restores the 0.16.13 path.

0.16.13 fixes causal-subject receipt handoff after deterministic history recovery. When a first noisy history pass is superseded by a scoped retry for the same canonical subject, the causal timeline now ranks the corrected interval-bearing receipt above the older empty receipt while still anchoring the subject identity so later controller histories cannot replace it. This lets 0.16.12 derive both native-log boundary windows from the recovered interval.

0.16.12 promotes native Hubitat execution logs to the first causal provenance layer. Once a subject interval is established, the host derives both START and END log windows from the observed Hubitat timestamps, reads those windows in parallel, and deterministically correlates physical controller/input events -> subject commands -> state boundaries. A repeated match from the same physical controller/input at both boundaries is treated as strong temporal provenance and can finalize the causal evidence layer without weaker room/sensor/location/app discovery. App log rows that occur after the device command are explicitly classified as downstream handling rather than initiation.

0.16.11 closes the remaining empty-subject causal gap from 0.16.10. If an attribute-less causal history read infers one binary state attribute from a full mixed page but establishes no bounded interval, the host deterministically retries the same canonical device once with that inferred attribute and the 50-row ceiling before it may stop the causal investigation. The retry is host-generated, consumes no additional model round, and lets the 0.16.10 upstream switch-scoped history path recover older state boundaries hidden behind noisy metering/RTT telemetry.

0.16.10 hardens causal investigations around observed device-state boundaries. History target resolution now recovers unique minor misspellings from the authoritative identity world, switch history is scoped upstream so noisy metering telemetry cannot crowd out the older on/off boundary, causal native-log windows are host-derived from the Hubitat event timestamp and converted explicitly to UTC, broad unscoped device inventories are blocked during causal investigations, and final synthesis treats app configuration as capability/navigation context rather than execution proof.

0.16.9 narrows the MCP transport's former global request lock. Session initialization and tool-catalog mutation remain serialized, cacheable aggregate device snapshots remain single-flight, and ordinary MCP operations run through a bounded concurrency gate (2 calls by default). This lets independent per-device live reads and verified writes overlap while retaining a `mcp_max_concurrent_calls: 1` rollback setting that restores serialized ordinary traffic.

0.16.8 adds a deterministic semantic fast path for clear brightness and thermostat requests. These requests still use the same fresh host identity grounding and deterministic verified execution, but no longer pay for a provider round when the action, direction, amount, and target wording are already unambiguous.

0.16.7 adds bounded structural-identity freshness and typed multi-device semantic selections. Host grounding now expires old room/device identity, refreshes from the bulk context before falling back to the detailed manifest, and zero-model routine controls use the same fresh host grounding as model-interpreted controls. Explicit commands naming multiple canonical devices compile to one deterministic multi-device action.

0.16.6 hardens routine-control failure handling, makes multi-round provider timing cumulative, and wires the existing `rule_write_enabled` setting into both deterministic and model-driven Rule Machine write paths.

0.16.5 improves read-aloud phrasing in the web UI. Visual arrows such as `50% → 70%` are spoken as natural transitions such as “50 percent to 70 percent” instead of the speech engine announcing “right arrow”.

0.16.4 makes host-owned entity grounding independent of the model's bounded
semantic context. The planner still receives a compact capability world, but
the host now retains the complete cached identity world for final target
binding. This prevents larger installations from losing a valid room merely
because it fell outside the planner context budget.

0.16.3 adds host-owned semantic entity grounding. The reasoning model can still
interpret meaning, but it no longer gets final authority over *which* similarly
named entity the user meant. If the user explicitly names one real room and does
not explicitly name a full device label, HomeBrain binds the semantic plan to
that room when the room advertises the requested ability. Conversely, a full
explicit device label stays device-scoped. This prevents a controller named
"Hallway dimmer" from stealing a room-wide request such as "increase hallway
brightness" from the actual Hallway lights.

The capability ontology is tightened at the same time: a state attribute named
`level` alone is not evidence of a writable light. Non-Light devices need
actual level-control capability/command plus actuator evidence, and
button/controller components without `Actuator` are excluded even if bridge
metadata happens to expose `SwitchLevel` or `setLevel`. The semantic world and
the deterministic executor continue to share the same predicate.

0.16.2 hardens state-dependent semantic actions. A device can correctly
advertise a capability while its cheapest native attribute endpoint has never
reported the current value. Relative brightness/temperature now reads the
native attribute first and, only when that yields no numeric state, retries
through one fresh bulk live-context snapshot. Concurrent room controls coalesce
that fallback in the MCP client. HomeBrain still never calculates a relative
change from stale identity-cache state. If neither authoritative source has a
baseline, it returns **Needs input** with an absolute-level/setpoint suggestion
instead of a generic Failed result or guessing.

0.16.1 tightens the capability ontology used by that world model: an ordinary
Hubitat dimmer does not have to advertise a literal `Light` capability or put
"Light" in its label. Devices exposing semantic level control
(`SwitchLevel`/`setLevel`/`level`) are treated as brightness-capable unless
their identity has stronger non-light semantics such as fan speed, shade/door
position, thermostat setpoints, or audio volume. Planning and deterministic
execution now use the same brightness predicate, so a device that appears
brightness-capable to the AI cannot then be rejected by the executor merely
because it is labelled "Hallway Main" rather than "Hallway Light".

0.16.0 adds a capability-grounded semantic world model. Before a non-trivial
semantic control turn, HomeBrain projects the real Hubitat identity snapshot into
bounded room/device context containing canonical names, semantic kinds, and
abilities such as `brightness`, `heating_setpoint`, `temperature`, and
`color_temperature`. This projection deliberately excludes device IDs, raw
Hubitat command names, command parameters, and current state values. The planner
therefore knows what kinds of things actually exist without being allowed to
treat cached identity metadata as live-state evidence or author protocol payloads.

The same semantic architecture now covers heating-setpoint intent. Natural
requests such as "make Bedroom 1 warmer", "lower the living room temperature a
little", or "set Bedroom 1 to 20.5 degrees" become typed
`adjust_temperature`/`set_temperature` actions. The host then resolves only
devices that explicitly advertise a heating-setpoint ability, reads the live
`heatingSetpoint` before relative changes, clamps to the guarded setpoint range,
compiles `setHeatingSetpoint`, and verifies convergence. The default relative
temperature step is configured independently with
`semantic_default_temperature_step` (1.0 by default).

0.15.0 introduced the meaning-first `SemanticAgentCore` for routine device
control. Natural language is translated into a strict typed
goal/target/action plan before execution. Simple unambiguous commands can produce
the same semantic plan through a zero-model fast path, while freer paraphrases
use `SemanticPlanner`; both paths converge on the same deterministic
`DeviceControlService`. The model never authors Hubitat gateway names, device
IDs, positional command parameters, or verification payloads. Safety, target
resolution, state reads, command compilation, and post-command verification stay
host-owned.

Relative light changes are therefore state-dependent operations rather than
phrase patches. For example, "increase living room brightness", "make the living
room brighter", and equivalent paraphrases plan an `adjust_level` action. The
executor reads each matched light's live level, applies the configured brightness
step, clamps to 0-100, compiles the resulting absolute `setLevel` commands, and
verifies each final level. `semantic_default_brightness_step` defaults to 20
percentage points; the semantic planner can also express explicit, small, or large
relative changes. When genuine information is missing, the request outcome is
`needs_input` rather than incorrectly reporting Success.

Semantic-language quality is evaluated separately from ordinary unit tests.
`tests/fixtures/semantic_control_eval.json` contains paraphrase, safety,
scheduling, and clarification cases; `scripts/run_semantic_planner_eval.py`
runs those cases directly against the configured reasoning model without
executing any Hubitat action. This gives model/intent regressions an explicit
evaluation target instead of waiting for another live phrase to fail.

Requests outside the currently supported routine semantic domain continue into
the established unified tool loop. FastAPI sends those requests to the production
`homebrain_agent.UnifiedMCPAgent`, which delegates no-more-tools final synthesis
to `FinalAnswerCoordinator`. A `ToolDiscoveryCatalog` supplies
a fixed initial registry and expands it only from explicit structured gateway
matches. Deterministic device resolution and history are always present in that
registry; discovery cannot replace a local bounded adapter with the broader
gateway that hosts its upstream operation. Ollama Online selects native calls,
which run through `ToolExecutor` and `HubitatMCPClient`. Request-scoped evidence
receipts are sanitised and isolated by `EvidenceRecorder`; the production agent
selects `LiveEvidenceAuthority` through a context-local grounding-policy factory.
The base orchestrator keeps its normal `GroundingPolicy` constructor and direct
base-agent callers retain the original contract. No global module monkey-patch is
used, and concurrent production requests cannot leak recorders or metrics across
request contexts. Grounding retries and refusals are recorded at the authority
decision boundary rather than inferred from final messages. No regex router or
prompt-keyword tool gate controls read-versus-write behaviour.

Model-driven reads use a generic evidence-reasoning contract. Current-turn tool
results are the only evidence allowed to support live or historical factual
claims; prior assistant messages remain conversation context only. Ordinary native reads have a soft budget of three model tool rounds and eight
model-directed read executions. Analytical/causal history requests use a separate
request-local investigative profile of five rounds and twelve reads so the model
can connect heterogeneous evidence classes instead of stopping after the first
timeline. Once the active profile is spent, callable read tools are removed for
the next provider turn and the model must synthesize from the evidence already
gathered. Mutation executions are never rejected by this read budget. The older
causal sensor-hunting hint remains filtered; the larger investigative budget is
for evidence diversity, not room-wide fan-out.

A successful non-investigative device-history call that contains deterministic
`temporalAnalysis` is also an explicit evidence-sufficiency boundary. HomeBrain
finishes every call the model already emitted in that native round, then moves
directly to no-more-tools synthesis instead of opening a later round for unrelated
location, motion, rule, or diagnostics reads. Investigative history requests remain
free to gather additional current-turn evidence, including causal,
normality/expectation, comparison, and correlation questions. Those turns receive a
separate host contract: history establishes what happened, not what caused it; a
normality claim needs either an explicit baseline/expected rule or suitably cautious
wording; comparisons need the other side of the comparison; and unrelated exhaustive
reads are discouraged. Investigative reads are ordered by evidence quality rather
than fan-out: direct provenance/log evidence first when available, then subject-linked
rule/app evidence, then mode/location correlation, then same-room button/controller
event history when room discovery exposes it, then a small number of materially
relevant environmental-sensor histories. Room-filter results surface bounded
controller candidates from advertised button capabilities and suggest explicit
history attributes such as pushed, held, released, and doubleTapped. Exact room
metadata is preferred, with a conservative label-affinity fallback for button-capable
devices whose room metadata is missing or incomplete (for example a controller named
after the requested room); environmental sensors are not pulled in by that fallback.
A stronger
direct source should replace several weaker temporal correlations, not be added
after an exhaustive room sweep. Related-device history used for investigative
absence/correlation claims must name the specific attribute being checked; generic
attribute-less history is not treated as proof that an omitted capability had no
events. For well-known history attributes, the resolved device's advertised
attributes/capabilities are also checked before event-history execution: a provably
unsupported attribute is returned to the reasoning loop with the device's available
attributes instead of being used to manufacture an absence claim. Sparse/custom
driver metadata remains permissive. Gateway/sub-tool calls are also checked against live schema/discovery
compatibility before execution, so an operation discovered under one gateway cannot
be guessed through another.

For actual why/cause/trigger requests, 0.12.0 adds a host-owned causal evidence
planner. After the subject history resolves, the planner derives the subject's exact
room from structured target metadata, performs one exact-room provenance discovery,
selects the highest-ranked same-room button/controller candidate, and reads only that
candidate's strongest advertised event attribute. This planning step no longer
depends on the model choosing a particular room-filter operator. The planner then
compares controller event timestamps with subject active-transition starts and
surfaces alignments within two seconds as high-value provenance evidence. Alignment
does not identify the person who operated a control; it only raises that controller
event above weaker environmental correlation.

Once aligned controller provenance exists, the model is told not to spend remaining
budget on motion/illuminance merely to re-explain that same turn-on transition.
Remaining investigative reads should instead test downstream rule/app/log behavior
or genuinely unexplained transitions. If no controller candidate or no alignment is
found, the model can continue to the next strongest evidence class. This keeps the
model responsible for causal interpretation while making evidence acquisition
structurally reliable.

Final synthesis is a separate reasoning phase. HomeBrain builds a structured
current-turn evidence brief plus bounded excerpts of the actual privacy-redacted
tool results and places both at the end of the final no-tools context so normal
message compaction cannot hide the strongest evidence. Event-style histories such
as pushed/held/released are preserved with timestamps and descriptions instead of
being forced into binary temporal analysis. For ordinary temporal device histories,
0.12.0 also preserves command/state events that fall within eight seconds of an
observed interval boundary, so evidence such as `command-setLevel`, `command-off`,
and the associated state transition remains available to distinguish initial
provenance from downstream automation effects.

0.13.0 closes the remaining finalization split: when an investigative model turn
voluntarily stops requesting tools, the orchestrator no longer returns that draft
directly. Every investigative completion now goes through the same shared
`FinalAnswerCoordinator` used by budget/evidence stop paths, so the evidence brief,
bounded tool packet, causal timeline, and synthesis validators always run in
production.

Causal synthesis also receives a structured timeline that joins every observed
subject interval with nearby controller provenance, boundary commands, and mode/
location context. Intervals are marked MATERIAL when they are long enough or carry
direct provenance/command evidence. Final synthesis must account for every MATERIAL
row; short adjacent unresolved flickers may be grouped. A coverage validator detects
when a material row has been silently omitted and asks the model for one no-tools
repair rather than authoring the answer itself.

When boundary-adjacent device commands exist but no command-source evidence has been
checked, the tool loop gets one bounded causal-completeness retry before finalization.
That retry asks for a stronger rule/app/log source and explicitly forbids revisiting
controller or environmental-sensor history. If no stronger source is available, the
final answer keeps the command source unresolved instead of guessing. The synthesis
contract keeps the original user objective primary, asks for a chronological
multi-source explanation, and separates trigger/provenance, downstream automation
effects, weaker correlations, and unresolved gaps.

0.13.1 tightens that completion phase after live 0.13.0 validation. Boundary-near
source rows are now selected from the full fetched event page before the ordinary
newest-first evidence cap is applied, so later daytime activity cannot push an
earlier investigated `command-off` or `command-setLevel` row out of causal
synthesis. The causal timeline and evidence ledger prefer these preserved boundary
rows.

When the host has already completed exact-room controller provenance and the subject
contains boundary commands, it now enters causal completion immediately instead of
giving the provider another unrestricted device/history round. During that bounded
phase the model sees only read-only app/rule/log provenance gateways plus
`hub_search_tools`. Device history, location reads, generic target resolution, and
mutation gateways are withheld. A discovery-only round may expose one needed read
gateway; after the first non-search provenance read attempt HomeBrain moves directly
to final synthesis. This prevents auxiliary controller/device guesses from adding
latency or turning an otherwise answered investigation into an unresolved
missing-device outcome.

0.13.2 fixes two generic live-soak gaps found in the first 0.13.1 run. Semantic
history requests commonly omit an explicit state attribute; in that path the binary
attribute and interval analysis are inferred only after the local history service
returns. Boundary-event selection now runs again after deterministic enrichment, so
`boundaryEvents` is populated for inferred histories as well as explicit
`attribute=switch`/contact/motion reads.

Gateway argument inspection is also canonicalized. Evidence, grounding, and
gateway-operation validation now recognize both direct envelopes
(`{"tool":"hub_get_logs","args":{...}}`) and one-level-wrapped envelopes
(`{"args":{"tool":"hub_get_logs","args":{...}}}`) without rewriting the payload.
This keeps provenance receipts and log checks aligned with the live MCP schema.

Finally, causal completion no longer pays for fuzzy discovery merely to expose
read-only provenance gateways already returned by MCP `list_tools`. It activates a
small purpose-specific registry (search plus up to four app/rule/log/diagnostic read
gateways) and allows up to two complementary provenance reads in that single model
round before final synthesis. Routine requests keep the lean initial registry.

0.13.3 tightens the evidence boundary itself. Conversation history remains available
during normal reasoning/tool selection so follow-up wording can be understood, but
investigative final synthesis now receives only the system prompt plus messages from
the latest real user turn onward. Prior user/assistant conclusions are deliberately
excluded from the final no-tools reasoning pass because conversation is context, not
current-turn evidence.

For causal requests, the resolved subject history is also a hard prerequisite for
provenance expansion. If the current-turn subject temporal analysis establishes no
bounded active interval in the requested window, HomeBrain stops before same-room
controller/sensor/location/app/log expansion, records `causal_subject_empty_stop`,
and finalizes from the current-turn subject evidence. An unverified zero does not
prove the device stayed inactive, but historical controller events from another
period can no longer resurrect a causal timeline that the subject history did not
establish in this request.

0.13.4 makes empty/partial history answers auditable rather than merely safe.
`windowEvents` now preserves bounded source rows that actually fall inside the
requested semantic time window independently of interval construction and the
ordinary newest-first event cap. This means an unverified zero-interval history can
still retain commands such as `command-setLevel` and `command-off` that occurred
inside the window without pretending they prove an active state interval. The final
evidence ledger renders those rows when no bounded interval exists.

Source attribution is also validated: a draft that says "the logs show..." is
repaired when no native log source was checked and the claim actually comes from
device-event history. Finally, generic investigative history requests begin from the
fixed local history registry without fuzzy `hub_search_tools` discovery or an
upfront app manifest. Explicit requests for logs/rules/apps/automation still keep
normal discovery, and later causal completion can activate the bounded provenance
registry if subject evidence warrants it. Successful use of this path increments
`history_known_tool_fastpath`.

0.13.5 turns that bounded completion into a fixed causal evidence pipeline. Once
the subject history establishes real transitions, HomeBrain gathers the
highest-ranked same-room controller evidence and the hub location/mode stream
host-side, with location events clipped to the same semantic history window. It
then switches immediately to one read-only provenance round for installed
log/rule/app gateways before final synthesis. Installed provenance readers are
offered directly; `hub_search_tools` is a fallback only when no suitable reader
exists.

Write semantics are also separated from fail-closed unknown-tool safety. An
undeclared model function remains non-executable, but it no longer marks an
otherwise read-only request as a write. Explicit user mutations and real declared
mutating tool selections still activate the unverified-mutation guard.

0.13.6 makes causal correlation boundary-directional. Controller/button events
are classified against the nearest observed START or END boundary; an END-aligned
physical event can support turn-off/end provenance but is never exposed as the
cause of the earlier turn-on. The causal timeline renders START provenance and
END-controller evidence separately, and a deterministic synthesis validator repairs
drafts that cross those roles.

Unverified histories also retain unbounded/open active transitions explicitly.
An active transition with no observed closing transition becomes a material OPEN
timeline row with its recorded start time and no invented duration. When material
turn-on rows remain unresolved, HomeBrain loads installed app identities as
navigation context before the single provenance round so the model can inspect
logs and one relevant app/rule detail in the same round instead of spending a
later round listing apps.

0.13.7 adds one final bounded evidence-selection step for unresolved causal
turn-ons. Exact-room discovery now identifies devices that explicitly advertise
MotionSensor/PresenceSensor capabilities. After controller evidence is checked,
HomeBrain may read exactly one highest-ranked motion/presence history when material
START transitions remain unresolved. Lux/temperature-only sensors are not eligible.

The selected sensor is correlated against subject START/END boundaries with signed
timing. Tight repeated START alignment and bounded delayed-off END alignment are
surfaced deterministically. When multiple starts show the subject changing before
Hubitat records the sensor active edge, synthesis may treat that ordering as
evidence against a Hubitat automation reacting to that recorded edge and as support
for a possible upstream/outside-Hubitat trigger. It must not name a specific
external hub or automation without independent topology/configuration evidence.

0.14.0 adds a deterministic operational health layer independent of the
conversation/model loop. `HealthAuditService` checks MCP/hub reachability, the
detailed device inventory, explicit offline/unreachable device states, low
batteries, normalized automation status, firmware-update status from the Hub Info
device, and native diagnostic logs from the previous configurable number of hours.
Recurring log warnings/errors are grouped so repeated copies become one finding
with an occurrence count. Disabled automations are reported in counts but are not
treated as faults; broken, paused, and unknown automations are attention items.

Every audit is persisted under `/data` with the previous snapshot so the dashboard
can show new and resolved findings without rerunning the audit on page load. The
same service backs a manual **Run system check now** button and
`/api/health-audit` endpoints. `MorningHealthScheduler` runs the read-only audit
daily at the configured local time using the Hubitat timezone, with a bounded
post-start catch-up window. The WebUI shows health status, attention/new/resolved
counts, device count, last-check time, next scheduled run, and expandable findings.
No health check performs a device, rule, firmware, or hub mutation.

0.14.2 turns that operational monitor into a deterministic diagnostic summary.
The device inventory now includes `lastActivity` when the MCP server supplies it.
Explicit offline states remain authoritative and separate from old event times.
Periodic telemetry older than the configured threshold is suspiciously stale;
buttons, passive sensors, presence devices, and otherwise static devices are
classified as quiet rather than offline. Long-active motion, normal long-lived
occupancy, and devices that have never reported are retained as separate classes.

Stale periodic devices from the same identifiable subsystem are correlated when
three or more stop reporting within the configured time window. For example,
several Tasmota/MQTT power devices going quiet together become one possible MQTT
bridge interruption, with the affected devices listed below it. Log fingerprints
remove timestamps, UUIDs, request/correlation IDs, volatile numeric IDs, and other
changing fields before grouping. Each group retains occurrence count and first/
last-seen timestamps. The dashboard presents independent Hub, Devices,
Automations, and Logs health so peripheral findings do not imply that the hub
itself is unhealthy.

0.14.3 refines those live results. Periodic telemetry that has only just crossed
the stale threshold is retained as a candidate and must remain stale on the next
audit before becoming an individual warning. Telemetry older than the separate
long-term threshold is labelled as possibly unused, disconnected, or obsolete
instead of looking like an ordinary delayed check-in. Google TV/FireTV ADB shell
timeouts receive a stable, readable summary, and automation findings preserve the
bounded raw status evidence and reason supplied by Hubitat.

Issue snapshots now carry a schema version. After an upgrade that changes issue
fingerprints, the first check establishes a fresh comparison baseline instead of
showing false new/resolved changes. The following check resumes normal change
tracking.

The scheduled morning result can optionally be sent directly to Pushover. The
notification contains the Hub/Devices/Automations/Logs hierarchy, totals, and the
top actionable findings. Delivery is attempted only for scheduled checks; manual
checks do not notify. A delivery failure is recorded separately and never discards
the completed audit.

0.14.4 adds a dedicated **Send Pushover test** button beside the manual System
Check button. It sends a clearly labelled test notification using the stored
add-on credentials without running or changing the health audit. Success and
failure are shown directly on the System Check card.

0.14.5 changes that manual action from a placeholder test into **Send report to
Pushover**. It delivers the latest stored System Check using the same hierarchy,
totals, and leading findings as the scheduled morning notification. If no report
exists yet, HomeBrain asks the user to run System Check first.

Deterministic safeguards are validators, not answer authors. Duration/cardinality,
checked-source, close mode-correlation, and causal-timeline coverage checks are
applied locally. If the model draft conflicts with one of those invariants, HomeBrain
gives the model one no-tools repair pass with the evidence brief/timeline and
localized correction baseline. Whole-answer history fallback is reserved for
genuinely single-source simple history queries; multi-source investigative answers
are never replaced by a duration sentence.

The production wrapper also owns deterministic live-soak safeguards. Common
routine light/switch commands are sent through the bounded local control adapter
before the model can expand a generic noun into one particular device. Exact
contact-history requests remove presentation-only leading articles before target
resolution, and “why did ... open/close” answers select the relevant contact event
while explicitly stating that event history does not identify causation. Contact
event timestamps are rendered as natural local date and time text while preserving
the authoritative timestamp value and offset. Browser-session history references
support deterministic “before that” and “after that” follow-ups, including
pronoun-only forms such as “When did it open before that?”. Calendar-day filters
count or list yesterday's contact events without model arithmetic or generic event
dumps, and those aggregate/list queries do not replace the last single-event
reference. Ambiguous device choices are retained per browser session, including
choices recovered from deterministic unresolved messages, so a pronoun-only
clarification stays `unresolved` and repeats the choices before any provider call.
Deterministic read and routine-control outcomes use `DirectOutcomeContext` to own
request-local evidence, choices, request class, and mutation state, restoring every
context token on both normal completion and failure.

Contextual current-state follow-ups for temperature, humidity, battery, and power
use the explicitly selected clarification device and bypass provider synthesis.
Active and inactive motion-sensor list/count questions use deterministic live
device filtering, keeping these bounded reads at Hubitat latency with zero model
rounds and zero tool-discovery calls. Room-level attribute reads are intercepted
before the provider loop and filter candidate devices by the requested capability.
Multiple valid sources return deterministic clarification choices, while a single
capable source returns a direct current-state answer. Explicit selection phrases
replace the browser-session target without model involvement, and live values are
refreshed from authoritative Hubitat state before each current-state response.
The WebUI preserves the original requested attribute when a clarification button
is tapped, so selecting a device resubmits a deterministic named-attribute request
instead of a bare label that would enter the model loop. For other ambiguous
history/reasoning questions, the WebUI now preserves the entire original question
and appends the exact selected device, so phrases such as `last night` and `during
the night` survive clarification instead of degrading into an unbounded 24-hour
follow-up.

Resolved target identity is also request-local. When one deterministic adapter
successfully resolves a device, HomeBrain caches that exact target under the active
request identity and indexes it by the successful user wording plus its id/name/
label. A later adapter in the same request can reuse the target without repeating a
targeted `hub_list_devices` lookup; successful reuse increments
`resolution_cache_hit`. Complete device-filter results seed the same cache by their
exact returned labels/ids.

0.12.0 makes that cache metadata-aware. For a typed history read, a sparse
context target can still be reused immediately when its advertised capabilities
positively authorize the requested history dimension—for example `MotionSensor`
authorizes `motion`. When the sparse target does not positively advertise the
required capability and lacks current attribute metadata, history deliberately
misses that cache entry, refreshes the detailed target, and only then decides
whether the requested attribute is supported. This prevents a sparse illuminance/
temperature record from bypassing the unsupported-motion guard without adding an
extra lookup to already-proven MotionSensor targets. The refresh is exposed as
`resolution_cache_metadata_miss`. The cache never crosses request boundaries and
still checks required command capability before reuse.

The live device layer separates common state from richer device metadata. On MCP
servers that expose `hubitat://context`, `HubitatMCPClient` reads that resource as
a two-second, generation-fenced snapshot. The upstream resource is specifically
built from one bulk Hubitat inventory read and returns device id, label, room,
capabilities, and the common live attributes used by aggregate questions. Concurrent
context readers share one in-flight request. Every mutation invalidates the same
snapshot generation; a pre-write context response is rejected rather than reused
as post-write evidence. If the resource is unavailable, partial, truncated, or has
incomplete device identity coverage, HomeBrain falls back to the established full
inventory path instead of weakening an exhaustive claim.

This bulk path is selected from structured data requirements, not prompt wording.
Active rooms require `motion` and `switch`; active lights and non-light switches
require `switch`; deterministic attribute filters use the resource when the
requested value is a declared live-state field or a structural identity field such
as room, label, id, or capabilities. This lets investigative same-room discovery
avoid a detailed whole-hub inventory read. Filter matches expose compact capabilities
and seed request-local target identity for later exact history reads. Numeric
aggregate queries such as top/highest/lowest/count power, battery, temperature,
and humidity use the same complete bulk live-context path when the requested
attribute is covered, avoiding an unnecessary full detailed inventory read. An
unsupported or partial context resource still falls back to the complete inventory
path. Once a request has a complete, non-empty canonical power/energy aggregate,
request-local execution policy rejects later model attempts to re-run the same
question through generic `value`/`valueStr` fields; those fields remain available
only when the canonical measurement returned no usable rows. This prevents a valid
bulk-context result from turning into an unnecessary ~30-second detailed inventory
read. Attributes outside that contract remain on the complete inventory path. The
active-room definition is unchanged: `motion=active OR light switch=on`. The
resource's compact `attributes` map is normalized to `currentStates` so richer
typed/unit-bearing metadata can still be merged by device id without stale
metadata overwriting fresh live values.

Final synthesis also receives a compact current-turn evidence ledger whenever a
request gathered multiple material evidence classes. The ledger is built from the
request-scoped evidence receipts rather than conversation memory and states which
device histories, location/mode history, logs, rule/app reads, filters, and live
context were actually checked. Checked source presence is separate from evidentiary
strength: a source can be present without proving causation. The final prompt therefore
cannot legitimately say that a checked sensor/location/log/rule source was "not
provided" merely because the turn was long or context was compacted. Location-event
receipts expose bounded event details as well as their count, making mode correlations
used by the final answer auditable in the API evidence. Temporal history receipts now
also expose the bounded observed interval list (start/end/duration, capped for output),
so final synthesis can distinguish an exhaustive interval count from a summary of only
the longest or most notable periods.

At the serialization boundary, a narrow source-consistency guard backs up the ledger:
if the final prose explicitly says a sensor/related-device, location/mode, log, rule/app,
or device-history source was not provided/checked while successful current-turn
receipts prove otherwise, only that contradictory sentence is replaced. The
replacement says the source was checked but did not by itself establish a cause; it
does not manufacture a causal conclusion. Claims such as "no motion events were
recorded" remain untouched because they describe the contents of a checked source,
not the absence of the source itself.

Final history serialization keeps deterministic duration safety without erasing
unrelated analysis. For unverified event streams, a correctly rounded duration is
left alone when the model explicitly presents it as an estimate/recorded observation.
If the model states a wrong or exact-looking total, only the unsafe duration/
continuity sentence is replaced with the deterministic recorded-row estimate; other
current-turn observations and carefully hedged correlations remain intact. A separate
interval-cardinality guard prevents exhaustive wording such as "two separate periods"
when deterministic evidence contains five observed bounded intervals, while allowing
explicit subsets such as "the two longest periods". Zero unverified histories retain
the stricter deterministic serializer because missing transitions can otherwise turn
an apparent zero into a false absence claim. Attribute-level source-absence wording
such as "no recorded motion data" is likewise rewritten to the bounded zero-history
statement when the corresponding unverified motion history cannot prove absence.

The WebUI dashboard uses the same bulk live-context snapshot for its 30-second
state poll rather than forcing a detailed device-manifest refresh each time. Rich
hub-information decoration is taken from an already-cached detailed manifest when
one exists; the dashboard does not create a detailed refresh solely for decoration.
An explicit `/api/refresh` still refreshes MCP tools and the detailed manifest.
Detailed inventory remains the source for command metadata, measurement units,
health/alert fields, target resolution that needs richer metadata, and other reads
whose requirements are not covered by the context resource.

Hubitat device-list projection semantics are centralized in `device_read_contract`.
The upstream MCP server has two distinct live-state result contracts: compact
summary reads expose `currentStates`, while detailed reads expose the same reported
state as `attributes`; requesting capabilities or commands promotes a projection to
detailed mode. `HubitatMCPClient` normalizes every projected `hub_list_devices`
request at the protocol boundary, independent of prompt wording, model choice, or
which local adapter initiated it. It also validates that every record in a non-empty
projected response contains the promised state container. A structurally incomplete
response is treated as a read failure rather than as proof that all devices are
inactive, allowing the established authoritative fallback to run. The cached
detailed device manifest is built from the same contract.

`RequestMetrics` wraps the maintained production request path. It records model
rounds, provider time, evidence-backed tool calls, exact tool-discovery calls and
cumulative discovery duration, cumulative remote MCP duration, actual MCP retry
attempts, grounding retries and refusals, confirmation queuing and expiry,
confirmed Rule Machine verification duration, verification failures, ambiguous
and missing device resolutions, cancellation, total duration, and the final
request outcome. It also exposes MCP lock-wait, MCP HTTP, and MCP shared-read-wait
durations, so time spent awaiting another already-running manifest/snapshot is no
longer hidden inside a local tool's elapsed time. Completed-request classification
is delegated to the pure `request_outcome_policy` module, which applies an explicit
fixed precedence to privacy-safe counters only. A grounding refusal is labelled
`refused`; a mutation verification failure is labelled `failed`; a recorded
cancellation is labelled `cancelled`; expired confirmations and deterministic
ambiguous or missing device resolution are labelled `unresolved`. The policy never
inspects user or model text. Local adapters are excluded from MCP timing. Its fixed
metric vocabulary rejects dynamic labels so device names, prompts, credentials,
and tool arguments cannot become metric dimensions. Metrics are returned on the
production `ObservedAgentOutcome` without changing the original result fields.

MCP retries are counted at the transport loop immediately before an actual retry
POST begins. Transport failures and retryable HTTP 5xx responses share the same
counter, while cancellation during backoff does not count a retry that never
started. Retry eligibility remains governed by the existing read-safe transport
policy.

`api_response_builder.build_agent_response` is the live serialization boundary
for `/api/ask`. It preserves the existing response fields, deep-copies evidence
and metrics, supports legacy outcomes without metrics, and never adds prompt,
session, or request identifiers to the response payload. It returns privacy-safe
`metric_rows` plus an optional fixed `outcome_presentation` object containing the
normalised outcome value, human-readable label, and tone token for WebUI styling.
The response includes model metadata only when request metrics confirm at least
one model round, so deterministic responses no longer imply that Gemma participated.
For deterministic device-history proof this boundary rejects both an explicit
numeric total-duration claim that contradicts the pre-computed temporal total and
a named `no data`/`no history` sentence when the same current-turn evidence proves
one or more intervals. Corrected evidence receipts mark that a final-answer
correction was applied.

`technical_metrics_presenter.present_request_metrics` converts only the fixed,
privacy-safe request metric vocabulary into compact technical-detail rows. It
reads the production `counters` and `timings_ms` maps, omits zero or unavailable
values, and ignores unknown keys so prompts, device names, session identifiers,
tool arguments, and dynamic labels cannot become visible metric rows. The same
module exposes a fixed outcome-presentation contract for the five supported
request outcomes, giving WebUI rendering stable labels and tone tokens without
duplicating outcome policy in JavaScript.

The WebUI consumes only that fixed `outcome_presentation` object and renders a
compact response badge for success, unresolved, refused, cancelled, and failed
outcomes. Labels are inserted with DOM `textContent`, tone classes are restricted
to the fixed positive, warning, neutral, and critical vocabulary, and legacy
responses without outcome metadata continue to render normally.

`ProviderTokenEstimator` supplies deterministic, dependency-free approximate
token counts for known model families and a conservative default profile.
`TokenAwareModelContextPolicy` applies those estimates only as an additional
stricter production ceiling. Existing configured character limits remain hard
caps and direct base-agent callers retain the original `ModelContextPolicy`.

`ConfirmationPolicy` makes bounded decisions from structured tool effects;
sensitive MCP mutations require an explicit, session-scoped confirmation kept
by `ConfirmationStore`. Expired pending confirmations are removed and counted at
the store boundary; a normally returned expired confirmation is classified as
`unresolved`, while read-only and routine gateway operations do not require
confirmation.

After a valid confirmation is consumed, `ConfirmedActionCoordinator`
revalidates and executes the immutable action group. Rule Machine writes are
sequential, fail closed on the first unverified result, record verification at
that exact boundary, and use deterministic ID-and-health reporting rather than
model-generated success claims.

`ModelContextPolicy` applies the conversation-history and cumulative
tool-result budgets to copied provider payloads. It never mutates the
authoritative transcript, evidence, confirmation state, or tool results.

Common daily Rule Machine windows are compiled by `RuleAuthoringService`, not
by model-generated JSON. It uses bounded target lookup, shared fuzzy-safe name
resolution, advertised-command verification, duplicate checks, two atomic
rules, the normal structured confirmation gate, and healthy-result
verification. Advanced rule shapes continue through native MCP discovery.

Hub firmware and resource questions use `HubInfoService`, which refreshes the
Hub Information Driver, polls a bounded number of times, reconciles its cached
identity with live attributes, and returns one authoritative structured
snapshot.

Named-device history questions use `DeviceHistoryService`. It resolves one
device through the shared fuzzy-safe resolver and reads a bounded, optional
attribute-filtered event window from Hubitat. An exact multi-word target miss gets
one bounded broader targeted lookup using the final identifying token; any broader
match is surfaced as a clarification candidate and is never silently substituted.
Missing and ambiguous history targets are reported separately. For state-pair
attributes such as switch, contact, motion, lock, and valve, deterministic temporal
analysis pairs complete intervals and pre-computes totals, longest duration,
continuity, and boundary coverage. Successful history reads then return to the
model for one answer-synthesis round so it can answer the user's actual question
from those grounded derived facts instead of ending at a generic event dump. The
same pre-computed totals are copied into bounded evidence `details` so technical
output exposes `totalActiveDuration`, `totalActiveSeconds`, `intervalCount`,
`longestActiveDuration`, and coverage without dumping the full event stream.
Analytical attribute-history calls without an explicit time window keep the
normal 24-hour bound; the automatic seven-day widening is reserved for explicit
small (1-3 event) point lookups such as “when was it last on/open?”. This prevents
an old unmatched boundary event from turning a complete duration into an
unnecessary lower-bound answer, while preserving the deeper lookup used for true
“last occurrence” questions.

For semantic calendar phrases, `history_time_windows` binds the original
request to an explicit local-time interval before tool execution. Supported
phrases are `last night`, the common equivalents `during the night`, `overnight`,
and `through the night`, plus `yesterday`, `this morning`, `since midnight`,
`today`, and explicit `between <clock> and <clock>` ranges. `last night` has one
stable, auditable definition: 18:00 on the previous local calendar day through
08:00 on the current day, capped at the current time if that overnight window is
still in progress. An explicit clock range overrides that default. The
authoritative local timezone is read from the Hubitat MCP Rule Server's
`hub_get_info.timeZone` IANA identifier and cached briefly; container UTC is never
preferred when Hubitat reports its own timezone. Device resolution now happens
before that timezone read, so an ambiguous or missing history target can return its
clarification without paying for `hub_get_info`. The upstream Hubitat API still
receives one bounded `hoursBack` read; HomeBrain widens it only far enough to reach
the requested start plus a boundary buffer, using absolute UTC elapsed time for
the fetch bound so autumn DST fallback cannot under-fetch, then clips interval
arithmetic locally to the requested start/end.

History page coverage and history-source integrity are separate concepts.
`sourceCompleteToStart` / `sourcePageCompleteToStart` mean only that the returned
Hubitat page reaches the requested boundary; they do not prove that every physical
device transition was persisted in `hub_list_device_events`. Until an independent
cross-source check verifies that event stream for a request/device, HomeBrain marks
its integrity as `unverified`. It does not extend a predecessor state to the
window start, does not synthesize a predecessor from a later transition, and does
not extend an unclosed active state to the window end. Explicit first-transition
inference may be retained as diagnostic context, but it cannot upgrade coverage to
complete while source integrity is unverified.

Accordingly, paired state rows are exposed as an `unverified-event-stream`
estimate, not as an exact total and not as a mathematical lower bound: omitted
off/on transitions can make a paired span either too large or too small. Exact
window start/end, Hubitat IANA timezone, UTC offsets, timezone source, page coverage,
source-integrity status, source/analysis event counts, inferred-attribute status,
first-window/predecessor state evidence, and deterministic row-pair calculations
are included in bounded evidence details. The final serialization guard rewrites
unsupported exact-duration, continuity, and absence claims to match that evidence.
For a single successful history receipt with zero bounded intervals and an
unverified event stream, the serializer no longer relies on English phrase
detection at all: it emits the deterministic uncertainty statement directly, so
wording such as "no record of it being on" or "all activity happened later" cannot
bypass the evidence boundary. Reported transitions remain evidence of what the
event source recorded, never proof of who or what caused the change.

Final device-claim grounding is deliberately non-blocking with respect to the
Hubitat inventory. After synthesis, the agent validates named-device claims using
id/label pairs already present in this turn's structured tool results plus any
detailed manifest that is already cached. It never refreshes the complete device
manifest solely for that auxiliary final-answer check. This preserves the mismatch
retry/refusal guard when the relevant identities are already known while avoiding
a hidden multi-page inventory read after a targeted history or device query has
otherwise completed.

Resolved device targets preserve structured measurement units from Hubitat and
supply conservative standard units for common attributes when the gateway omits
them. This keeps named temperature, humidity, battery, and power answers tied to
explicit evidence rather than model inference.

## Setup

1. Install and configure `MCP Rule Server` on Hubitat.
2. Copy its local MCP endpoint and token.
3. Create an API key in your ollama.com account.
4. Configure the add-on:

   ```yaml
   hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
   hubitat_mcp_token: YOUR_HUBITAT_TOKEN
   ollama_direct_cloud_enabled: true
   ollama_direct_cloud_base_url: https://ollama.com
   ollama_direct_cloud_api_key: YOUR_OLLAMA_API_KEY
   ollama_direct_cloud_model: gemma4:31b-cloud
   require_sensitive_confirmation: true
   morning_health_check_enabled: true
   morning_health_check_time: "07:00"
   health_check_log_hours: 24
   health_check_low_battery: 20
   health_check_stale_hours: 24
   health_check_long_stale_hours: 168
   health_check_cluster_minutes: 15
   health_check_motion_active_hours: 2
   pushover_enabled: false
   pushover_app_token: ""
   pushover_user_key: ""
   pushover_device: ""
   ha_tts_enabled: true
   ha_tts_notify_service: ""
   ha_tts_media_stream: ""
   ```

To receive the morning result in Pushover, register a Pushover application and
copy its application token plus your user key (or a delivery-group key) into the
three `pushover_*` options above, then set `pushover_enabled: true`.

For reliable answer speech inside the Home Assistant Android companion app,
HomeBrain can send native mobile-app TTS through the Home Assistant Core API. The
add-on requests both Home Assistant Core API access and the compatible Supervisor
API token grant (`hassio_api: true`, `hassio_role: default`) because some
live Supervisor installations do not inject `SUPERVISOR_TOKEN` with the Core API
flag alone. HomeBrain also accepts the legacy `HASSIO_TOKEN` environment name as
a compatibility fallback without exposing either token.
Leave `ha_tts_notify_service` empty when Home Assistant has exactly one
`notify.mobile_app_*` service and HomeBrain will auto-discover it. When several
mobile-app services exist, HomeBrain also tries to match the Android device
model from the current WebView user-agent (for example `SM-S938B` to
`notify.mobile_app_sm_s938b`) before asking for an explicit target. You can
still set the option explicitly, for example `notify.mobile_app_sm_s938b`. Leave `ha_tts_media_stream` empty to use the
companion app default music stream, or set `alarm_stream` / `alarm_stream_max`
when that behaviour is specifically wanted. Normal browsers continue to use
browser speech first; Android WebView prefers the Home Assistant native TTS path.

5. Start the add-on and open its Home Assistant sidebar panel.

### Optional: local Ollama first, cloud as fallback

If you run `ollama serve` on a machine on your own network, you can have
the add-on try it first and only fall back to Ollama Online when the local
instance is off or unreachable -- useful for cutting response latency when
local hardware is available, without losing the reliability of the cloud
path when it is not.

```yaml
ollama_local_enabled: true
ollama_local_base_url: http://192.168.1.50:11434
ollama_local_model: gemma3:12b
ollama_local_connect_timeout_seconds: 3
ollama_local_timeout_seconds: 12
ollama_local_keep_alive_seconds: 120
```

This is opt-in and off by default. When enabled, every model round trip
tries the local instance first. The timeout is deliberately split in two
rather than one flat number:

- `ollama_local_connect_timeout_seconds` (default 3s) bounds how long it
  waits to reach the local instance at all -- if it's off or unreachable,
  this fails fast and falls back to the cloud path quickly.
- `ollama_local_timeout_seconds` (default 12s) bounds how long it waits for
  a response *after* connecting -- generous, because Ollama loads a model
  into memory on first use after being idle, and that cold load alone can
take several seconds. A single flat timeout would either be too long for
"nothing is listening" or too short for "just woke up and is loading."

There is no persistent "local is down" state -- if the local instance comes
back online, the very next request uses it again automatically.

`ollama_local_keep_alive_seconds` (default 120s) is sent as Ollama's own
`keep_alive` option on local requests, so the local model unloads from
memory after that many idle seconds instead of relying on Ollama's own
default (5 minutes). Set it lower to free memory sooner, or higher to keep
it warm longer across bursts of use. It's never sent to the cloud endpoint.

`GET /api/status` reports `ollama.local_configured` and `ollama.local_model`
so you can confirm it is wired up correctly.

The add-on uses authenticated Home Assistant ingress. Its direct host-port
mapping is disabled by default so the control API is not exposed to the local
network independently of Home Assistant. Do not enable a direct port mapping
unless an authenticated reverse proxy or equivalent access control protects it.

Short room/device measurement phrases such as **bathroom temperature** and
**Bedroom 1 humidity** now use a deterministic attribute-first path. HomeBrain
reads the live measurement snapshot, matches both device label and room metadata,
and only falls back to device-name resolution if no capable reporter matches. This
removes client-to-client model variance and avoids a false unresolved outcome when
a valid room sensor is already present.

Immediate dimmer-level requests such as **set living room lights to 100%** now
use the deterministic routine-control path, send Hubitat `setLevel` parameters in
the required positional array, and retain live level verification. Batched raw
`hub_call_device_command` proposals are also classified from every contained
command, so routine `setLevel` batches no longer inherit the gateway's destructive
hint and ask for an unnecessary confirmation. Failed confirmed writes now mark the
request outcome **failed** instead of leaving a contradictory green Success badge.

Routine device writes now also use a nonblocking local identity fast path for
unique exact cached targets. A cold identity lookup prefers the complete bulk
`hubitat://context` resource before falling back to the heavier detailed device
manifest, so a simple light command no longer needs to wait for a full
`hub_list_devices` refresh when sufficient identity is already available.

The WebUI puts the Ask/Speak/answer card directly below the page heading so the
primary interaction is immediately reachable on mobile. Ask and Speak share one
compact 50/50 action row, and the runtime MCP/Ollama/model status pills use a
smaller compact treatment to reduce vertical space. It also includes live
dashboard tiles, a persistent System Health card with a compact status badge, a
manual **Run system check now** button, a manual **Send report to Pushover**
button, smart-home shortcuts, optional read-aloud answers, outcome badges,
response metadata, copy, and expandable technical details. Answer speech now
falls back to Home Assistant companion-app native TTS when browser/WebView speech
is unavailable, and Android WebView prefers that native path. TTS failures now
show the backend reason directly on the Read answer button instead of only a
generic setup warning. Because browser speech is more reliable than Android
WebView speech on some phones, the Home Assistant Android view also shows a compact
**Open in browser** shortcut beside the read-aloud option. It launches the current
HomeBrain Home Assistant panel in the device's external/default browser using the
Android intent path, while normal browsers keep their existing behaviour. Direct current-time questions are answered
algorithmically from the Hubitat location timezone rather than delegated to the
language model. System Health separates Hub, Devices,
Automations, and Logs, groups recurring log signatures, and shows correlated
stale-device clusters. Detailed findings omit redundant WARNING prefixes. To
reduce visual noise, only device names and their state/value are coloured in the
Devices section; surrounding labels and other finding text stay neutral. Broken
automation descriptions also stay neutral except for the explicit **BROKEN**
state, which is highlighted red. Pushover
reports include named offline devices, low
batteries, broken automations, log findings, and resolved findings within the
service message limit. In the opened Pushover message, offline device names and
states are red while low-battery device names and reported battery values are
amber; surrounding text remains neutral. If HTML colour markup makes the complete
report exceed Pushover's per-message limit, HomeBrain splits it into numbered
parts instead of dropping later sections. Pushover now also mirrors the missing
comparison information from the dashboard: non-offline device warnings remain under
a dedicated **Device warnings** section, and actual **New since previous check**
item names are included rather than only the summary count. The scheduled morning health check is read-only and uses
the Hubitat timezone; its stored snapshot is reused by the dashboard.

## API

These endpoints are intended to be reached through Home Assistant ingress:

- `GET /api/status` — MCP and Ollama Online readiness
- `GET /api/dashboard` — cached live-state dashboard counts
- `GET /api/health-audit` — latest stored system-health audit and schedule status
- `POST /api/health-audit/run` — run the same read-only audit immediately
- `POST /api/ask` — process a request through the unified MCP agent
- `POST /api/chat` — compatibility alias for `/api/ask`
- `POST /api/refresh` — refresh MCP tools and device manifest
- `GET /health` — add-on health probe
