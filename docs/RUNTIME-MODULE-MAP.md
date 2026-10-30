# Runtime module map

This is the authoritative inventory of shipped Python modules under `hubitat-mcp-ai/rootfs/app/`.

The repository drift test compares this table directly with the live directory. Add, remove, or rename a row in the same pull request as the corresponding runtime module change.

| Module | Role |
| --- | --- |
| `agent_prompt_policy.py` | Builds the system prompt and optional identity manifests. |
| `aggregate_fallback_policy.py` | Keeps generic value/valueStr aggregate fallbacks request-local and suppresses them after complete non-empty canonical meter evidence. |
| `api_response_builder.py` | Builds the stable API response and presented metrics. |
| `app.py` | Owns FastAPI routes, configuration, shared services, and request coordination. |
| `automation_diagnostic_policy.py` | Distinguishes fast configuration inventories from evidence-first, read-only runtime automation investigation and model synthesis. |
| `automation_ideas_service.py` | Asks the model for grounded, creative new-automation suggestions (never factual claims). |
| `automation_status_service.py` | Reads and normalises Hubitat automation status. |
| `capability_grounding.py` | Prevents unsupported capability-denial claims. |
| `causal_answer_plan.py` | Builds a source-scoped pre-synthesis OFF claim and hypothesis plan, and validates command-history claims against its evidence coverage. |
| `causal_attribution_guard.py` | Prevents app/rule configuration-only evidence from being promoted into a specific causal trigger, and ensures stronger aligned controller provenance wins when present. |
| `sensor_causal_claim_guard.py` | Reconciles confident named-sensor OFF-blocker diagnoses against typed sensor-specific active-state and timer decision receipts; incomplete proof produces a concise tentative answer without implying that source coverage proves runtime causation. |
| `occupancy_causal_proof.py` | Reconciles generic false-motion/ghosting certainty against verified app-command-to-switch-state pairs and actual motion-event listener metadata, without treating cloned sensor transitions as confirmed controller inputs. |
| `occupancy_timing_correlation.py` | Derives positive, bounded sensor-inactive to app-issued-OFF to switch-OFF alignments from actual typed history/producer/listener receipts; avoids asserting physical vacancy, ghost motion, or definitive source completeness. |
| `causal_command_semantics.py` | Declares driver/capability-gated state-changing command methods, checks level parameters, and separates reliable dimmer effects from driver-dependent possibilities. |
| `causal_lighting_context.py` | Explains bounded level-command chronology and correlates specifically selected occupancy history with proven lighting activations without inventing a sensor trigger. |
| `causal_command_provenance.py` | Correlates compatible ON/OFF/setLevel command rows to focal switch boundaries, keeps command producers distinct from bridge reporters and flags competing apps without inventing a unique initiator. |
| `causal_command_clue_guard.py` | Prevents unverified external-controller exclusion when an exact-event preceding Hubitat command is present; preserves producer metadata as an investigative clue rather than causal proof. |
| `skills_framework.py` | Selects and loads bounded repo-owned MCP operating and investigative skills by request intent without granting tools. |
| `skill_investigation.py` | Projects exact causal events and intervening-state anomalies into ranked candidate hypotheses. |
| `skill_investigation_followup.py` | Selects at most two evidence-derived, read-only missing-focal follow-ups (current producer config and explicitly allowlisted archived log counts); preserves no-causation and secret-redaction boundaries. |
| `skill_topology.py` | Plans read-only producer-first configuration and source-coverage checks from current-turn receipts. |
| `skill_source_completion.py` | Plans a required device-scoped log read from resolved telemetry evidence before final synthesis; does not execute or mutate. |
| `skill_decision_summary.py` | Produces source-ranked causal hypotheses and calibrated offline telemetry diagnoses without inventing execution or transport facts. |
| `skill_grounded_answer.py` | Direct, source-grounded explanation for unique focal ON events with preceding recorded commands but no proven causal chain; prevents an unverified model verdict overriding typed evidence. |
| `skill_focal_window.py` | Plans exact-time, bounded state and command-producer log reads from unique focal event receipts; avoids latest-N pagination gaps and UTC/BST skew. |
| `historical_window_integrity.py` | Converts explicit two-date incident ranges into precise UK/UTC bounds and rejects a causal verdict where the oldest retained target event is newer than the requested period. |
| `skill_secret_guard.py` | Redacts credentials from model-facing tool content and final assistant responses. |
| `causal_native_logs.py` | Derives native-log windows for both causal boundaries and deterministically correlates physical controller/input events -> subject commands -> state transitions, including repeated start/end provenance. |
| `causal_rule_decision_context.py` | Separates confirmed lighting-app command provenance, scoped execution logs, current rule configuration, and present-day sensor-health evidence without inferring historical sensor truth. |
| `causal_subject_prefetch.py` | Conservatively matches one explicit known switch device and ON/OFF transition from a causal prompt so subject history can be gathered before the first provider round; ambiguous/broader causal questions fall through unchanged. |
| `causal_windowed_source.py` | Verifies MCP absolute `since`/`until` device-event reads and merges bounded sensor evidence only when the installed server confirms the window. |
| `causal_history_coverage.py` | Detects unavailable focal sensor prehistory in returned newest-N pages and prevents causal exclusion from history gaps. |
| `focal_evidence_reconciliation.py` | Reconciles verified bounded MCP history, private-message-free archived app-log coverage, and ON button-causality claims before synthesis without treating partial archives as command evidence. |
| `motion_lockout_investigation.py` | Performs bounded read-only light-OFF, button and motion event-sequence prefetch; checks current configuration and scoped execution logs; permits one-pass synthesis only when manual provenance and required evidence reads are verified, without claiming historical enforcement from silence. |
| `targeted_lockout_config.py` | Resolves named app lockout configuration questions through the read-only, permission-gated apps gateway without model-selected tool names; reports stored setting vs intended duration and no historical proof. |
| `focal_history_lookback.py` | Derives longer bounded native history reads from explicitly dated source-zone event clocks. |
| `archived_app_decision_evidence.py` | Scoped privacy-safe reads of opt-in archived Hubitat app-log messages, preserving collector clock and execution-proof boundaries. |
| `focal_coverage_contract.py` | Reconciles requested-event evidence sources before published `investigation_coverage` scoring, preventing unrelated newer OFF histories from being labelled focal proof. |
| `focal_history_report.py` | Renders checked native/journal/app-log evidence with timestamp and retention caveats without generative provenance invention. |
| `focal_event_cross_source.py` | Reconciles native press/command evidence with Historical Journal collector observations without conflating clock/source provenance. |
| `focal_event_provenance.py` | Generic source-linked historical focal selection: newest observed state vs independently verified manual press-command-OFF chain, explicit event-day clock offset, and typed current persisted settings versus user expectations. |
| `scoped_execution_evidence.py` | Produces model-only bounded app log excerpts with row-level scope/clock provenance and a public count-only receipt; extracts OFF state-event handler references without promoting them to proof of action or decision. |
| `decision_claim_reconciliation.py` | Cross-domain typed time quantities, provenance and decision-versus-effect stages from bounded, privacy-scrubbed log excerpts; explicitly reports duration conflicts without treating textual assertions as verified enforcement. |
| `ai_investigation_routing.py` | One bounded, no-tools model choice among read-only investigation / whole-hub report / aggregate performance, with host-validated scope and fallback to MCP agent; ContextVar signals model selection to status presenters. |
| `device_incident_depth.py` | Bounded read-only post-baseline root-cause checkpoint for offline/MQTT single-device investigations; model still selects live driver/automation/upstream evidence tools. |
| `investigation_objective.py` | Defines a single read-only primary objective for source, rule, and general investigations, shared by routing, synthesis and evidence completion; never authorises writes or certifies source reasoning. |
| `investigation_dependency_leads.py` | Constructs bounded, read-only source-attested device/app dependency leads without treating proximity as cause. |
| `investigation_intelligence.py` | Cross-domain evidence requirements, source completeness and claim boundaries for historical lockouts, stale MQTT devices and scheduler job ownership; completion is based on observed time-linked evidence, not tool-call success. |
| `investigation_checkpoint.py` | Cross-domain, privacy-bounded source receipt ledger and read-only iterative evidence-selection checkpoint for unfinished investigations; avoids domain-specific device assumptions and repeated sources. |
| `investigation_fulfillment_gate.py` | Ensures interpreted read-only diagnostics cannot end at inventory/identity lookups; offers one bounded evidence-source retry and reports unresolved findings safely if no substantive source is read. |
| `group_app_decision_recovery.py` | Performs bounded, read-only Historical Journal log checks for independently verified command-issuing app IDs during scoped original-agent multi-device investigations; emits private-text-free, collector-reception-only decision metadata. |
| `recent_edge_context.py` | Bounded read-only Historical Journal lookup for verified target lights when recent native histories contain no switch changes; checks a separate 15-minute pre-window context without redefining the requested period. |
| `group_journal_recovery.py` | Bounded read-only Historical Journal fallback for named multi-device incidents with missing Hubitat switch states; preserves source/collector timestamp provenance and gap reports without granting new tool rights. |
| `unified_incident_digest.py` | Builds concise source-timestamped, cause-first multi-light incident explanations from archived switch-state observations, matched OFF/brightness commands and verified hub modes; removes redundant collector copies and labels unmatched reception-only observations. Does not invent external initiators or call tools. |
| `unified_incident_synthesis.py` | Read-only incident-ledger evidence reconciliation for incomplete switch-state histories; catches contradicting OFF/activation claims and produces a single chronological command/state ledger. No tool authority or source creation. |
| `unified_investigation_bridge.py` | Reuses V2's bounded, source-attested device event projections inside the original HomeBrain MCP agent; computes temporal command/state/sensor relations and missing input evidence for the original model's natural-language explanation. It grants no new tool IDs, executes no reads or writes, and makes no external-initiator claim. |
| `incident_reasoning_depth.py` | Distinguishes source retrieval from verified driver methods and linked controllers, and generic diagnostics from target-corroborated upstream evidence in read-only incident reports. |
| `incident_grounded_fallback.py` | Returns a bounded, source-timestamped partial report for the single incident actually read when an open-ended selection drifts onto an unsupported device; never fabricates an initiator. |
| `evidence_gateway_contract.py` | Read-only MCP envelope normalisation and required-field preflight; preserves device/time scope and rejects incomplete requests without Hubitat calls; never rewrites writes. |
| `causal_hypothesis_evaluation.py` | Evaluates typed OFF actor hypotheses and configured timer feasibility without inferring executions. |
| `causal_investigation_engine.py` | Ranks cross-integration causal candidates using cached topology, bounded histories, directional timestamps, and stated coverage limits. |
| `causal_evidence_planner.py` | Derives exact subject-room provenance discovery, one ranked controller history read, and deterministic controller-to-subject boundary alignments (start versus end) for causal investigations without authoring the causal answer. |
| `causal_completion_policy.py` | Decides whether the ON or OFF causal investigation is source-complete from typed checked evidence, not user wording or verified actor requirements. |
| `causal_certainty_contract.py` | Reconciles narrative and verdict table causal claims with one observed OFF command/trigger certainty graph, without upgrading correlation to external action. |
| `causal_transition_provenance.py` | Selects the user's exact closed interval and checks OFF commands independently of the ON path, preserving failed and empty bounded event-history reads. |
| `causal_evidence_graph.py` | Normalizes a single observed event into typed, source-scoped command, sensor, listener, configuration, log, location and OFF-provenance facts; identifies bounded evidence gaps for model-led synthesis without inventing execution links. |
| `causal_claim_verification.py` | Verifies app command ownership, bounded empty-log inference and relative before/after sensor timing from the focal causal graph at both synthesis and API boundaries. |
| `causal_coverage_claim_guard.py` | Cross-checks controller-history universal claims against the graph's observed ON boundaries and distinct aligned button events; preserves explicit exceptions and scoped claims. |
| `known_automation_topology.py` | Parses user-configured Aqara/SmartThings-style external automation topology and matches focal live trigger timing to configured target actions without promoting configuration into execution provenance. |
| `causal_timeline.py` | Joins observed bounded/open subject intervals with directional controller provenance, subject command boundaries, and mode/context evidence; also exposes bounded causal-completeness and material-row coverage checks without authoring conclusions. |
| `controller_correlation_guard.py` | Rejects synthesis that misuses an interval-end controller event as provenance for the earlier turn-on transition. |
| `automation_dependency_probe.py` | Bounded evidence-driven app configuration reads, typed current action-device edges, and weaker text-only shared-action candidates; explicitly excludes job ownership/execution claims. |
| `rm_settings_dependency.py` | Safely projects bounded Rule Machine 5.x indexed settings onto provenance-labelled device references and key-family counts without retaining raw settings or inferring actions. |
| `rule_design_claim_guard.py` | Calibrates unsupported native writer, timeout, overnight and manual-lockout claims for explicit read-only Rule Machine proposals; does not author or queue rules. |
| `existing_rule_claim_guard.py` | Calibrates unverified existing-rule action-tree claims while preserving independently observed current-turn OFF commands, sensor timing, complete Groovy source reads and WARN logs. |
| `existing_rule_observed_evidence.py` | Source- and app-ID-matched projection of confirmed runtime OFF/state pairs, last subscribed sensor inactivity, long-running handler WARN logs and full installed source coverage; does not claim complete compiled rule semantics. |
| `existing_rule_settings_evidence.py` | ID-bound, read-only allowlisted projection of indexed Rule Machine and controller setting values; preserves partial-evidence status and redacts unrelated config. |
| `existing_rule_page_evidence.py` | Extracts bounded, privacy-safe action syntax from explicitly requested native Rule Machine editor pages; not a compiled-rule action-tree validator. |
| `native_rule_creation_staging.py` | Strict creation safety check for user-required atomic disabled-at-birth native Rule Machine rules; refuses unverified active-then-disable staging without model or hub writes. |
| `night_idle_rule_authoring.py` | Model-free exact-intent native Rule Machine night-idle OFF compiler; verifies named rule inventory, device IDs/capabilities, native action guide and routes guarded proposal to ordinary confirmation. |
| `scheduler_identity_reconciliation.py` | Compares source-recognized installed app identities/status with encoded scheduler-key candidate IDs, explicitly separating an ID overlap from proof of ownership or execution. |
| `audit_priority_planner.py` | Prioritises exact offline/log/heartbeat source combinations and labels scheduler ownership, timestamp clustering and disabled-app dependencies without asserting unseen failures. |
| `audit_reasoning_context.py` | Bounded cross-source current audit evidence packet for the optional, no-tools chat AI interpretation; preserves scheduler/log/performance limits. |
| `audit_ai_advisory_guard.py` | Corrects optional whole-hub AI advisory overclaims from top-N performance samples, saturated log windows and user-reported device power while retaining provider/model attribution independently. |
| `composite_system_audit_policy.py` | Routes whole-hub audits spanning warnings/errors, apps/rules and device or health checks into the evidence-rich System Check rather than partial performance-only synthesis. |
| `performance_timeout_digest.py` | Produces a bounded, evidence-only performance report if final AI synthesis times out, with no speculative repair claims. |
| `provenance_app_log_planner.py` | Selects one read-only app-log request for a verified command issuer and incident time, preventing duplicate checks. |
| `historical_command_source_contract.py` | Identifies positive command events within mixed Hubitat history, derives UK-local incident times correctly in UTC, and separates recorded command producers from causal/physical evidence. |
| `conversation_recall.py` | Gives pure chat-reference questions a session-local, tool-free answer or one bounded model round, without pretending prior discussion proves Hubitat state. |
| `current_state_claim_contract.py` | Reconciles simple current single-device status claims with same-turn targeted reported attributes when no independent source supports unreported measurements. |
| `chat_transport.py` | Owns provider HTTP, streaming, and response assembly. |
| `anthropic_transport.py` | Adapts explicit Claude API requests and tool-use IDs to HomeBrain's existing MCP executor, without cross-provider fallback. |
| `requested_device_explanation.py` | Source-faithful read-only summary of the named device when model output drifts to an irrelevant log device. |
| `adaptive_investigation_policy.py` | General read-only model-led investigation routing across multiple domains. |
| `source_evidence_metadata.py` | Privacy-safe source receipts, verified pages, adaptive recovery diagnostics and contiguous coverage checks. |
| `historical_causal_claim_guard.py` | Flags unverified named-app command execution claims against returned current-turn history; produces a cautious evidence-only answer rather than fabricated root cause. |
| `source_method_projection.py` | Projects bounded, line-numbered whole candidate method bodies from verified driver source into model synthesis without additional device reads; does not certify runtime semantics. |
| `source_exception_causality_guard.py` | Source-only, evidence-scoped calibration of unsupported LimitExceededException payload/transport-size and average-latency timeout causality; maintains verified call-site descriptions while deferring unverified root-cause claims. |
| `source_analysis_completion.py` | Stops repeat source reads after complete scoped device/source evidence and provides an evidence-limited failure report if model source analysis does not complete. |
| `groovy_source_investigation.py` | Discover MCP source reads for installed Hubitat apps, separate instance/code IDs and extract bounded Groovy excerpts without guessing code or affecting hub state. |
| `groovy_method_scope.py` | Conservative Groovy method-boundary and code-symbol index; prioritizes whole method excerpts while marking uncertain syntax and evidence-budget omissions, independent of full-file coverage. |
| `tool_free_knowledge_policy.py` | Strict opt-in static technical explanations without MCP discovery or tool execution; excludes live device/app requests. |
| `scoped_app_status_read.py` | Deterministic read-only app configuration execution for explicit app-ID status questions; truthful incomplete status on failed/missing reads. |
| `investigation_evidence_ledger.py` | Deduplicates checked command-event receipts and detects explicit false command-absence claims; read-only. |
| `lockout_claim_consistency.py` | Reports contradictory lockout duration claims without changing Hubitat settings. |
| `paid_model_routing.py` | Opt-in read-side model tier selection and fail-closed, persistent estimated-USD reservation ledger for paid Ollama requests. |
| `household_ollama_accounts.py` | Validates owner consent, adulthood, provider authorisation and scoped cloud secondary-account routing; denies rate-limit/auth rotation. |
| `provider_rate_limit_policy.py` | Sanitises Ollama Cloud HTTP 429 limit/usage responses, preserving only bounded Retry-After seconds and actionable guidance without replaying provider content or credentials. |
| `chatgpt_mcp.py` | Exposes the opt-in ChatGPT-facing Streamable HTTP MCP transport and high-level HomeBrainOS tools. |
| `control_intent_guard.py` | Fail-closed immediate-control qualifier check and protected/group-device classification; never grants independent write authority. |
| `confirmation_policy.py` | Decides whether structured actions require confirmation. |
| `confirmation_store.py` | Stores, expires, consumes, and cancels pending confirmations. |
| `confirmed_action_coordinator.py` | Revalidates and executes confirmed action groups. |
| `contact_history_queries.py` | Parses and presents bounded contact-history follow-ups and calendar-day aggregations. |
| `contextual_read_fast_path.py` | Parses and presents deterministic session-context attribute reads and motion aggregation. |
| `deterministic_tool_presenter.py` | Formats fixed answers for supported deterministic reads. |
| `device_claim_grounding.py` | Grounds a named-device claim in the final answer against this turn's device-scoped evidence. |
| `device_command_receipts.py` | Adjudicates typed Hubitat device-command dispatch and state-verification receipts without treating accepted commands as physical proof. |
| `device_control_service.py` | Executes bounded device-control operations. |
| `device_history_service.py` | Resolves one device and reads bounded event history. |
| `device_query_service.py` | Performs read-side inventory queries and aggregation. |
| `room_scoped_live_aggregates.py` | Applies original-question room constraints to live ON-light and non-light-switch aggregates using authoritative Hubitat room identities, independently of optional model tool parameters. Rejects unresolved scope instead of leaking whole-home results. |
| `device_read_contract.py` | Centralizes Hubitat device-list projection modes, state-field normalization, and projected-state shape validation. |
| `device_state_summary.py` | Provides shared pure device-state summary helpers. |
| `device_target_resolver.py` | Resolves natural-language targets to concrete devices. |
| `time_expressions.py` | Shared deterministic clock-time recognition (parsing an isolated "at <time>" token, never scanning free text for meaning); used by `rule_authoring_service.py` and `device_control_service.py`. |
| `direct_outcome_context.py` | Owns request-local evidence, choice, request-class, and mutation context. |
| `evidence_ledger.py` | Builds a compact current-turn checked-source ledger for final synthesis. |
| `evidence_recorder.py` | Stores sanitised request-scoped evidence receipts. |
| `evidence_source_scope.py` | Prevents unverified cross-app Groovy source substitutions after target-matched current-turn evidence; permits explicitly named comparisons. |
| `evidence_source_guard.py` | Corrects final claims that contradict successful current-turn source availability. |
| `observed_app_exception_guard.py` | Corrects categorical denials of explicitly recorded per-app Hubitat excessive-load ERROR rows at the final API response boundary without inferring shared cause or overall CPU impact. |
| `observed_long_method_guard.py` | Corrects false model denials of long-running app method WARN entries using successful source-scoped Hubitat logs without inferring hub-wide CPU or shared causation. |
| `observed_off_latency_causality.py` | Calibrates unproven long-handler-caused lighting delay verdicts against app-matched OFF/state pairs and motion listener-linked inactive-to-command timing, retaining WARN evidence as a separate anomaly. |
| `evidence_claim_calibrator.py` | Cross-route factual-confidence and wording checks against bounded history and device-scoped watchdog receipts; deduplicates redundant standalone summaries while preserving observations and source limits. |
| `system_audit_coverage.py` | Route-matched read-only whole-hub audit section/source contracts, separating bounded log inventory and performance evidence from individual device causal-history proofs. |
| `final_answer_coordinator.py` | Owns the final no-more-tools synthesis round and injects the current-turn evidence ledger. |
| `analytical_answer_quality.py` | Domain-agnostic question-first answer contract and one bounded no-tools improvement pass for omissions, subject to the existing factual validator. |
| `grounding_policy.py` | Applies deterministic grounding retry and refusal policy. |
| `health_audit_scheduler.py` | Runs the stored read-only system health audit on a configurable morning schedule using hub-local time. |
| `health_audit_service.py` | Performs deterministic Hub/MCP/device/battery/automation/log health checks, persists snapshots, and tracks new/resolved findings. |
| `history_result_enrichment.py` | Enriches bounded model-driven history reads with uniquely inferable binary attributes and safe post-window boundary evidence. |
| `causal_sensor_candidate_priority.py` | Ranks capability-verified sensor candidates referenced by automations before generic room candidates, without treating configured sources as historical proof. |
| `typed_device_history_evidence.py` | Extracts ID-scoped mixed command/state events from direct Hubitat history receipts and renders bounded diagnostic findings without inferred hardware outcomes. |
| `recorded_telemetry_freshness.py` | Timestamps bounded device-attributed event history and stored age samples; distinguishes emitted attributes from proven physical connectivity. |
| `device_watchdog_evidence.py` | Extracts source-ID-matched repeated watchdog no-data warnings from bounded current-turn log receipts, without treating reconnect attempts as successful delivery. |
| `telemetry_clock_consistency.py` | Reconciles as-of device-state metadata, reported data age and stored lastSeen timestamps without claiming physical telemetry or power; flags contradictory clocks in shared API investigation output. |
| `causal_initiator_provenance_guard.py` | Applies source-bound checks to model and repaired causal attribution claims; unknown initiating actors cannot become likely external automations merely because command history is bounded. |
| `causal_fail_closed_summary.py` | Provides a conservative observed-event fallback when the model's causal validation repair still fails. |
| `general_evidence_completion.py` | Checks required investigative source classes against successful, scoped read receipts and reports missing classes without promoting source checks to proof. |
| `shared_investigation_completion.py` | API-boundary, route-independent evidence coverage and partial-outcome reporting; never changes Hubitat or claims a read proves causality. |
| `general_task_engine.py` | Validates model-proposed cross-domain objectives, explicit proposal-only intent, skill selections, live capability-search phrases and evidence goals; advisory-only and opt-in, never grants MCP write authority. |
| `gateway_argument_view.py` | Canonical read-only view of direct or one-level-wrapped MCP gateway operation envelopes so evidence, grounding, and gateway compatibility checks agree on the same sub-tool without rewriting provider payloads. |
| `history_cardinality_guard.py` | Corrects exhaustive interval-count claims that contradict deterministic temporal evidence. |
| `history_temporal_analysis.py` | Derives bounded state intervals, deterministic duration totals, and bounded interval proof from authoritative device events. |
| `interval_duration_guard.py` | Repairs model-written ON/OFF duration table rows using matching typed recorded intervals, preserving ordinary minute rounding and unrelated rows. |
| `history_time_windows.py` | Parses request-scoped calendar phrases and resolves explicit local-time history windows. |
| `historical_evidence_journal.py` | Opt-in read-only Hubitat WebSocket collector with persistent bounded SQLite history, connection-gap tracking, privacy-filtered app logs and source-versus-reception timestamps; archived rows remain weaker evidence than direct command provenance. |
| `home_assistant_tts.py` | Sends bounded answer speech through Home Assistant mobile-app native TTS, including safe target discovery and stop control. |
| `investigation_policy.py` | Central shared classification for causal and analytical history requests so orchestration and final synthesis use the same request intent. |
| `homebrain_agent.py` | Production UnifiedMCPAgent composition and metrics wrapper. |
| `hub_info_service.py` | Reads refreshed Hub Information Driver state. |
| `hub_timezone.py` | Resolves and briefly caches the authoritative Hubitat IANA timezone for semantic history windows. |
| `live_evidence_authority.py` | Combines live evidence receipts with grounding decisions. |
| `location_correlation.py` | Computes deterministic tight temporal proximity between observed device-history interval boundaries and current-turn location/mode events. |
| `location_correlation_guard.py` | Corrects categorical final no-correlation claims when current-turn location evidence contains a tightly adjacent subject transition, while preserving correlation-versus-causation. |
| `location_event_queries.py` | Parses and presents bounded hub location-event (mode change) follow-ups. |
| `location_privacy.py` | Redacts precise-location device attributes (GPS, address, map tiles, journey logs) from provider-bound tool results. |
| `log_evidence_compactor.py` | Keeps log evidence receipts bounded while preserving compact full-result Rule Machine threshold samples for final causality validation. |
| `mcp_agent_orchestrator.py` | Coordinates the native tool-calling agent loop. |
| `mcp_client.py` | Implements Hubitat MCP JSON-RPC transport and tool access. |
| `mcp_skill_guidance.py` | Provides general, Claude-skill-inspired live-MCP discovery, progressive evidence investigation, rule semantics and safety context, with explicit deep-investigation selection. |
| `mcp_retry_metrics.py` | Records actual retry attempts begun at the MCP transport boundary. |
| `model_context_policy.py` | Bounds copied provider conversation and tool-result context. |
| `natural_datetime.py` | Formats authoritative ISO event timestamps for natural-language answers. |
| `one_time_rule_cleanup.py` | Soft-deletes expired HomeBrain-generated one-time Rule Machine rules on a guarded Hubitat-local nightly schedule. |
| `observed_agent_outcome.py` | Builds the immutable production outcome with request metrics. |
| `off_hypothesis_synthesis_guard.py` | Ensures final OFF explanations include material, evidence-backed timer feasibility and bounded command claims. |
| `performance_api_finalizer.py` | Runs the bounded recent-log read and evidence-scoped performance synthesis directly on the production `/api/ask`/`/api/chat` request path, then applies the fail-closed live semantic guard before serialization. |
| `performance_causality_guard.py` | Prevents recent log activity from being promoted into the cause of longer-window performance statistics without direct linking evidence, and blocks unsupported threshold/edit prescriptions. |
| `performance_diagnostic_evidence_gate.py` | Classifies adaptive source-scoped performance evidence as diagnostic signal, repeated neutral activity, sparse/neutral observations, or no observations, and forces unsupported mechanism hypotheses to remain unresolved. |
| `performance_diagnostic_format_guard.py` | Applies adaptive diagnostic evidence boundaries by entity and claim type regardless of Markdown shape, including cadence, same-second rate, mechanism-action, and threshold-trigger promotion checks. |
| `performance_evidence_first.py` | Supplies the evidence-first performance synthesis contract and a generic last-mile guard for unsupported qualitative, conditional-mechanism, reporting-overhead, and optimisation conclusions. |
| `performance_evidence_use_guard.py` | Applies final current-turn performance evidence integrity after generic semantic repairs, separating long-running operations from connectivity failures while preserving literal WARN evidence and inspection-first cluster advice. |
| `performance_inventory_check.py` | Reconciles complete scheduler-key candidate ID sets against bounded identity-only Hubitat app/device inventories, preserving source completeness, entity existence versus job ownership, and measured performance overlap. |
| `performance_job_analysis.py` | Groups scheduler rows by verified owner ID and handler, records incomplete ownership/row coverage, and distinguishes scheduled entries from executed CPU work. |
| `performance_host_plan.py` | Collects the bounded metrics/performance/log evidence set for broad performance+recommendation requests before final synthesis, adding scheduler evidence only when explicitly requested. |
| `performance_live_semantic_guard.py` | Localizes unsupported live performance wording for assertive implementation hypotheses, scheduler/job-to-load causality, unverified scheduler tuning, qualitative database conclusions, and over-severe backup alerts. |
| `performance_log_observation_guard.py` | Restores cited WARN/ERROR text from current-turn log evidence when causal or generic repair prose would otherwise overwrite the literal observation. |
| `performance_result_compat.py` | Applies narrow, provenance-preserving compatibility normalization to known malformed upstream performance result fields. |
| `performance_semantic_grounding.py` | Preserves measured performance facts while structurally localizing unsupported implementation mechanisms, outcome causality, and configuration prescriptions. |
| `provider_token_estimator.py` | Estimates provider token usage conservatively. |
| `pushover_notifier.py` | Formats and sends optional bounded scheduled System Check summaries through the Pushover Message API. |
| `reasoning_policy.py` | Tracks native tool-round shape, selected-device clarification constraints, and generic evidence-review/synthesis contracts without question-specific routing. |
| `request_runtime.py` | Tracks in-flight read-only investigation stages, retains verified-source checkpoints for bounded timeouts, and redacts URL tokens in HTTP logs. |
| `request_classification.py` | Provides non-authoritative presentation and manifest hints. |
| `request_metrics.py` | Collects fixed privacy-safe counters and timings. |
| `request_observation.py` | Owns request metrics lifecycle, cancellation/failure classification, and observed-outcome construction. |
| `request_outcome_policy.py` | Classifies completed requests from fixed privacy-safe counters with explicit precedence. |
| `room_status_snapshot.py` | Parses explicit room-state requests and renders a deterministic detailed inventory summary with offline-sensor health precedence. |
| `rule_machine_analysis.py` | Deterministic read-only analysis of explicit Rule Machine app IDs, verified configured sensor dependencies, and linked-parent health. |
| `targeted_rule_scope_policy.py` | Separates bounded named Rule Machine inspections from explicit whole-hub audit requests and parses coordinated app IDs. |
| `native_rule_claim_guard.py` | Evidence-bound final claim calibration for named-rule reviews, especially truncated histories and unverified cross-rule references. |
| `native_rule_evidence_prefetch.py` | Reads native rule health and numeric local-variable metadata through a bounded read-only MCP gateway before deep Rule Machine interpretation. |
| `rule_authoring_service.py` | Compiles supported fixed-time schedules, and classifies stateful automation goals for capability-driven authoring. |
| `stateful_rule_capabilities.py` | Performs live read-only Rule Machine capability preflight and rejects incomplete cumulative-usage proposal topology before confirmation. |
| `rule_proposal_confirmation.py` | Resolves a handled rule-authoring proposal into a response message, running proposed writes through the confirmation policy and queuing them. |
| `scheduler_secondary_inventory.py` | Performs a bounded sample of targeted `hub_get_device` reads for scheduler candidates absent from the context resource; exact returned-ID matches prove source-scoped entity presence only, while failures/timeouts remain unresolved and never imply deletion or ownership. |
| `scheduler_report_sanitizer.py` | Replaces recognized model-authored scheduled-job and log-cadence tables with source-derived counts and source-labelled observations; leaves unrelated AI interpretation intact. |
| `semantic_agent_core.py` | Converts fast or model-derived semantic control plans into deterministic HomeBrain device-control arguments and policy defaults. |
| `semantic_fast_path.py` | Parses narrow unambiguous brightness/heating wording into typed semantic plans without a provider round; host grounding and deterministic execution remain authoritative. |
| `semantic_plan.py` | Defines and validates the typed goal/target/action intermediate representation shared by fast paths and AI planning. |
| `semantic_planner.py` | Uses the reasoning model only for natural-language meaning, returning strict semantic plans without Hubitat wire details. |
| `semantic_world_model.py` | Projects cached Hubitat identity/capabilities into bounded semantic room/device abilities without exposing IDs, wire commands, or live-state claims. |
| `technical_metrics_presenter.py` | Converts fixed metrics and outcomes into UI-safe rows. |
| `synthesis_context.py` | Preserves bounded privacy-redacted current-turn tool-result excerpts for the final no-tools reasoning synthesis pass. |
| `synthesis_validator.py` | Detects deterministic factual conflicts in model synthesis and supplies a localized repair baseline without replacing supported analysis. |
| `token_aware_context_policy.py` | Applies stricter model-aware context ceilings. |
| `tool_discovery_catalog.py` | Owns prompt-independent tool visibility and expansion. |
| `tool_catalog_assembly.py` | Combines a request's already-fetched remote tools with the fixed local tool set into a ready `ToolDiscoveryCatalog`. |
| `tool_executor.py` | Dispatches approved calls and records normalised results. |
| `tool_registry.py` | Defines local schemas and structured tool effects. |
| `webui.py` | Renders the Home Assistant ingress interface. |