from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

from agent_prompt_policy import (
    build_system_prompt,
    render_app_manifest,
    render_device_manifest,
)
from chat_transport import ChatTransport
from source_analysis_completion import (
    source_trace_ready_for_synthesis, configuration_semantics_followup,
)
from source_method_projection import SourceChunkCollector
from tool_free_knowledge_policy import eligible_tool_free_knowledge, tool_free_messages
from adaptive_investigation_policy import model_led_investigation_request, READ_ONLY_AGENT_DIRECTIVE
from device_incident_depth import (
    device_incident_followup, incident_progress_followup,
    evidence_progress_checkpoint,
    is_connectivity_root_cause_request, CONNECTIVITY_EVIDENCE_PLAN,
)
from paid_model_routing import (
    set_original_paid_request,
    reset_original_paid_request,
    explicit_paid_request,
)
from confirmed_action_coordinator import ConfirmedActionCoordinator
from confirmation_policy import ConfirmationAction, ConfirmationPolicy
from confirmation_store import CONFIRM_WORDS, ConfirmationStore, PendingConfirmation
from capability_grounding import CapabilityAction, CapabilityGroundingPolicy
from causal_evidence_planner import (
    build_reporting_source_secondary_analysis,
    controller_boundary_alignments,
    controller_history_arguments,
    controller_history_candidates,
    render_controller_alignment_instruction,
    render_reporting_source_secondary_summary_evidence,
    render_sensor_correlation_instruction,
    sensor_transition_correlations,
    subject_has_observed_intervals,
    subject_room_filter_arguments,
    trigger_sensor_history_arguments,
    trigger_sensor_history_candidates,
)
from investigation_intelligence import (
    plan_investigation, render_investigation_plan, assess_investigation,
)
from causal_history_coverage import assess_local_sensor_history_coverage
from focal_history_report import render_bounded_focal_reconstruction
from motion_lockout_investigation import (
    is_motion_lockout_investigation, prefetch_motion_lockout,
    collected_lockout_ready_for_synthesis,
    collected_explicit_focal_ready_for_synthesis,
)
from targeted_lockout_config import read_current_lockout_config
from groovy_source_investigation import GroovySourceService, RequestScopedGroovyMcp, requested_groovy_app_id
from investigation_objective import resolve_primary_objective
from ai_investigation_routing import active_request_interpretation, without_request_interpretation
from investigation_fulfillment_gate import (
    investigating, inventory_without_investigation, inventory_answer,
    retry_instruction as incomplete_investigation_retry,
    honest_partial_answer,
)
from focal_evidence_reconciliation import (
    reconcile_window_coverage, summarize_journal_app_logs,
)
from causal_sensor_candidate_priority import prioritize_focal_sensor_candidates
from causal_windowed_source import (
    build_focal_sensor_window_probe,
    verify_windowed_sensor_reply,
    merge_windowed_sensor_history,
)
from causal_investigation_engine import (
    MAX_EXTRA_SENSOR_READS,
    SENSOR_BATCH_SIZE,
    has_strong_requested_correlated_candidate,
    has_repeated_requested_controller_candidate,
    has_local_requested_off_correlation,
    plan_cross_integration_candidates,
    rank_causal_hypotheses,
)
from causal_lighting_context import (
    matched_occupancy_edge,
    render_concise_lighting_answer,
    choose_occupancy_event_sources,
)
from causal_rule_decision_context import (
    app_log_window,
    configuration_text,
    configured_mode_triggers,
    execution_log_lines,
    mode_transition_correlations,
    proven_lighting_command,
    referenced_sensor_identities,
)
from causal_transition_provenance import (
    focal_closed_transition,
    positive_off_command_already_recorded,
    scoped_off_history_receipt,
)
from group_journal_recovery import recover_group_journal
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from recent_edge_context import recover_recent_edge, render_recent_edge
from group_app_decision_recovery import recover_group_app_decisions
from unified_investigation_bridge import (
    unified_investigation_followup, reconcile_unified_investigation_answer,
    collect_unified_evidence,
)
from causal_evidence_graph import (
    build_causal_evidence_graph,
    needs_mode_history,
    render_causal_evidence_graph,
    select_focal_sensor_events,
    supports_one_pass_deep_synthesis,
)
from causal_command_provenance import (
    boundary_producer_transition_kind,
    boundary_producer_transition_match,
    boundary_producer_transition_sufficient,
    command_producer_transition_sufficient,
    correlate_boundary_producers,
    correlate_command_producers,
    render_competing_command_summary,
    focal_transition_boundary,
    prompt_focal_transition_boundary,
    render_boundary_producer_summary,
    render_command_producer_summary,
    render_command_producer_evidence,
    render_preceding_command_candidates,
)
from causal_subject_prefetch import (
    causal_subject_history_arguments,
    causal_subject_seed,
    switch_transition_from_prompt,
)
from causal_native_logs import (
    causal_boundary_log_windows,
    correlate_native_log_boundaries,
    native_log_app_execution_sufficient,
    native_log_causal_provenance_sufficient,
    native_log_open_start_sufficient,
    native_log_provenance_sufficient,
    render_native_log_correlation,
    render_strong_native_provenance_answer,
)
from causal_timeline import (
    causal_log_windows,
    explicitly_focused_event_rows,
    has_explicit_focal_clock,
    render_command_source_followup,
    unresolved_material_timeline_rows,
)
from deterministic_tool_presenter import present_tool_result
from incident_grounded_fallback import render_grounded_incident_fallback
from device_claim_grounding import (
    DeviceClaimAction,
    DeviceClaimGroundingPolicy,
    extract_receipt_device_ids,
    extract_event_reporter_device_ids,
    extract_tool_message_device_identities,
    find_named_device_mismatch,
)
from device_control_service import DeviceControlService
from device_history_service import DeviceHistoryService
from device_query_service import DeviceQueryService
from evidence_recorder import EvidenceRecorder
from evidence_source_scope import source_app_scope_error
from target_history_scope import (
    render_target_scope_followup,
    inspect_target_history_scope,
    guard_unscoped_target_history_denial,
)
from final_answer_coordinator import FinalAnswerCoordinator, _original_user_request
from skills_framework import render_skills_for_request
from skill_topology import render_topology_plan
from skill_source_completion import (
    pending_device_log_read, pending_historical_command_read,
    pending_scoped_explanation_command_read, block_unscoped_historical_logs,
)
from requested_device_explanation import render_requested_device_explanation
from skill_focal_window import build_focal_source_plan, execute_focal_source_plan, render_unverified_focal_outcome, project_archived_focal_state
from skill_investigation_followup import execute_unverified_next_reads
from investigation_checkpoint import (
    is_investigative_question, render_investigation_checkpoint,
    requests_explicit_hypothesis_comparison, build_evidence_checkpoint,
)
from skill_secret_guard import redact_model_messages, redact_secrets
from causal_command_clue_guard import guard_causal_exclusion_with_command_clue
from causal_initiator_provenance_guard import guard_unverified_initiator_claims
from grounding_policy import GroundingAction, GroundingPolicy
from hub_info_service import HubInfoService
from history_result_enrichment import inferred_state_retry_arguments
from investigation_policy import (
    is_causal_investigation,
    is_history_investigation,
    uses_known_history_evidence_path,
)
from known_automation_topology import (
    known_automation_sensor_candidate_visibility,
    parse_known_automations,
    prioritize_known_automation_sensor_candidates,
)
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from model_context_policy import ModelContextPolicy
from historical_command_source_contract import history_window_instruction
from provenance_app_log_planner import pending_provenance_app_log_read
from conversation_recall import conversation_reference_answer, conversation_reference_intent
from control_intent_guard import unsafe_control_prompt, explicitly_read_only_request
from request_classification import (
    matches as _matches,
    requests_mutation as _requests_mutation,
    routine_control_arguments as _routine_control_arguments,
)
from reasoning_policy import set_reasoning_profile
from automation_diagnostic_policy import (
    AUTOMATION_DIAGNOSTIC_INSTRUCTION,
    INTEGRATION_DIAGNOSTIC_INSTRUCTION,
    is_automation_runtime_diagnostic,
    is_integration_runtime_diagnostic,
)
from request_metrics import increment_active_metric
from request_runtime import set_request_stage
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService
from night_idle_rule_authoring import propose_night_idle, recognise_night_idle_creation
from native_rule_creation_staging import demands_atomic_disabled_rule_creation, render_atomic_staging_stop
from rule_design_claim_guard import calibrate_rule_design_review
from existing_rule_claim_guard import calibrate_existing_rule_verification
from rule_machine_analysis import requires_rule_logic_inspection
from targeted_rule_scope_policy import (
    named_rule_app_ids, is_existing_rule_verification_request,
    is_new_rule_design_review_request,
)
from native_rule_evidence_prefetch import prefetch_native_rule_evidence
from existing_rule_settings_evidence import prefetch_installed_app_settings
from stateful_rule_capabilities import (
    inspect_stateful_rule_capabilities,
    cumulative_rule_proposal_error,
)
from rule_proposal_confirmation import RuleProposalConfirmation
from tool_executor import ToolExecutor
from tool_discovery_catalog import SEARCH_TOOL, ToolDiscoveryCatalog
from mcp_skill_guidance import (
    build_mcp_skill_guidance,
    build_mcp_skill_guidance_for_domains,
    wants_deep_investigation,
)
from general_task_engine import GeneralTaskPlanner
from general_evidence_completion import assess_task_source_coverage
from tool_catalog_assembly import build_request_tool_catalog
from tool_registry import (
    EVIDENCE_KINDS as _EVIDENCE_KINDS,
    LOCAL_ACTIVE_LIGHTS_TOOL as _LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL as _LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL as _LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_CONTROL_TOOL as _LOCAL_CONTROL_TOOL,
    LOCAL_DEVICE_HISTORY_TOOL as _LOCAL_DEVICE_HISTORY_TOOL,
    LOCAL_GROOVY_SOURCE_TOOL as _LOCAL_GROOVY_SOURCE_TOOL,
    LOCAL_DEVICE_INVENTORY_TOOL as _LOCAL_DEVICE_INVENTORY_TOOL,
    LOCAL_FILTER_TOOL as _LOCAL_FILTER_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL as _LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL as _LOCAL_HUB_INFO_TOOL,
    LOCAL_LOCATION_EVENTS_TOOL as _LOCAL_LOCATION_EVENTS_TOOL,
    LOCAL_QUERY_TOOL as _LOCAL_QUERY_TOOL,
    LOCAL_RESOLVE_TOOL as _LOCAL_RESOLVE_TOOL,
    LOCAL_WEATHER_TOOL as _LOCAL_WEATHER_TOOL,
    ToolEffect,
    classify_tool_effect,
    normalize_rule_machine_proposal,
    rule_machine_proposal_error,
)

logger = logging.getLogger("HomeBrainOS.Orchestrator")


def _gateway_leaf(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    leaf = str(arguments.get("tool") or "").strip()
    inner = arguments.get("args")
    return leaf, dict(inner) if isinstance(inner, dict) else {}


def _is_broad_device_inventory_call(
    tool_name: str,
    arguments: dict[str, Any],
) -> bool:
    if tool_name not in {"hub_read_devices", "hub_manage_devices"}:
        return False
    leaf, inner = _gateway_leaf(arguments)
    if leaf != "hub_list_devices":
        return False
    scoped_keys = {
        "filter",
        "labelFilter",
        "capabilityFilter",
        "roomFilter",
        "changedSince",
        "attributeNames",
        "onlyOn",
        "cursor",
    }
    return not any(
        key in inner and inner.get(key) not in (None, "", [], {})
        for key in scoped_keys
    )


def _normalize_causal_log_call(
    tool_name: str,
    arguments: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    original_user: str = "",
) -> dict[str, Any]:
    """Force native log reads onto observed causal boundary timestamps.

    Native hub logs interpret timezone-free values as UTC. Model-authored
    conversions can therefore shift a Hubitat-local +01:00 boundary by an hour.
    The host owns this conversion because the actual device-history timestamp is
    already structured evidence.
    """

    leaf, inner = _gateway_leaf(arguments)
    direct = tool_name == "hub_get_logs"
    gateway = leaf == "hub_get_logs"
    if not (direct or gateway):
        return arguments

    focused = explicitly_focused_event_rows(evidence, original_user)
    windows = causal_log_windows(evidence, original_user=original_user)
    if not windows:
        return arguments

    prior_log_reads = sum(
        1
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("success") is True
        and (
            str(receipt.get("tool") or "") == "hub_get_logs"
            or str(receipt.get("sub_tool") or "") == "hub_get_logs"
        )
    )
    # A scoped one-event investigation always reads that same event, even
    # after a host-side app-log prefetch. Rotating to the next interval was
    # silently changing the question from 07:53 to 07:08.
    window = windows[0] if focused else windows[min(prior_log_reads, len(windows) - 1)]
    normalized = dict(arguments)
    if direct:
        normalized["since"] = window["since"]
        normalized["until"] = window["until"]
        normalized.setdefault("limit", 100)
        return normalized

    normalized_inner = dict(inner)
    normalized_inner["since"] = window["since"]
    normalized_inner["until"] = window["until"]
    normalized_inner.setdefault("limit", 100)
    normalized["args"] = normalized_inner
    return normalized


def _controller_followup_arguments(
    candidates: list[dict[str, Any]],
) -> dict[str, str] | None:
    """Compatibility adapter for the pre-0.12 controller-selection contract."""

    return controller_history_arguments({
        "eventSourceHints": {"controllerCandidates": candidates}
    })


_APP_TERMS = {
    "app", "apps", "automation", "automations", "pause", "paused", "resume",
    "rule", "rules",
}
_DEVICE_TERMS = {
    "battery", "batteries", "device", "devices", "door", "light", "lights",
    "fan", "humidity", "lamp", "lamps", "lock", "motion", "outlet", "plug",
    "presence", "sensor", "state", "switch", "temperature", "thermostat",
    "weather",
}
_LOG_TERMS = {"log", "logs"}
_HOME_STATE_PATTERNS = (
    r"\bwhat(?:'s| is) happening\b",
    r"\bhome (?:status|summary|overview)\b",
)

_READ_QUERY_PREFIX = re.compile(
    r"^\s*(?:why|when|what|which|where|how|is|are|was|were|did|does|do|"
    r"has|have|had)\b",
    re.I,
)

# A negative safety instruction inside an investigation never authorises a
# mutation. Stop at an independent positive clause or sentence boundary.
_NEGATED_WRITE_CLAUSE = re.compile(
    r"\b(?:do\s+not|don't|never)\s+(?:actually\s+)?"
    r"(?:turn|switch|power|set|change|alter|create|delete|disable|enable|"
    r"restart|block|unblock|allow|configure|execute|run|send|issue|"
    r"install|remove|pause|resume|update|write|apply|schedule|"
    r"start|stop|toggle|lock|unlock)\b"
    r"(?:(?![.!?;]|\b(?:but|however|instead|then)\b).)*",
    re.I | re.S,
)


def _without_prohibited_actions(text: str) -> str:
    """Strip explicit prohibitions, never independently requested changes."""
    return _NEGATED_WRITE_CLAUSE.sub("", text)



def _explicit_mutation_request(prompt: str) -> bool:
    """Return user write intent without treating diagnostic wording as a write.

    requests_mutation() is deliberately broad for routing/control detection and
    therefore matches phrases such as "why did the light turn off?" merely
    because they contain a control verb. Request semantics need a narrower
    contract: ordinary interrogatives remain reads, while imperative and polite
    action forms continue to use the established mutation parser.
    """

    text = str(prompt or "").strip()
    # Explicit model-selection is not device-control intent. A question like
    # "Use paid model. Why did Bathroom Light 1 turn on?" must stay read-only.
    # Strip only a leading routing directive; subsequent writes remain writes.
    text = re.sub(
        r"(?i)^\s*(?:use paid model|premium model|paid investigation)"
        r"\s*[.!:,;\-]*\s*", "", text,
    )
    if not text:
        return False
    # An explicit user no-write constraint is authoritative even if the
    # narrative mentions ON/OFF, command histories or rule configurations.
    # Model-proposed write tools must not override this host-level veto.
    if explicitly_read_only_request(text):
        return False
    # Conditional, cancelled and compound device-control lead-ins cannot
    # authorise a write via a model tool call any more than they can through
    # the deterministic fast path. Treat them as interpretation-only unless
    # the user separately requests explicit, confirmable rule authoring.
    if unsafe_control_prompt(text):
        return False
    # The user may describe a rule they WANT to build while explicitly
    # withholding present authority to create or queue it. Do not let the
    # opening phrase "I want to create" override an explicit review-only
    # instruction later in the same request.
    # AI's task interpretation has no authority to decide whether an
    # imperative is a write. Re-run this safety exemption independently.
    with without_request_interpretation():
        review_only_by_user = RuleAuthoringService.is_read_only_rule_design_request(text)
    if review_only_by_user:
        return False
    # Prevent explicit prohibitions from granting write permission.
    text = _without_prohibited_actions(text)
    if not text.strip():
        return False
    # Keep *mixed* requests in the guarded write path. Do not let a question
    # lead-in hide a later independent command to change hub state.
    secondary_write = re.search(
        r"(?i)(?:[.!?;]\s+(?:(?:also|then|instead)\s+)?|"
        r"\band\s+(?:then\s+|also\s+)?|\bbut\s+|"
        r"\binstead\s+)"
        r"(?:please\s+)?(?:turn|switch|set|change|create|delete|"
        r"disable|enable|restart|block|unblock|allow|configure)\b",
        text,
    )
    # Only an actual separately requested action grants mutation authority.
    # A subordinate "and change" within a single question ("Why did the
    # light turn on and change brightness?") is descriptive, not imperative;
    # a later independent sentence ("Why did it turn on? Then block it")
    # remains a real write. Prohibitions were already removed above.
    if secondary_write is not None:
        first_question_mark = text.find("?")
        if (
            first_question_mark >= 0
            and secondary_write.start() < first_question_mark
            and _READ_QUERY_PREFIX.search(text)
        ):
            return False
        return True
    # "Verify whether app 3950 issued OFF" is evidence verification,
    # not an instruction to issue OFF. A later independent imperative still
    # routes through confirmation via secondary_write.
    historical_verification_lead = re.match(
        r"(?i)^\s*(?:verify|check|confirm|determine|establish)\s+"
        r"(?:whether|if)\b",
        text,
    )
    if historical_verification_lead and secondary_write:
        # The existing broad mutation parser may decline an otherwise clear
        # trailing imperative when the whole prompt starts "Verify whether".
        # Preserve the independent state-changing request instead of silently
        # treating the combined prompt as read-only.
        return True
    if (_READ_QUERY_PREFIX.search(text) or historical_verification_lead) and not secondary_write:
        return False
    # Explanatory prompts are never write requests merely because their
    # subject is a command such as "switch=off" or "command-off".
    # Independent later imperatives still win via secondary_write above.
    explanatory_lead = re.match(
        r"(?i)^\s*(?:explain|compare|distinguish|describe|identify|"
        r"summarize|summarise|review|analyse|analyze|investigate|"
        r"diagnose|reconstruct|interpret)\b", text,
    )
    if explanatory_lead and secondary_write:
        return True
    if explanatory_lead and not secondary_write:
        return False
    # A request to execute an explicitly named device command is a real
    # user authorization even when it does not spell out its argument values.
    if re.match(
        r"(?i)^\s*(?:please\s+)?(?:run|execute|issue|send)\s+"
        r"(?:the\s+)?(?:(?:routine|sensitive)\s+)?"
        r"(?:device|hubitat)\s+command\b", text,
    ):
        return True
    # An imperative investigative lead-in can still be a READ, even when
    # describing a historical command (e.g. "Investigate thoroughly why
    # the light turned on?"). The broad control-verb parser must not turn
    # that explanation into a write request and later reject valid findings.
    # Retain writes for explicit mixed requests without a causal question.
    investigative_lead = re.match(
        r"^\s*(?:investigate|diagnose|explain|analyse|analyze|reconstruct)"
        r"\b", text, re.I,
    )
    if investigative_lead and not secondary_write and re.search(
        r"\b(?:why|what caused|what triggered|how did)\b", text, re.I,
    ):
        return False
    # A deep, explicitly read-only investigation of an installed Rule Machine
    # app remains a READ even if its question includes "could switch ... OFF".
    # requests_mutation() sees that descriptive phrase as a command. Fail
    # closed for independent mutation clauses and numbered/line-start writes.
    if (is_existing_rule_verification_request(prompt)
            and not secondary_write
            and re.match(
                r"(?i)^\s*(?:please\s+)?(?:perform|conduct|carry\s+out|"
                r"verify|inspect|check|review|audit|investigate|compare|"
                r"determine|establish|analyse|analyze)\b",
                text,
            )
            and not re.search(
                r"(?mi)^\s*(?:\d+\.\s*)?(?:please\s+)?"
                r"(?:turn|switch|set|change|create|delete|disable|enable|"
                r"restart|block|unblock|configure|execute|install|remove|"
                r"pause|resume|update|write|apply)\b",
                text,
            )):
        return False
    return _requests_mutation(text)

_DEVICE_INVENTORY_PATTERNS = (
    r"^\s*(?:please\s+)?(?:list|show)(?:\s+me)?\s+(?:all\s+|every\s+)?(?:my\s+)?devices\s*[?.!]*$",
    r"^\s*(?:my\s+)?device\s+inventory\s*[?.!]*$",
    r"^\s*what\s+devices\s+(?:do\s+i\s+have|are\s+on\s+the\s+hub)\s*[?.!]*$",
)

_DEVICE_INVENTORY_SCOPE_PATTERNS = (
    r"^\s*(?:please\s+)?(?:list|show)(?:\s+me)?\s+(?:all\s+)?(?P<group>.+?)\s+devices\s*[?.!]*$",
    r"^\s*(?:please\s+)?(?:list|show)(?:\s+me)?\s+devices\s+(?:in|from)\s+(?:the\s+)?(?P<group>.+?)\s*[?.!]*$",
)

_DEVICE_INVENTORY_LIVE_QUALIFIERS = {
    "active", "inactive", "on", "off", "online", "offline", "open", "closed",
    "low battery", "low batteries", "battery", "batteries", "motion", "motions",
    "light", "lights", "switch", "switches", "sensor", "sensors",
}


def _device_inventory_arguments(prompt: str) -> dict[str, str] | None:
    """Return deterministic inventory arguments without stealing live-state reads."""

    text = str(prompt or "").strip()
    if not text:
        return None
    if any(re.search(pattern, text, re.I) is not None for pattern in _DEVICE_INVENTORY_PATTERNS):
        return {}

    for pattern in _DEVICE_INVENTORY_SCOPE_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match is None:
            continue
        group = str(match.group("group") or "").strip(" .?!")
        if not group:
            return None
        normalized = re.sub(r"\s+", " ", group.casefold()).strip()
        if normalized in _DEVICE_INVENTORY_LIVE_QUALIFIERS:
            return None
        return {"group": group}
    return None


# Successful temporal history is strong structured evidence. Straight factual
# history requests can move directly to synthesis once the complete native tool
# round has executed. Investigative requests remain eligible for broader evidence
# gathering; classification lives in investigation_policy.py so the final
# coordinator and orchestrator cannot diverge.

# Live-observed, safety-relevant gap: a write-classified turn ("enable it",
# right after "disable humidity controller app" -> confirm -> disabled)
# returned "Enabled the '01. Humidity Controller' app." with model_rounds=1,
# tool_calls=0, and evidence=[] -- the model narrated a mutation success with
# no tool ever having executed. This only reaches the plain "return the
# model's own narration" branch at the bottom of the no-tool-calls handling
# below, which every other outcome (a queued confirmation, a rejected
# confirmation, a capability/device-claim/grounding refusal, a proposal
# error) already bypasses via its own earlier `return`. So checking right
# at that one fall-through point -- rather than message-sniffing for
# "already admits failure" wording, which turned out to be an unbounded
# and fragile set of legitimate phrasings elsewhere in this file -- reaches
# exactly the one case that was never verified: a mutation the model
# claimed but never actually attempted through a tool call this turn.
UNVERIFIED_MUTATION_REFUSAL = (
    "I could not verify that this action actually ran on Hubitat -- no "
    "successful tool result confirms it, so I will not report it as done."
)
RULE_WRITES_DISABLED_MESSAGE = (
    "Rule Machine writes are disabled in HomeBrain settings. "
    "No rule was queued or changed."
)

@dataclass(slots=True)
class AgentOutcome:
    message: str
    request_class: str
    evidence: list[dict[str, Any]]
    choices: list[str]
    confirmation_required: bool = False
    confirmation_count: int = 0
    # The API response and bounded-timeout fallback use a stable route field.
    # Defining it on the slotted base outcome prevents AttributeError when
    # safe_partial_outcome marks an investigation as timed out.
    route: str = "unified-mcp-agent"
    investigation_coverage: dict[str, Any] | None = None
    interpreted_intent: dict[str, str] | None = None


class UnifiedMCPAgent:
    """Ollama Online agent that executes live Hubitat MCP function calls."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        api_key: str,
        model_name: str = "gemma4:31b-cloud",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        stream_idle_timeout_seconds: float = 20,
        local_base_url: str = "",
        local_model_name: str = "",
        local_timeout_seconds: float = 12,
        local_connect_timeout_seconds: float = 3,
        local_keep_alive_seconds: float = 120,
        household_cloud_accounts: tuple[Any, ...] = (),
        household_cloud_failover_enabled: bool = False,
        cloud_first: bool = False,
        paid_routing_enabled: bool = False,
        paid_routing_mode: str = "hybrid",
        paid_budget_usd: float = 6.50,
        paid_deep_model: str = "deepseek-v4-pro",
        free_quota_paid_fallback_enabled: bool = False,
        claude_api_key: str = "",
        claude_model: str = "claude-sonnet-4-6",
        tool_limit: int = 48,
        max_tool_rounds: int = 9,
        require_sensitive_confirmation: bool = True,
        confirmation_ttl_seconds: float = 120,
        rule_write_enabled: bool = True,
        causal_subject_prefetch_enabled: bool = True,
        causal_deterministic_final_enabled: bool = True,
        general_task_engine_enabled: bool = False,
        known_automations: Any | None = None,
        internet_control_aliases: Any | None = None,
        max_tool_result_chars: int = 24000,
        max_history_messages: int = 8,
        max_history_chars: int = 12000,
        max_tool_context_chars: int = 48000,
        compacted_tool_result_chars: int = 1200,
        ai_client: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.transport = ChatTransport(
            api_key,
            model_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            stream_idle_timeout_seconds=stream_idle_timeout_seconds,
            client=ai_client,
            local_base_url=local_base_url,
            local_model_name=local_model_name,
            local_timeout_seconds=local_timeout_seconds,
            local_connect_timeout_seconds=local_connect_timeout_seconds,
            local_keep_alive_seconds=local_keep_alive_seconds,
            household_cloud_accounts=household_cloud_accounts,
            household_cloud_failover_enabled=household_cloud_failover_enabled,
            cloud_first=cloud_first,
            paid_routing_enabled=paid_routing_enabled,
            paid_routing_mode=paid_routing_mode,
            paid_budget_usd=paid_budget_usd,
            paid_deep_model=paid_deep_model,
            free_quota_paid_fallback_enabled=free_quota_paid_fallback_enabled,
            claude_api_key=claude_api_key,
            claude_model=claude_model,
        )
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.rule_write_enabled = bool(rule_write_enabled)
        self.causal_subject_prefetch_enabled = bool(
            causal_subject_prefetch_enabled
        )
        self.causal_deterministic_final_enabled = bool(
            causal_deterministic_final_enabled
        )
        # Opt-in semantic planning; no changes to tool permissions or approval.
        self.general_task_engine_enabled = bool(general_task_engine_enabled)
        self.general_task_planner = GeneralTaskPlanner(self._chat)
        self.known_automations = parse_known_automations(known_automations)
        self.confirmation_policy = ConfirmationPolicy(
            enabled=self.require_sensitive_confirmation
        )
        self.confirmations = ConfirmationStore(confirmation_ttl_seconds)
        self.max_tool_result_chars = max(2000, int(max_tool_result_chars))
        self.context_policy = ModelContextPolicy(
            max_history_messages=max_history_messages,
            max_history_chars=max_history_chars,
            max_tool_context_chars=max_tool_context_chars,
            compacted_tool_result_chars=compacted_tool_result_chars,
        )
        self.max_history_messages = self.context_policy.max_history_messages
        self.max_history_chars = self.context_policy.max_history_chars
        self.max_tool_context_chars = self.context_policy.max_tool_context_chars
        self.compacted_tool_result_chars = (
            self.context_policy.compacted_tool_result_chars
        )
        self._app_manifest: list[dict[str, Any]] = []
        self._app_manifest_at = 0.0
        self.evidence = EvidenceRecorder()
        self.rule_authoring = RuleAuthoringService(
            self.mcp,
            self.evidence.record,
            internet_control_aliases=internet_control_aliases,
        )
        self.device_history = DeviceHistoryService(
            self.mcp,
            self.evidence.record,
        )
        self.executor = ToolExecutor(
            self.mcp,
            self.evidence,
            local_handlers={
                _LOCAL_FILTER_TOOL: self._filter_devices,
                _LOCAL_QUERY_TOOL: self._query_devices,
                _LOCAL_RESOLVE_TOOL: self._resolve_device,
                _LOCAL_DEVICE_HISTORY_TOOL: self.device_history.history,
                _LOCAL_GROOVY_SOURCE_TOOL: self._read_groovy_source,
                _LOCAL_DEVICE_INVENTORY_TOOL: self._device_inventory,
                _LOCAL_LOCATION_EVENTS_TOOL: self.device_history.location_events,
                _LOCAL_WEATHER_TOOL: self._weather_snapshot,
                _LOCAL_ACTIVE_LIGHTS_TOOL: self._active_lights,
                _LOCAL_ACTIVE_ROOMS_TOOL: self._active_rooms,
                _LOCAL_ACTIVE_SWITCHES_TOOL: self._active_switches,
                _LOCAL_HOME_SNAPSHOT_TOOL: self._home_snapshot,
                _LOCAL_CONTROL_TOOL: self._control_devices,
                _LOCAL_HUB_INFO_TOOL: self._hub_info_snapshot,
            },
            max_tool_result_chars=self.max_tool_result_chars,
        )
        self.final_answers = FinalAnswerCoordinator(
            self._chat,
            evidence_supplier=self.evidence.receipts,
        )
        self._request_class: ContextVar[str] = ContextVar(
            "hubitat_request_class", default="live-read"
        )
        self._current_user_objective: ContextVar[str] = ContextVar("homebrain_current_user_objective", default="")
        self._groovy_mcp_cache: ContextVar[RequestScopedGroovyMcp | None] = ContextVar(
            "homebrain_request_local_groovy_mcp_cache", default=None
        )
        self._investigation_reflection_used: ContextVar[bool] = ContextVar(
            "homebrain_investigation_reflection_used", default=False
        )
        self._investigation_hypotheses: ContextVar[tuple[Any, ...]] = ContextVar(
            "homebrain_request_hypothesis_comparisons", default=()
        )
        self._investigation_baseline: ContextVar[tuple[str, int] | None] = ContextVar(
            "homebrain_investigation_baseline", default=None
        )
        self._choices: ContextVar[list[str] | None] = ContextVar(
            "hubitat_choices", default=None
        )
        self._mutation_call_seen: ContextVar[bool] = ContextVar(
            "hubitat_mutation_call_seen", default=False
        )
        self._mutation_requested_by_user: ContextVar[bool] = ContextVar(
            "hubitat_mutation_requested_by_user", default=False
        )
        self._review_first_mode: ContextVar[bool] = ContextVar(
            "hubitat_review_existing_before_create", default=False
        )
        self.confirmed_actions = ConfirmedActionCoordinator(
            self.confirmation_policy,
            self.executor,
            self._chat,
            self._mark_mutation,
            rule_create_preflight=self.rule_authoring.duplicate_create_group_error,
        )
        self._rule_proposal_confirmation = RuleProposalConfirmation(
            self.confirmation_policy,
            self.confirmations,
            self._mutation_call_seen,
        )
    @property
    def configured(self) -> bool:
        return self.transport.configured

    @property
    def confirmation_ttl_seconds(self) -> float:
        return self.confirmations.ttl_seconds

    @property
    def _pending(self) -> dict[str, PendingConfirmation]:
        return self.confirmations.pending

    def _invalidate_app_manifest(self) -> None:
        """Drop cached app/rule identities whenever the hub may have changed."""

        self._app_manifest = []
        self._app_manifest_at = 0.0

    def _mark_mutation(self) -> None:
        self._mutation_call_seen.set(True)
        self._invalidate_app_manifest()

    @property
    def api_key(self) -> str:
        return self.transport.api_key

    @property
    def model_name(self) -> str:
        return self.transport.model_name

    @property
    def local_configured(self) -> bool:
        return self.transport.local_configured

    @property
    def local_model_name(self) -> str:
        return self.transport.local_model_name

    @property
    def base_url(self) -> str:
        return self.transport.base_url

    @property
    def timeout_seconds(self) -> float:
        return self.transport.timeout_seconds

    @property
    def ai_client(self) -> Any:
        return self.transport.client

    @property
    def stream_idle_timeout_seconds(self) -> float:
        return self.transport.stream_idle_timeout_seconds

    @stream_idle_timeout_seconds.setter
    def stream_idle_timeout_seconds(self, value: float) -> None:
        self.transport.stream_idle_timeout_seconds = max(0.001, float(value))

    async def close(self) -> None:
        await self.transport.close()

    @staticmethod
    def _is_conversational_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        conversational = (
            r"(?:hi|hello|hey|thanks|thank you|good morning|good evening)[.!? ]*",
            r"(?:help|what can you do|who are you)[.!? ]*",
        )
        return bool(conversation_reference_intent(prompt)) or any(
            re.fullmatch(pattern, normalized) for pattern in conversational
        )

    @staticmethod
    def _result_summary(result: MCPToolResult) -> str:
        return ToolExecutor.result_summary(result)

    def _record_evidence(
        self,
        gateway: str,
        arguments: dict[str, Any],
        *,
        success: bool,
        elapsed_ms: int,
        summary: str,
        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
        mutates: bool | None = None,
        effect: ToolEffect | str | None = None,
    ) -> None:
        self.evidence.record(
            gateway,
            arguments,
            success=success,
            elapsed_ms=elapsed_ms,
            summary=summary,
            supports_live_claim=supports_live_claim,
            evidence_kind=evidence_kind,
            mutates=mutates,
            effect=effect,
        )

    def _has_live_evidence(self) -> bool:
        return self.evidence.has_live_evidence()

    @property
    def _evidence(self) -> ContextVar[list[dict[str, Any]] | None]:
        """Compatibility view; new code should use ``self.evidence``."""

        return self.evidence.context

    _matches = staticmethod(_matches)
    _requests_mutation = staticmethod(_requests_mutation)
    _routine_control_arguments = staticmethod(_routine_control_arguments)

    @staticmethod
    def _device_attributes(device: dict[str, Any]) -> dict[str, Any]:
        return HubInfoService.device_attributes(device)

    @staticmethod
    def _device_attribute_units(device: dict[str, Any]) -> dict[str, str]:
        return HubInfoService.device_attribute_units(device)

    @staticmethod
    def _inferred_memory_unit(value: Any) -> str | None:
        return HubInfoService.inferred_memory_unit(value)

    @staticmethod
    def _hub_info_device(
        devices: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return HubInfoService.hub_info_device(devices)

    @staticmethod
    def _find_device_record(value: Any) -> dict[str, Any] | None:
        return HubInfoService.find_device_record(value)

    @staticmethod
    def _merge_device_identity(
        live_devices: list[dict[str, Any]],
        identity_devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return HubInfoService.merge_device_identity(
            live_devices,
            identity_devices,
        )

    async def _hub_info_snapshot(
        self,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        return await HubInfoService(self.mcp).snapshot(arguments)
    async def _lighting_rule_decision_followup(
        self,
        base_answer: str,
        *,
        transition: str = "on",
    ) -> str:
        """Enrich a proven lighting command with bounded read-only rule evidence.

        No result from configuration can override command producer provenance.
        Rule logs are scoped by the producer app ID and event time; present-day
        sensor health cannot prove the historical rule condition was true.
        """

        if transition != "on":
            return base_answer
        focus = proven_lighting_command(
            self.evidence.receipts(), transition=transition
        )
        if not focus:
            return base_answer
        producer = focus.get("producer") or {}
        app_id = str(producer.get("id") or "")
        app_name = str(producer.get("label") or "").strip()
        window = app_log_window(focus)
        if not window:
            return base_answer

        async def bounded_read(
            gateway: str,
            leaf: str,
            args: dict[str, Any],
            kind: str,
            live: bool,
        ) -> dict[str, Any] | None:
            request = {"tool": leaf, "args": args}
            start = time.monotonic()
            try:
                result = await self.mcp.call_tool(gateway, request)
                ok = self._tool_succeeded(result)
                data = result.data if isinstance(result.data, dict) else {}
                if data.get("status") in {"pending", "in_progress"}:
                    ok = False
            except Exception as error:
                ok = False
                data = {}
                logger.debug(
                    "Lighting rule follow-up %s failed: %s", leaf, error
                )
            # Preserve the *content* of host-prefetched facts in bounded
            # receipts. Previously the deep model saw "read available" only,
            # prompting it to repeat configuration/log requests and potentially
            # drift to an unrelated historical window.
            scoped_details: dict[str, Any] = {}
            if ok and leaf == "hub_get_app_config":
                config_excerpts, _ = configuration_text(data)
                scoped_details = {
                    "appId": app_id,
                    "configured": config_excerpts[:12],
                }
            elif ok and leaf == "hub_get_logs":
                log_rows = data.get("logs")
                scoped_details = {
                    "appId": app_id,
                    "logCount": len(log_rows) if isinstance(log_rows, list) else None,
                    "scopedSince": str(args.get("since") or ""),
                    "scopedUntil": str(args.get("until") or ""),
                    "execution": execution_log_lines(data, focus)[:8],
                }
            elif ok and leaf == "hub_list_device_events":
                # Keep bounded actual sensor edges and triggered[] handler
                # notifications near the requested ON and OFF boundaries.
                # A summary-only receipt previously forced the model to
                # repeat this MCP read to inspect a fact the host already had.
                scoped_details = {
                    "deviceId": str(args.get("deviceId") or ""),
                    "attribute": str(args.get("attribute") or ""),
                    "events": select_focal_sensor_events(
                        data,
                        {
                            "start": focus.get("stateBoundary"),
                            "end": focus.get("intervalEnd"),
                        },
                    ),
                }
            self.evidence.record(
                gateway,
                request,
                success=ok,
                elapsed_ms=round((time.monotonic() - start) * 1000),
                summary=(
                    f"Scoped {leaf} for command-producing app {app_id}: "
                    + ("read available" if ok else "read unavailable")
                ),
                supports_live_claim=live and ok,
                evidence_kind=kind,
                mutates=False,
                effect="read",
                details=scoped_details,
            )
            return data if ok else None

        app_data = await bounded_read(
            "hub_read_apps_code",
            "hub_get_app_config",
            {"appId": app_id, "includeSettings": False},
            "tool_result",
            False,
        )
        config_items: list[str] = []
        config_search = ""
        if isinstance(app_data, dict):
            actual = app_data.get("app") or {}
            if str(actual.get("id") or "") == app_id:
                config_items, config_search = configuration_text(app_data)

        log_data = await bounded_read(
            "hub_read_diagnostics",
            "hub_get_logs",
            window,
            "native_log_history",
            True,
        )
        execution = (
            execution_log_lines(log_data, focus)
            if isinstance(log_data, dict) else []
        )

        # A scope-to-rule log can prove its own trigger, if retained. When it
        # cannot, one bounded hub-wide mode-log check may corroborate a matching
        # configured mode transition. Correlation is NOT proof that the Rule
        # Machine conditions were true, and unavailable logs remain unknown.
        mode_events: list[str] = []
        if (
            configured_mode_triggers(config_items)
            and not any("mode" in line.casefold() for line in execution)
        ):
            mode_args = {
                "since": window["since"],
                "until": window["until"],
                "limit": 40,
                "pattern": r"(?i)\bmode\b",
            }
            mode_data = await bounded_read(
                "hub_read_diagnostics",
                "hub_get_logs",
                mode_args,
                "native_log_history",
                True,
            )
            if isinstance(mode_data, dict):
                mode_events = mode_transition_correlations(
                    mode_data, focus, config_items
                )

        # Producer attribution is already proved. Only now investigate the
        # automation's decision context, with a small read-only budget.
        try:
            identities = [
                item for item in (await self.mcp.get_device_identities() or [])
                if isinstance(item, dict)
            ]
        except Exception:
            identities = []
        subject = str(focus.get("subject") or "").casefold()
        subject_record = next(
            (
                item for item in identities
                if str(item.get("label") or item.get("name") or "").casefold() == subject
            ),
            None,
        )
        history_room = next(
            (
                str((receipt.get("details") or {}).get("room") or "").strip()
                for receipt in self.evidence.receipts()
                if receipt.get("tool") == "homebrain_device_history"
                and isinstance(receipt.get("details"), dict)
                and str((receipt["details"].get("label") or "")).casefold() == subject
                and (receipt["details"].get("room") or "")
            ),
            "",
        )
        room = str(
            (subject_record or {}).get("room")
            or (subject_record or {}).get("roomName")
            or history_room
            or ""
        ).strip()

        referenced = (
            referenced_sensor_identities(config_search, identities, room)
            if config_search else []
        )

        # A direct app log that actually names its trigger has precedence.
        # Otherwise test only configured occupancy sources or one unambiguous
        # room occupancy device; never search every motion sensor on the hub.
        occupancy_matches: list[dict[str, Any]] = []
        if not any(re.search(r"\bTriggered:\s*\S", row, re.I) for row in execution):
            candidates = choose_occupancy_event_sources(
                identities,
                config_search=config_search,
                subject_room=room,
            )
            for candidate, attribute, _configured in candidates:
                device_id = str(candidate.get("id") or candidate.get("deviceId") or "")
                events = await bounded_read(
                    "hub_read_devices",
                    "hub_list_device_events",
                    {
                        "deviceId": device_id,
                        "hoursBack": 24,
                        "limit": 50,
                        "attribute": attribute,
                    },
                    "authoritative_device_event_history",
                    True,
                )
                if not isinstance(events, dict):
                    continue
                match = matched_occupancy_edge(
                    focus,
                    label=str(candidate.get("label") or candidate.get("name") or ""),
                    attribute=attribute,
                    event_data=events,
                    configured=_configured,
                )
                if match is not None:
                    occupancy_matches.append(match)
                    self.evidence.record(
                        "homebrain_causal_trigger_correlation",
                        {
                            "appId": app_id,
                            "deviceId": device_id,
                            "attribute": attribute,
                        },
                        success=True,
                        elapsed_ms=0,
                        summary=(
                            f"Observed {attribute} activity on configured sensor "
                            f"{match['label']} near the light transition"
                        ),
                        supports_live_claim=True,
                        evidence_kind="deterministic_causal_secondary_correlation",
                        effect="read",
                        details={
                            "label": match["label"],
                            "attribute": attribute,
                            "configured": match["configured"],
                            "sensorEvent": match["when"].isoformat(),
                            "stateBoundary": str(focus.get("stateBoundary") or ""),
                            "signedDeltaSeconds": match["signedDeltaSeconds"],
                        },
                    )
                    increment_active_metric("causal_sensor_aligned")
                    if match["configured"] and match["signedDeltaSeconds"] <= 0:
                        break
            if candidates:
                increment_active_metric("causal_sensor_read", len(candidates))

        return render_concise_lighting_answer(
            self.evidence.receipts(),
            focus,
            logs=execution,
            config_search=config_search,
            referenced_sensors=referenced,
            occupancy_matches=occupancy_matches,
            mode_events=mode_events,
        )

    async def _prefetch_explicit_causal_subject(
        self,
        user_prompt: str,
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
    ) -> tuple[str, str | None, str | None]:
        """Gather explicit switch-causal evidence before the first model round.

        This is deliberately narrower than general causal reasoning. It activates
        only when authoritative identity plus the prompt establish exactly one
        known switch device and an explicit on/off transition. The host then runs
        the same DeviceHistoryService and native-log correlation used by the
        ordinary model-selected path.

        Returns (status, canonical_subject_key, transition), where status is
        one of: not_applicable, empty, sufficient, partial. The subject key lets
        the caller keep the prefetched device anchored as the investigative
        subject if later fallback reasoning inspects controller histories.
        """

        if not self.causal_subject_prefetch_enabled:
            return "not_applicable", None, None

        history_tool = catalog.declared_tool(_LOCAL_DEVICE_HISTORY_TOOL)
        if history_tool is None:
            return "not_applicable", None, None

        try:
            identities = await self.mcp.get_device_identities()
        except Exception as exc:
            logger.debug("Causal subject prefetch identity unavailable: %s", exc)
            return "not_applicable", None, None

        seed = causal_subject_seed(user_prompt, identities)
        if seed is None:
            return "not_applicable", None, None
        subject_key = re.sub(
            r"[^a-z0-9]", "", seed.name.casefold()
        ) or None

        arguments = {
            "name": seed.name,
            "attribute": seed.attribute,
            "_resolved_target": dict(seed.target),
            "_include_command_provenance": True,
            "_causal_transition": seed.transition,
            "_causal_correlation_history": True,
            # DeviceHistoryService interprets an explicit small state-history
            # limit as "latest transitions over the bounded seven-day horizon"
            # while still fetching enough rows internally for interval analysis.
            "limit": 3,
        }
        signature = json.dumps(
            [_LOCAL_DEVICE_HISTORY_TOOL, arguments],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        if signature in completed_calls:
            return "partial", subject_key, seed.transition
        completed_calls.add(signature)

        increment_active_metric("causal_subject_prefetch")
        execution = await self.executor.execute(
            _LOCAL_DEVICE_HISTORY_TOOL,
            arguments,
            tool=history_tool,
            supports_live_claim=True,
            evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
        )
        messages.append({
            "role": "tool",
            "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
            "content": execution.content,
        })
        messages.append({
            "role": "user",
            "content": (
                "HOST CAUSAL SUBJECT PREFETCH\n"
                f"Authoritative identity matched the explicit transition subject to "
                f"{seed.name!r} (confidence={seed.confidence:.3f}); the host gathered "
                f"{seed.attribute} history before provider tool selection. Treat this "
                "as current-turn evidence and do not request the same subject history "
                "again merely to confirm it."
            ),
        })

        if not execution.success or execution.result is None:
            return "partial", subject_key, seed.transition
        data = (
            execution.result.data
            if isinstance(execution.result.data, dict)
            else {}
        )
        if not subject_has_observed_intervals(data):
            increment_active_metric("causal_subject_empty_stop")
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL SUBJECT EVIDENCE STOP\n"
                    "The deterministic subject prefetch did not establish a bounded "
                    "active interval. Finalize from current-turn evidence only; do not "
                    "construct a cause for an unobserved transition."
                ),
            })
            return "empty", subject_key, seed.transition

        # A completed ON interval has an independent OFF boundary.
        # Inspect its command history before either ON fast path returns.
        if wants_deep_investigation(user_prompt) and seed.transition in {"on", "off"}:
            await self._collect_focal_off_provenance(
                user_prompt=user_prompt,
                resolved_device_id=str(seed.target.get("id") or ""),
                requested_transition=seed.transition,
                catalog=catalog,
            )
        current_evidence = self.evidence.receipts()
        explicit_off = (
            seed.transition == "off"
            and has_explicit_focal_clock(user_prompt)
        )
        focused_off = (
            focal_closed_transition(
                current_evidence, user_prompt,
                resolved_device_id=str(seed.target.get("id") or ""),
            )
            if explicit_off else None
        )
        if explicit_off and focused_off is None:
            messages.append({
                "role": "user",
                "content": (
                    "An exact OFF time was requested, but no unique observed "
                    "OFF boundary was established at that timestamp. Do not "
                    "substitute a newer OFF event or infer its cause."
                ),
            })
            return "partial", subject_key, seed.transition
        command_correlations = correlate_command_producers(current_evidence)
        requested_boundary = (
            focused_off["end"] if focused_off else
            prompt_focal_transition_boundary(
                current_evidence, seed.transition, user_prompt,
            )
        )
        if has_explicit_focal_clock(user_prompt) and not requested_boundary:
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL FOCAL BOUNDARY UNVERIFIED\\n"
                    "The exact requested ON/OFF boundary was not uniquely "
                    "observed in the returned history. Do not substitute the "
                    "latest transition or use nearby sensor correlation "
                    "as if it belonged to the requested time."
                ),
            })
            return "partial", subject_key, seed.transition
        if command_producer_transition_sufficient(
            command_correlations,
            seed.transition,
            requested_boundary=requested_boundary,
        ):
            increment_active_metric("causal_command_producer_provenance")
            instruction = render_command_producer_evidence(
                command_correlations
            )
            if instruction:
                messages.append({"role": "user", "content": instruction})
            return "sufficient", subject_key, seed.transition

        # A longer preceding command is a useful investigative clue, not
        # sufficient causal attribution. Preserve it for grounded synthesis.
        if requested_boundary:
            clue = render_preceding_command_candidates(
                current_evidence,
                subject=seed.name,
                transition=seed.transition,
                requested_boundary=requested_boundary,
            )
            if clue:
                messages.append({"role": "user", "content": clue})
                increment_active_metric("causal_preceding_command_clues")

        boundary_correlations = correlate_boundary_producers(
            self.evidence.receipts()
        )
        if boundary_producer_transition_sufficient(
            boundary_correlations,
            seed.transition,
            requested_boundary=requested_boundary if has_explicit_focal_clock(user_prompt) else None,
        ):
            increment_active_metric("causal_boundary_producer_provenance")
            boundary_kind = boundary_producer_transition_kind(
                boundary_correlations,
                seed.transition,
                requested_boundary=(
                    requested_boundary if has_explicit_focal_clock(user_prompt)
                    else None
                ),
            )
            boundary_match = boundary_producer_transition_match(
                boundary_correlations,
                seed.transition,
                requested_boundary=(
                    requested_boundary if has_explicit_focal_clock(user_prompt)
                    else None
                ),
            )
            if boundary_kind == "reporting_source" and boundary_match is not None:
                await self._collect_reporting_source_secondary_correlation(
                    subject_history=data,
                    transition=seed.transition,
                    boundary_match=boundary_match,
                    catalog=catalog,
                    completed_calls=completed_calls,
                    explicit_historical_focus=has_explicit_focal_clock(user_prompt),
                )
                if (
                    seed.transition == "on"
                    and wants_deep_investigation(user_prompt)
                ):
                    await self._collect_physical_response_evidence(
                        subject_history=data,
                        boundary_match=boundary_match,
                        catalog=catalog,
                        completed_calls=completed_calls,
                    )
            return "sufficient", subject_key, seed.transition

        sufficient = await self._collect_causal_boundary_logs(
            catalog=catalog,
            completed_calls=completed_calls,
            messages=messages,
            original_user=user_prompt,
        )
        return (
            ("sufficient", subject_key, seed.transition)
            if sufficient
            else ("partial", subject_key, seed.transition)
        )


    async def _collect_focal_off_provenance(
        self,
        *,
        user_prompt: str,
        resolved_device_id: str,
        requested_transition: str = "on",
        catalog: ToolDiscoveryCatalog,
    ) -> None:
        """Read the focal OFF command and app context independently of ON.

        Bounded, read-only, and no assumption that the notified OFF listener
        produced the observed state. Failed or empty reads are not evidence of
        a missing command or an absent external automation.
        """
        focus = focal_closed_transition(
            self.evidence.receipts(), user_prompt,
            resolved_device_id=resolved_device_id,
            requested_transition=requested_transition,
        )
        if not focus:
            return
        if (
            requested_transition == "on"
            and has_explicit_focal_clock(user_prompt)
        ):
            requested_on = prompt_focal_transition_boundary(
                self.evidence.receipts(), "on", user_prompt,
            )
            if requested_on:
                try:
                    on_at = datetime.fromisoformat(
                        requested_on.replace("Z", "+00:00")
                    )
                    off_at = datetime.fromisoformat(
                        str(focus.get("end") or "").replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    on_at, off_at = None, None
                if (
                    on_at is not None and off_at is not None
                    and on_at.tzinfo and off_at.tzinfo
                    and (off_at - on_at).total_seconds() > 300
                ):
                    # A distant closing OFF is not a predecessor cause of
                    # the explicitly requested ON. Keep short-interval OFF
                    # provenance available as an independent observation,
                    # which is valuable for rapid toggles and existing
                    # source-backed transition analysis.
                    increment_active_metric("causal_irrelevant_off_skipped")
                    return
        prior_off = scoped_off_history_receipt(self.evidence.receipts(), focus)
        proven = positive_off_command_already_recorded(
            self.evidence.receipts(), focus
        )
        if proven:
            increment_active_metric("causal_off_command_reused")
        elif prior_off is None and catalog.available_tool("hub_read_devices") is not None:
            request = {
                "tool": "hub_list_device_events",
                "args": {
                    "deviceId": focus["deviceId"], "attribute": "command-off",
                    "hoursBack": 168, "limit": 50,
                },
            }
            started = time.monotonic()
            try:
                result = await self.mcp.call_tool("hub_read_devices", request)
                ok = self._tool_succeeded(result)
                data = result.data if ok and isinstance(result.data, dict) else {}
            except Exception as exc:
                logger.debug("Focal OFF command-history unavailable: %s", exc)
                ok, data = False, {}
            events = data.get("events")
            details = (
                {
                    "label": focus["subject"],
                    "deviceId": focus["deviceId"],
                    "eventName": "command-off",
                    "events": [
                        row for row in events[:50] if isinstance(row, dict)
                    ] if isinstance(events, list) else [],
                    "eventCount": len(events) if isinstance(events, list) else None,
                    "focalBoundary": focus["end"],
                    "historyScope": "bounded-returned-event-page",
                }
                if ok else None
            )
            self.evidence.record(
                "hub_read_devices", request, success=ok,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary="Focal OFF command page checked" if ok else
                "Focal OFF command page unavailable",
                supports_live_claim=ok,
                evidence_kind="authoritative_command_event_history",
                effect="read", mutates=False, details=details,
            )
            increment_active_metric("causal_off_provenance_reads")

        command_matches = [
            row for row in correlate_command_producers(self.evidence.receipts())
            if row.get("boundaryRole") == "end"
            and row.get("subject") == focus["subject"]
            and str(row.get("stateBoundary") or "")[:19] == focus["end"][:19]
            and not row.get("competingCommands")
        ]
        direct_app_id = next((
            str((row.get("producer") or {}).get("id") or "")
            for row in command_matches
            if str((row.get("producer") or {}).get("type") or "").casefold() == "app"
            and str((row.get("producer") or {}).get("id") or "")
        ), "")
        listeners = [
            item for item in (focus["offStateEvent"].get("triggered") or [])
            if isinstance(item, dict) and item.get("appId")
            and ("light" in str(item.get("handler") or "").casefold()
                 or "switch" in str(item.get("handler") or "").casefold())
        ]
        notified_app_id = str(listeners[0]["appId"]) if listeners else ""
        log_app_id = direct_app_id or notified_app_id
        if not log_app_id or catalog.available_tool("hub_read_diagnostics") is None:
            return
        off_time = datetime.fromisoformat(str(focus["end"]).replace("Z", "+00:00"))
        if off_time.tzinfo is None:
            return
        since = (off_time - timedelta(seconds=12)).astimezone(
            timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        until = (off_time + timedelta(seconds=6)).astimezone(
            timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        log_args = {"appId": log_app_id, "since": since, "until": until, "limit": 60}
        log_exists = any(
            row.get("success") is True and row.get("sub_tool") == "hub_get_logs"
            and str(((row.get("arguments") or {}).get("args") or {}).get("appId") or "")
                == log_app_id
            and ((row.get("arguments") or {}).get("args") or {}).get("since") == since
            for row in self.evidence.receipts()
        )
        if not log_exists:
            request = {"tool": "hub_get_logs", "args": log_args}
            started = time.monotonic()
            try:
                result = await self.mcp.call_tool("hub_read_diagnostics", request)
                ok = self._tool_succeeded(result)
                data = result.data if ok and isinstance(result.data, dict) else {}
            except Exception as exc:
                logger.debug("Focal OFF app logs unavailable: %s", exc)
                ok, data = False, {}
            rows = data.get("logs")
            self.evidence.record(
                "hub_read_diagnostics", request, success=ok,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary="Focal OFF app logs checked" if ok
                    else "Focal OFF app logs unavailable",
                supports_live_claim=ok, evidence_kind="native_log_history",
                effect="read", mutates=False,
                details=({
                    "appId": log_app_id,
                    "logCount": len(rows) if isinstance(rows, list) else None,
                    "scopedSince": since, "scopedUntil": until,
                    "execution": execution_log_lines(
                        data, {"command": {"date": focus["end"]}}
                    )[:8],
                } if ok else None),
            )
            increment_active_metric("causal_off_app_log_reads")

        # Compare source-scoped native app logs with archived messages, if the
        # app is explicitly allowlisted. Do not expose private log text or
        # turn a zero-row response into a negative execution claim.
        archive = getattr(self, "historical_journal", None)
        if (
            archive is not None
            and getattr(archive, "enabled", False)
            and getattr(archive, "_started", False)
            and getattr(archive, "capture_logs", False)
            and log_app_id in getattr(archive, "log_app_ids", set())
        ):
            stored = None
            started_archive = time.monotonic()
            try:
                stored = await asyncio.to_thread(
                    archive.query, app_id=log_app_id,
                    since=since, until=until, limit=60,
                )
            except (OSError, ValueError, RuntimeError) as error:
                logger.debug("Archived app-log evidence unavailable: %s", error)
            native_rows = [
                receipt.get("details") or {}
                for receipt in self.evidence.receipts()
                if receipt.get("sub_tool") == "hub_get_logs"
                and str((receipt.get("details") or {}).get("appId") or "") == log_app_id
                and (receipt.get("details") or {}).get("scopedSince") == since
                and receipt.get("success") is True
            ]
            native_count = (
                native_rows[-1].get("logCount")
                if native_rows and isinstance(native_rows[-1].get("logCount"), int)
                else None
            )
            self.evidence.record(
                "homebrain_archived_app_log_reconciliation",
                {"appId": log_app_id, "since": since, "until": until},
                success=stored is not None,
                elapsed_ms=round((time.monotonic() - started_archive) * 1000),
                summary="Bounded native and archived app-log sources reconciled",
                supports_live_claim=False,
                evidence_kind="partial_archived_app_log_evidence",
                effect="read", mutates=False,
                details=summarize_journal_app_logs(
                    stored, app_id=log_app_id, since=since, until=until,
                    native_count=native_count,
                ),
            )
            increment_active_metric("causal_archived_app_log_checks")

        # An explicit why-OFF request also needs the observed OFF listener's
        # current settings when no direct OFF command producer is identified.
        # That app remains a listener candidate, never a proven actor.
        context_app_id = (
            direct_app_id
            or (notified_app_id if requested_transition == "off" else "")
        )
        if not context_app_id or catalog.available_tool("hub_read_apps_code") is None:
            return
        checked = any(
            row.get("success") is True and row.get("sub_tool") == "hub_get_app_config"
            and str(((row.get("arguments") or {}).get("args") or {}).get("appId") or "")
                == context_app_id
            for row in self.evidence.receipts()
        )
        if checked:
            return
        request = {
            "tool": "hub_get_app_config",
            "args": {"appId": context_app_id, "includeSettings": False},
        }
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_read_apps_code", request)
            ok = self._tool_succeeded(result)
            data = result.data if ok and isinstance(result.data, dict) else {}
        except Exception as exc:
            logger.debug("Focal OFF app config unavailable: %s", exc)
            ok, data = False, {}
        excerpts, _ = configuration_text(data) if ok else ([], "")
        self.evidence.record(
            "hub_read_apps_code", request, success=ok,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary="Focal OFF producer config read" if ok
                else "Focal OFF producer config unavailable",
            supports_live_claim=False, evidence_kind="tool_result",
            effect="read", mutates=False,
            details=({
                "appId": context_app_id, "configured": excerpts[:8],
                "historicalExecutionNotProven": True,
            } if ok else None),
        )
        increment_active_metric("causal_off_app_config_reads")


    async def _collect_physical_response_evidence(
        self,
        *,
        subject_history: dict[str, Any],
        boundary_match: dict[str, Any],
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
    ) -> None:
        """Read relevant *after*-ON commands and one notified app's context.

        This is a bounded, read-only addition for comprehensive investigations
        of an externally reported state event. It does not assume that a Hue,
        Aqara, or other bridge-originated report was generated by an automation.
        The state event's triggered[] means "notified", never "issued ON".
        """
        subject_id = str(subject_history.get("deviceId") or "")
        boundary = str(boundary_match.get("stateBoundary") or "")
        try:
            at = datetime.fromisoformat(boundary.replace("Z", "+00:00"))
        except ValueError:
            return
        if at.tzinfo is None:
            return

        listeners = [
            item for item in ((boundary_match.get("event") or {}).get("triggered") or [])
            if isinstance(item, dict) and item.get("appId")
        ]
        # Prefer an actual device-state change listener over generic telemetry
        # or dashboard listeners, and inspect only one relevant notified app.
        lighting_listeners = [
            item for item in listeners
            if "light" in str(item.get("handler") or "").casefold()
            or "switch" in str(item.get("handler") or "").casefold()
        ]
        app_id = str(lighting_listeners[0].get("appId") or "") if lighting_listeners else ""
        requests: list[tuple[str, str, dict[str, Any], str]] = []
        # Earlier subject-prefetch history may already contain the precise
        # post-ON command and producer. Re-reading its 168-hour event page
        # cannot strengthen that positive provenance fact.
        post_on_already_observed = False
        for event in subject_history.get("commandEvents") or []:
            if (
                not isinstance(event, dict)
                or str(event.get("name") or "") != "command-setLevel"
                or not isinstance(event.get("producedBy"), dict)
            ):
                continue
            try:
                command_time = datetime.fromisoformat(
                    str(event.get("date") or "").replace("Z", "+00:00")
                )
                if command_time.tzinfo is None:
                    continue
                elapsed = (command_time - at).total_seconds()
            except (TypeError, ValueError):
                continue
            if 0 <= elapsed <= 5:
                post_on_already_observed = True
                break
        if post_on_already_observed:
            increment_active_metric("causal_physical_command_reused")
        elif subject_id and catalog.available_tool("hub_read_devices") is not None:
            requests.append((
                "hub_read_devices", "hub_list_device_events",
                {
                    "deviceId": subject_id, "attribute": "command-setLevel",
                    "hoursBack": 168, "limit": 50,
                },
                "authoritative_command_event_history",
            ))
        if app_id and catalog.available_tool("hub_read_apps_code") is not None:
            requests.append((
                "hub_read_apps_code", "hub_get_app_config",
                {"appId": app_id, "includeSettings": False},
                "tool_result",
            ))
        if app_id and catalog.available_tool("hub_read_diagnostics") is not None:
            requests.append((
                "hub_read_diagnostics", "hub_get_logs",
                {
                    "appId": app_id,
                    "since": (at - timedelta(seconds=12)).astimezone(
                        timezone.utc
                    ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "until": (at + timedelta(seconds=6)).astimezone(
                        timezone.utc
                    ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "limit": 60,
                },
                "native_log_history",
            ))

        async def read_one(item: tuple[str, str, dict[str, Any], str]):
            gateway, leaf, args, kind = item
            started = time.monotonic()
            try:
                result = await self.mcp.call_tool(
                    gateway, {"tool": leaf, "args": args}
                )
                ok = self._tool_succeeded(result)
                data = result.data if ok and isinstance(result.data, dict) else {}
            except Exception as error:
                logger.debug("Physical causal followup %s unavailable: %s", leaf, error)
                ok, data = False, {}
            details: dict[str, Any] = {}
            if ok and leaf == "hub_list_device_events":
                rows = data.get("events") or []
                details = {
                    "label": str(subject_history.get("label") or ""),
                    "deviceId": subject_id, "attribute": "command-setLevel",
                    "eventName": "command-setLevel",
                    "events": [row for row in rows if isinstance(row, dict)][:50],
                    "eventCount": len(rows),
                }
            elif ok and leaf == "hub_get_app_config":
                app = data.get("app") or {}
                excerpts, _text = (
                    configuration_text(data)
                    if str(app.get("id") or "") == app_id
                    else ([], "")
                )
                details = {
                    "appId": app_id, "checked": True,
                    "configured": excerpts[:8],
                    "historicalExecutionNotProven": True,
                }
            elif ok and leaf == "hub_get_logs":
                rows = data.get("logs") or []
                details = {
                    "appId": app_id, "logCount": len(rows),
                    "scopedSince": str(args["since"]),
                    "scopedUntil": str(args["until"]),
                    "execution": [
                        row for row in rows[:8] if isinstance(row, dict)
                    ],
                }
            self.evidence.record(
                gateway, {"tool": leaf, "args": args},
                success=ok,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=(
                    f"Focused post-state response: {leaf} "
                    + ("checked" if ok else "unavailable")
                ),
                supports_live_claim=ok and leaf != "hub_get_app_config",
                evidence_kind=kind,
                effect="read", mutates=False,
                details=details or None,
            )
            return ok

        if requests:
            await asyncio.gather(*(read_one(item) for item in requests))
            increment_active_metric("causal_physical_response_reads", len(requests))


    async def _collect_reporting_source_secondary_correlation(
        self,
        *,
        subject_history: dict[str, Any],
        transition: str,
        boundary_match: dict[str, Any],
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        explicit_historical_focus: bool = False,
    ) -> None:
        """Run bounded multi-candidate correlation for bridge/device provenance."""

        filter_tool = catalog.declared_tool(_LOCAL_FILTER_TOOL)
        history_tool = catalog.declared_tool(_LOCAL_DEVICE_HISTORY_TOOL)
        room_arguments = subject_room_filter_arguments(subject_history)
        if history_tool is None or room_arguments is None:
            return

        started = time.monotonic()
        increment_active_metric("causal_reporting_source_correlation")
        increment_active_metric("causal_room_plan")

        # Candidate discovery is structural, not a live-state claim. Reuse the
        # fresh authoritative identity snapshot when it contains enough
        # capability/attribute shape to rank the same bounded controller and
        # occupancy candidates. This avoids a full bulk live-context read solely
        # to rediscover room membership. If the cached snapshot cannot safely
        # prove occupancy attribute exposure, fall back to the existing live
        # room filter.
        filter_data: dict[str, Any] = {}
        candidate_inventory: list[dict[str, Any]] = []
        cached_candidate_plan = False
        peek_identities = getattr(self.mcp, "peek_device_identities", None)
        if callable(peek_identities):
            try:
                identities = [
                    dict(item)
                    for item in (peek_identities() or [])
                    if isinstance(item, dict)
                ]
            except Exception:
                identities = []
            if identities:
                candidate_inventory = identities
                cached_hints = DeviceQueryService.cached_room_event_source_hints(
                    identities,
                    room_arguments.get("value"),
                )

                # A newer detailed identity manifest can legitimately outrank an
                # older (but still identity-TTL-fresh) live-context snapshot while
                # carrying less attribute shape. Before paying for another whole-
                # home live read, borrow only attribute names from the cached
                # context and keep the newer identity rows authoritative for
                # device ID, label, room, capabilities, and commands.
                if cached_hints is None:
                    peek_context = getattr(
                        self.mcp,
                        "peek_cached_live_context_devices",
                        None,
                    )
                    try:
                        context_devices = (
                            [
                                dict(item)
                                for item in (peek_context() or [])
                                if isinstance(item, dict)
                            ]
                            if callable(peek_context)
                            else []
                        )
                    except Exception:
                        context_devices = []
                    if context_devices:
                        enriched_identities = (
                            DeviceQueryService.enrich_identity_attribute_shape(
                                identities,
                                context_devices,
                            )
                        )
                        candidate_inventory = enriched_identities
                        cached_hints = (
                            DeviceQueryService.cached_room_event_source_hints(
                                enriched_identities,
                                room_arguments.get("value"),
                            )
                        )
                        if cached_hints is not None:
                            increment_active_metric(
                                "causal_cached_context_shape_plan"
                            )

                if cached_hints is not None:
                    filter_data = (
                        {"eventSourceHints": cached_hints}
                        if cached_hints
                        else {}
                    )
                    cached_candidate_plan = True
                    increment_active_metric("causal_cached_candidate_plan")
                else:
                    increment_active_metric(
                        "causal_cached_candidate_plan_fallback"
                    )

        if not cached_candidate_plan:
            if filter_tool is None:
                return
            filter_execution = await self.executor.execute(
                _LOCAL_FILTER_TOOL,
                room_arguments,
                tool=filter_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_FILTER_TOOL],
            )
            completed_calls.add(json.dumps(
                [_LOCAL_FILTER_TOOL, room_arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            filter_data = (
                filter_execution.result.data
                if filter_execution.result is not None
                and isinstance(filter_execution.result.data, dict)
                else {}
            )

        controller_specs = controller_history_candidates(
            filter_data,
            limit=2,
        )
        sensor_pool = trigger_sensor_history_candidates(
            filter_data,
            limit=8,
        )
        ranked_sensor_specs, sensor_priority_plan = prioritize_focal_sensor_candidates(
            sensor_pool,
            candidate_inventory,
            self.known_automations,
            subject=str(subject_history.get("label") or ""),
            subject_room=str(subject_history.get("room") or ""),
            transition=transition,
            limit=4,
        )
        sensor_specs = ranked_sensor_specs[:2]
        fallback_sensor_specs = ranked_sensor_specs[2:4]
        sensor_priority_plan["initialProbeSensorIds"] = [
            str((item.get("candidate") or {}).get("id") or "")
            for item in sensor_specs
        ]
        sensor_priority_plan["fallbackProbeSensorIds"] = [
            str((item.get("candidate") or {}).get("id") or "")
            for item in fallback_sensor_specs
        ]
        if sensor_priority_plan["topologyUsed"]:
            increment_active_metric("causal_topology_sensor_plan")
        if sensor_priority_plan["configuredCandidatesSelected"]:
            increment_active_metric("causal_configured_sensor_prioritized")
        topology_sensor_visibility = known_automation_sensor_candidate_visibility(
            [*sensor_specs, *sensor_pool],
            sensor_specs,
            self.known_automations,
            subject=subject_history.get("label"),
            transition=transition,
        )
        topology_sensor_fallbacks = sum(
            1
            for row in topology_sensor_visibility
            if isinstance(row, dict)
            and row.get("unavailableSourceSensors")
            and row.get("fallbackDerivedSensors")
        )
        if topology_sensor_fallbacks:
            increment_active_metric(
                "causal_topology_sensor_fallback",
                topology_sensor_fallbacks,
            )

        def grounded_history_arguments(
            spec: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            candidate = (
                dict(spec.get("candidate"))
                if isinstance(spec.get("candidate"), dict)
                else {}
            )
            arguments: dict[str, Any] = {
                "name": str(spec.get("name") or ""),
                "attribute": str(spec.get("attribute") or ""),
                "hours_back": 48,
                "limit": 50,
            }
            if candidate:
                arguments["_resolved_target"] = candidate
            return arguments, candidate

        journal_summary: dict[str, Any] | None = None
        # A local journal may preserve real-time Hubitat observations that
        # have rotated out of the MCP server's native event history. It is
        # deliberately a distinct, WEAKER evidence source: many Hubitat
        # socket frames contain no original event timestamp, so their
        # collector-reception time must not be treated as exact provenance.
        archive = getattr(self, "historical_journal", None)
        archive_rows: list[dict[str, Any]] = []
        if (
            transition == "off"
            and archive is not None
            and getattr(archive, "enabled", False)
            and getattr(archive, "_started", False)
        ):
            for spec in sensor_specs[:2]:
                scope = build_focal_sensor_window_probe(
                    spec, boundary_match.get("stateBoundary")
                )
                if scope is None:
                    continue
                try:
                    retrieved = await asyncio.to_thread(
                        archive.query,
                        since=scope["since"], until=scope["until"],
                        device_id=scope["deviceId"],
                        attribute=scope["attribute"], limit=40,
                    )
                except Exception as exc:
                    logger.warning(
                        "Historical journal window read unavailable: %s",
                        type(exc).__name__,
                    )
                    archive_rows.append({
                        "deviceId": scope["deviceId"],
                        "label": str(spec.get("name") or ""),
                        "attribute": scope["attribute"],
                        "status": "unavailable", "eventCount": 0,
                    })
                    continue
                observations = [
                    {
                        "value": item.get("value"),
                        "observedAt": item.get("observed_at"),
                        "timestampBasis": item.get("timestamp_basis"),
                        "captureSource": item.get("source"),
                    }
                    for item in (retrieved.get("events") or [])[:40]
                    if isinstance(item, dict) and item.get("stream") == "events"
                ]
                archive_rows.append({
                    "deviceId": scope["deviceId"],
                    "label": str(spec.get("name") or ""),
                    "attribute": scope["attribute"],
                    "status": "archived-partial-observations",
                    "eventCount": len(observations),
                    "events": observations,
                    "coverageComplete": False,
                    "gapCount": len(retrieved.get("gaps") or []),
                    "emptyProvesNoMotion": False,
                })
            if archive_rows:
                journal_summary = {
                    "status": "partial-archive-not-causal-proof",
                    "sensors": archive_rows,
                    "timestampBasis": "source timestamp if available, otherwise collector received",
                    "historicalCompletenessVerified": False,
                    "archivedSensorEventsAreNotOffCommandProvenance": True,
                    "lookupOrder": "journal-before-mcp",
                }


        async def read_focal_window(spec, args):
            started_window = time.monotonic()
            request = {"tool": "hub_list_device_events", "args": args}
            try:
                result = await self.mcp.call_tool("hub_read_devices", request)
                ok = self._tool_succeeded(result)
                data = result.data if ok and isinstance(result.data, dict) else {}
            except Exception as error:
                logger.debug("Focal sensor history window unavailable: %s", error)
                ok, data = False, {}
            verified = verify_windowed_sensor_reply(args, data if ok else None)
            details = {
                "label": str(spec.get("name") or ""),
                "deviceId": args["deviceId"],
                "attribute": args["attribute"],
                "windowVerified": verified.get("status") == "verified-window",
                "events": verified.get("events") or [],
                "eventCount": len(verified.get("events") or []),
                "historyScope": "bounded-absolute-window",
                "sourceHistoryComplete": False,
            }
            self.evidence.record(
                "hub_read_devices", request, success=ok,
                elapsed_ms=round((time.monotonic() - started_window) * 1000),
                summary=(
                    "Focal sensor absolute window: " +
                    str(verified.get("status") or "unavailable")
                ),
                supports_live_claim=verified.get("status") == "verified-window",
                evidence_kind="authoritative_device_event_history",
                effect="read", mutates=False, details=details,
            )
            return spec, verified


        # When the journal is available, check focal archived observations
        # FIRST, then ask MCP for one verified absolute window. Do not read
        # a newest-N sensor page first and then ask the same server for the
        # requested historical window. The journal is not command provenance.
        journal_first = bool(
            transition == "off"
            and archive is not None
            and getattr(archive, "enabled", False)
            and getattr(archive, "_started", False)
        )
        # A requested *historical ON* must use the named ON timestamp to
        # query the focal sensor window. Newest-N pages frequently contain
        # only subsequent mornings, yielding false absence and fan-out.
        # Server-side explicit since/until echoes remain mandatory: a
        # backend ignoring time filters never establishes historical data.
        focal_window_first = (
            journal_first or (
                explicit_historical_focus
                and transition == "on"
                and bool(boundary_match.get("stateBoundary"))
            )
        )
        direct_attempted_ids: set[str] = set()
        direct_sensor_data: list[dict[str, Any]] = []
        focal_window_probes: list[dict[str, Any]] = []
        if (
            focal_window_first
            and callable(getattr(catalog, "available_tool", None))
            and catalog.available_tool("hub_read_devices") is not None
        ):
            selections = []
            for spec in sensor_specs[:2]:
                args = build_focal_sensor_window_probe(
                    spec, boundary_match.get("stateBoundary")
                )
                if args and args["deviceId"] not in direct_attempted_ids:
                    direct_attempted_ids.add(args["deviceId"])
                    selections.append((spec, args))
            if selections:
                results = await asyncio.gather(*(
                    read_focal_window(spec, args)
                    for spec, args in selections
                ))
                for (spec, args), (_source_spec, reply) in zip(selections, results):
                    outcome = str(reply.get("status") or "unavailable")
                    rows = list(reply.get("events") or [])
                    focal_window_probes.append({
                        "deviceId": args["deviceId"],
                        "label": str(spec.get("name") or ""),
                        "status": outcome,
                        "eventCount": len(rows),
                        "retrievalOrder": (
                        "journal-first-direct-window" if journal_first
                        else "historical-on-direct-window"
                    ),
                    })
                    if outcome != "verified-window":
                        continue
                    candidate = spec.get("candidate") or {}
                    direct_sensor_data.append({
                        "label": str(spec.get("name") or ""),
                        "deviceId": args["deviceId"],
                        "attribute": args["attribute"],
                        "room": candidate.get("room") or subject_history.get("room"),
                        "candidateMatchBasis": candidate.get("matchBasis"),
                        "candidateRoom": candidate.get("room"),
                        "events": rows,
                        "observedEvents": rows,
                        "sourceHistoryComplete": False,
                        "windowedEvidenceVerified": True,
                        "historyScope": "bounded-absolute-window",
                    })
                increment_active_metric(
                    "causal_focal_window_reads", len(selections)
                )
                if any(
                    item["status"] == "verified-window"
                    and item["eventCount"] > 0
                    for item in focal_window_probes
                ):
                    increment_active_metric(
                        "causal_focal_window_evidence_recovered"
                    )
                # If both first-choice historical windows were verified but
                # yielded no events, probe up to two other ranked, distinct
                # occupancy sources before concluding the focal sensor evidence
                # is unavailable. An unverified initial window is NOT treated
                # as a negative sensor observation.
                elif (
                    explicit_historical_focus and transition == "on"
                    and len(focal_window_probes) == len(selections)
                    and all(row["status"] == "verified-window"
                            for row in focal_window_probes)
                    and fallback_sensor_specs
                ):
                    extras = []
                    for spec in fallback_sensor_specs:
                        args = build_focal_sensor_window_probe(
                            spec, boundary_match.get("stateBoundary")
                        )
                        if args and args["deviceId"] not in direct_attempted_ids:
                            direct_attempted_ids.add(args["deviceId"])
                            extras.append((spec, args))
                    if extras:
                        recovered = await asyncio.gather(*(
                            read_focal_window(spec, args)
                            for spec, args in extras
                        ))
                        for (spec, args), (_spec, reply) in zip(extras, recovered):
                            rows = list(reply.get("events") or [])
                            status = str(reply.get("status") or "unavailable")
                            focal_window_probes.append({
                                "deviceId": args["deviceId"],
                                "label": str(spec.get("name") or ""),
                                "status": status,
                                "eventCount": len(rows),
                                "retrievalOrder": "historical-empty-window-backup",
                            })
                            if status == "verified-window":
                                candidate = spec.get("candidate") or {}
                                direct_sensor_data.append({
                                    "label": str(spec.get("name") or ""),
                                    "deviceId": args["deviceId"],
                                    "attribute": args["attribute"],
                                    "room": candidate.get("room") or subject_history.get("room"),
                                    "candidateMatchBasis": candidate.get("matchBasis"),
                                    "events": rows, "observedEvents": rows,
                                    "sourceHistoryComplete": False,
                                    "windowedEvidenceVerified": True,
                                    "historyScope": "bounded-absolute-window",
                                })
                        increment_active_metric(
                            "causal_focal_window_reads", len(extras)
                        )
                        increment_active_metric(
                            "causal_historical_sensor_fallback_reads", len(extras)
                        )

        pending: list[
            tuple[str, dict[str, Any], dict[str, Any]]
        ] = []
        for spec in controller_specs:
            arguments, candidate = grounded_history_arguments(spec)
            increment_active_metric("causal_provenance_read")
            pending.append(("controller", arguments, candidate))
        for spec in sensor_specs:
            candidate = spec.get("candidate") or {}
            device_id = str(candidate.get("id") or "")
            if any(
                str(row.get("deviceId") or "") == device_id
                for row in direct_sensor_data
            ):
                # Confirmed absolute MCP window: newest-N would be redundant.
                continue
            arguments, candidate = grounded_history_arguments(spec)
            increment_active_metric("causal_sensor_read")
            pending.append(("sensor", arguments, candidate))

        # One unfiltered subject-event page lets deterministic analysis prove
        # patterns such as external ON -> level 100 -> downstream setLevel
        # recovery without asking a model to infer causation from screenshots or
        # unrelated logs.
        subject_label = str(subject_history.get("label") or "").strip()
        subject_id = str(subject_history.get("deviceId") or "").strip()
        if subject_label and subject_id:
            subject_target = {
                "id": subject_id,
                "label": subject_label,
                "name": subject_label,
                "room": subject_history.get("room"),
                "capabilities": subject_history.get("capabilities") or [],
            }
            subject_arguments: dict[str, Any] = {
                "name": subject_label,
                "hours_back": 48,
                "limit": 50,
                "_resolved_target": subject_target,
            }
            increment_active_metric("causal_subject_pattern_read")
            pending.append(("subject-events", subject_arguments, subject_target))

        async def read_history(
            arguments: dict[str, Any],
        ):
            return await self.executor.execute(
                _LOCAL_DEVICE_HISTORY_TOOL,
                arguments,
                tool=history_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
            )

        executions = (
            await asyncio.gather(
                *(read_history(arguments) for _kind, arguments, _meta in pending)
            )
            if pending
            else []
        )

        controller_data: list[dict[str, Any]] = []
        sensor_data: list[dict[str, Any]] = list(direct_sensor_data)
        subject_event_data: dict[str, Any] | None = None
        for (kind, arguments, metadata), execution in zip(pending, executions):
            completed_calls.add(json.dumps(
                [_LOCAL_DEVICE_HISTORY_TOOL, {
                    key: value
                    for key, value in arguments.items()
                    if not str(key).startswith("_")
                }],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            data = (
                dict(execution.result.data)
                if execution.result is not None
                and isinstance(execution.result.data, dict)
                else None
            )
            if not isinstance(data, dict):
                continue
            if kind in {"controller", "sensor"}:
                if metadata:
                    data["candidateMatchBasis"] = metadata.get("matchBasis")
                    data["candidateRoom"] = metadata.get("room")
                if kind == "controller":
                    controller_data.append(data)
                else:
                    sensor_data.append(data)
            else:
                subject_event_data = data

        analysis = build_reporting_source_secondary_analysis(
            subject_history,
            transition=transition,
            requested_boundary=boundary_match.get("stateBoundary"),
            controller_histories=controller_data,
            sensor_histories=sensor_data,
            subject_event_history=subject_event_data,
            known_automations=self.known_automations,
        )
        # The MCP Rule Server supports since/until on hub_list_device_events
        # and filters its native event store before the returned result limit.
        # Recover up to two room-local sensor windows if our recent-N reads
        # never reached the requested historical OFF boundary. Confirm that
        # the *installed* server echoes BOTH bounds before using any rows.
        initial_coverage = assess_local_sensor_history_coverage(
            sensor_data, boundary_match.get("stateBoundary")
        ) if transition == "off" else {}
        if (
            transition == "off"
            and initial_coverage.get("status") ==
                "pre-focal-not-observed-in-returned-pages"
            and callable(getattr(catalog, "available_tool", None))
            and catalog.available_tool("hub_read_devices") is not None
        ):
            selections = []
            seen_ids: set[str] = set(direct_attempted_ids)
            for spec in sensor_specs:
                args = build_focal_sensor_window_probe(
                    spec, boundary_match.get("stateBoundary")
                )
                if args is not None and args["deviceId"] not in seen_ids:
                    seen_ids.add(args["deviceId"])
                    selections.append((spec, args))
                if len(selections) >= 2:
                    break


            if selections:
                late_probes = [
                    {"deviceId": args["deviceId"], "label": str(spec.get("name") or ""),
                     "status": "attempted", "retrievalOrder": "recent-page-fallback"}
                    for spec, args in selections
                ]
                recovered = await asyncio.gather(*(
                    read_focal_window(spec, args) for spec, args in selections
                ))
                for index, (spec, reply) in enumerate(recovered):
                    late_probes[index]["status"] = reply.get("status")
                    late_probes[index]["eventCount"] = len(
                        reply.get("events") or []
                    )
                    if reply.get("status") != "verified-window":
                        continue
                    for idx, history in enumerate(sensor_data):
                        if str(history.get("label") or "") == str(spec.get("name") or ""):
                            sensor_data[idx] = merge_windowed_sensor_history(
                                history, reply
                            )
                            break
                focal_window_probes.extend(late_probes)
                increment_active_metric(
                    "causal_focal_window_reads", len(selections)
                )
                if any(row.get("status") == "verified-window"
                       and row.get("eventCount") for row in focal_window_probes):
                    increment_active_metric("causal_focal_window_evidence_recovered")
                analysis = build_reporting_source_secondary_analysis(
                    subject_history,
                    transition=transition,
                    requested_boundary=boundary_match.get("stateBoundary"),
                    controller_histories=controller_data,
                    sensor_histories=sensor_data,
                    subject_event_history=subject_event_data,
                    known_automations=self.known_automations,
                )

        # For a historical OFF event, room-local newest-N pages can lose
        # the event that prompted the question. Do not broaden to unrelated
        # sensors when the primary historical evidence is no longer visible.
        local_history_coverage = assess_local_sensor_history_coverage(
            sensor_data, boundary_match.get("stateBoundary")
        ) if transition == "off" else {}
        focal_history_gap = bool(
            local_history_coverage.get("status") ==
            "pre-focal-not-observed-in-returned-pages"
        )
        if focal_history_gap:
            increment_active_metric("causal_focal_history_gap_stop")
        # Adaptive evidence selection: when a device change came through a
        # reporting bridge and room-based sensors do not give a strong lead,
        # test bounded, capability-grounded candidates across integrations.
        # This is discovery and temporal comparison, never command provenance.
        initial_sensor_attempts = len(sensor_specs)
        expanded_sensor_attempts = 0
        all_candidate_specs: list[dict[str, Any]] = []
        # Room-local occupancy alternatives have already been inspected.
        # A unique repeated controller pattern at the requested ON boundary
        # is sufficient to stop *unrelated* cross-room exploratory reads,
        # without proving a native Hue/button mapping.
        repeated_controller = has_repeated_requested_controller_candidate(analysis)
        if repeated_controller:
            increment_active_metric("causal_controller_sufficient_stop")
        local_off_evidence = has_local_requested_off_correlation(analysis)
        if local_off_evidence:
            # The room-local OFF hypothesis is investigated, but *not*
            # verified. No unrelated cross-room exploration is needed to
            # conclude safely that OFF command ownership remains unknown.
            increment_active_metric("causal_local_off_evidence_stop")
        if not (
            repeated_controller
            or local_off_evidence
            or focal_history_gap
            or bool(focal_window_probes)
            or has_strong_requested_correlated_candidate(analysis)
        ):
            tried_ids = {
                str((spec.get("candidate") or {}).get("id") or "")
                for spec in sensor_specs if isinstance(spec, dict)
            }
            tried_ids.add(subject_id)
            all_candidate_specs = plan_cross_integration_candidates(
                candidate_inventory,
                subject=subject_label,
                subject_room=str(subject_history.get("room") or ""),
                transition=transition,
                tried_ids=tried_ids,
                known_automations=self.known_automations,
            )
            for batch_start in range(
                0, min(len(all_candidate_specs), MAX_EXTRA_SENSOR_READS), SENSOR_BATCH_SIZE
            ):
                batch = all_candidate_specs[
                    batch_start: min(batch_start + SENSOR_BATCH_SIZE, MAX_EXTRA_SENSOR_READS)
                ]
                expanded_sensor_attempts += len(batch)
                increment_active_metric("causal_adaptive_expansion")
                increment_active_metric("causal_adaptive_sensor_reads", len(batch))
                extra_pending = [
                    (spec, *grounded_history_arguments(spec))
                    for spec in batch
                ]
                extra_executions = await asyncio.gather(*(
                    read_history(arguments)
                    for _spec, arguments, _candidate in extra_pending
                ))
                for (_spec, arguments, candidate), execution in zip(
                    extra_pending, extra_executions
                ):
                    completed_calls.add(json.dumps(
                        [_LOCAL_DEVICE_HISTORY_TOOL, {
                            key: value for key, value in arguments.items()
                            if not str(key).startswith("_")
                        }],
                        sort_keys=True,
                        ensure_ascii=False,
                        default=str,
                    ))
                    if (
                        execution.result is None
                        or not isinstance(execution.result.data, dict)
                        or not execution.success
                    ):
                        continue
                    data = dict(execution.result.data)
                    data["candidateMatchBasis"] = candidate.get("matchBasis")
                    data["candidateRoom"] = candidate.get("room")
                    sensor_data.append(data)
                analysis = build_reporting_source_secondary_analysis(
                    subject_history,
                    transition=transition,
                    requested_boundary=boundary_match.get("stateBoundary"),
                    controller_histories=controller_data,
                    sensor_histories=sensor_data,
                    subject_event_history=subject_event_data,
                    known_automations=self.known_automations,
                )
                if has_strong_requested_correlated_candidate(analysis):
                    increment_active_metric("causal_adaptive_sufficient_stop")
                    break
        if expanded_sensor_attempts:
            increment_active_metric("causal_adaptive_candidate_plans")
        analysis["sensorSelection"] = sensor_priority_plan
        if focal_window_probes:
            analysis["focalWindowRetrieval"] = focal_window_probes
        if journal_summary:
            analysis["historicalJournal"] = journal_summary
            analysis["journalFirstPlan"] = {
                "journalSensorsChecked": len(archive_rows),
                "directWindowReads": len(direct_attempted_ids),
                "directWindowVerified": len(direct_sensor_data),
                "recentPageSensorFallbacks": sum(
                    1 for kind, _args, _meta in pending if kind == "sensor"
                ),
                "archivedRowsNeverPromotedToMcpFacts": True,
                "journalEmptyDoesNotProveInactivity": True,
            }

        if local_history_coverage:
            analysis["localSensorHistoryCoverage"] = reconcile_window_coverage(
                local_history_coverage, focal_window_probes
            )
        analysis["hypotheses"] = rank_causal_hypotheses(analysis)
        analysis["discoveryCoverage"] = {
            "roomFirstAttempted": initial_sensor_attempts,
            "outsideRoomAttempted": expanded_sensor_attempts,
            "indexedCandidatesOutsideRoom": len(all_candidate_specs),
            "unexaminedIndexedCandidates": max(
                0, len(all_candidate_specs) - expanded_sensor_attempts
            ),
            "crossIntegrationInventoryAvailable": bool(candidate_inventory),
            "crossRoomSkippedForLocalOffEvidence": bool(local_off_evidence),
            "crossRoomSkippedForFocalHistoryGap": bool(focal_history_gap),
            "localOffEvidenceIsNotCausalProof": True,
            "historicalExternalAutomationTraceVerified": False,
        }
        if len(all_candidate_specs) > expanded_sensor_attempts:
            increment_active_metric("causal_adaptive_unexamined_candidates")
        if topology_sensor_visibility:
            analysis["knownAutomationSensorVisibility"] = (
                topology_sensor_visibility
            )
        controller_rows = [
            row
            for item in analysis.get("controllers", [])
            if isinstance(item, dict)
            for row in item.get("relevantAlignments", [])
            if isinstance(row, dict)
        ]
        sensor_rows = [
            row
            for item in analysis.get("sensors", [])
            if isinstance(item, dict)
            for row in item.get("relevantCorrelations", [])
            if isinstance(row, dict)
        ]
        if controller_rows:
            increment_active_metric(
                "causal_provenance_aligned",
                len(controller_rows),
            )
        if sensor_rows:
            increment_active_metric(
                "causal_sensor_aligned",
                len(sensor_rows),
            )
        recovery = (
            analysis.get("levelRecovery")
            if isinstance(analysis.get("levelRecovery"), dict)
            else {}
        )
        if recovery.get("matchCount"):
            increment_active_metric(
                "causal_level_recovery_pattern",
                int(recovery.get("matchCount") or 0),
            )
        known_matches = [
            row
            for row in (analysis.get("knownAutomationMatches") or [])
            if isinstance(row, dict)
        ]
        if known_matches:
            increment_active_metric(
                "causal_known_automation_match",
                len(known_matches),
            )
        composite_sensor_matches = sum(
            len([
                item
                for item in (row.get("matchedDerivedSensors") or [])
                if isinstance(item, dict)
            ])
            for row in known_matches
        )
        if composite_sensor_matches:
            increment_active_metric(
                "causal_composite_sensor_match",
                composite_sensor_matches,
            )

        self.evidence.record(
            "homebrain_causal_secondary_correlation",
            {
                "subject": subject_history.get("label"),
                "room": subject_history.get("room"),
                "transition": transition,
            },
            success=True,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=(
                "bounded reporting-source correlation: "
                f"controllers={len(controller_data)}, "
                f"controller_alignments={len(controller_rows)}, "
                f"sensors={len(sensor_data)}, "
                f"sensor_correlations={len(sensor_rows)}, "
                f"level_recoveries={int(recovery.get('matchCount') or 0)}, "
                f"known_automation_matches={len(known_matches)}, "
                f"composite_sensor_matches={composite_sensor_matches}, "
                f"topology_sensor_fallbacks={topology_sensor_fallbacks}, "
                f"adaptive_reads={expanded_sensor_attempts}, "
                f"adaptive_candidates_unexamined={max(0, len(all_candidate_specs) - expanded_sensor_attempts)}"
            ),
            supports_live_claim=True,
            evidence_kind="deterministic_causal_secondary_correlation",
            effect=ToolEffect.READ,
            details=analysis,
        )

    async def _collect_causal_boundary_logs(
        self,
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
        original_user: str = "",
    ) -> bool:
        """Collect both subject boundaries from native logs before weaker evidence.

        Native logs are the closest available execution provenance. Query both
        start and end boundaries host-side so a repeated physical-controller
        pattern can be tested deterministically without spending a model round
        choosing log windows.
        """

        diagnostics_tool = catalog.declared_tool("hub_read_diagnostics")
        if diagnostics_tool is None:
            return False

        windows = causal_boundary_log_windows(
            self.evidence.receipts(),
            max_intervals=1,
            original_user=original_user,
        )
        if not windows:
            return False

        pending: list[tuple[dict[str, Any], str]] = []
        for window in windows:
            arguments = {
                "tool": "hub_get_logs",
                "args": {
                    "limit": 100,
                    "since": window["since"],
                    "until": window["until"],
                },
            }
            signature = json.dumps(
                ["hub_read_diagnostics", arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            if signature in completed_calls:
                continue
            completed_calls.add(signature)
            pending.append((arguments, window["boundaryRole"]))

        if not pending:
            correlations = correlate_native_log_boundaries(
                self.evidence.receipts()
            )
            return native_log_causal_provenance_sufficient(correlations)

        increment_active_metric("causal_native_log_reads", len(pending))

        async def read_one(
            arguments: dict[str, Any],
        ):
            return await self.executor.execute(
                "hub_read_diagnostics",
                arguments,
                tool=diagnostics_tool,
                supports_live_claim=True,
                evidence_kind="authoritative_native_log_history",
            )

        executions = await asyncio.gather(
            *(read_one(arguments) for arguments, _role in pending)
        )
        for (arguments, role), execution in zip(pending, executions):
            messages.append({
                "role": "tool",
                "tool_name": "hub_read_diagnostics",
                "content": execution.content,
            })
            messages.append({
                "role": "user",
                "content": (
                    "HOST NATIVE-LOG BOUNDARY READ\n"
                    f"Completed the host-derived {role} boundary log window "
                    f"{arguments['args']['since']} .. {arguments['args']['until']}. "
                    "This is direct current-turn provenance evidence."
                ),
            })

        correlations = correlate_native_log_boundaries(
            self.evidence.receipts()
        )
        if correlations:
            increment_active_metric(
                "causal_native_log_correlations",
                len(correlations),
            )
            instruction = render_native_log_correlation(correlations)
            if instruction:
                messages.append({"role": "user", "content": instruction})

        app_sufficient = native_log_app_execution_sufficient(correlations)
        closed_sufficient = native_log_provenance_sufficient(correlations)
        open_sufficient = native_log_open_start_sufficient(correlations)
        if app_sufficient:
            increment_active_metric("causal_native_app_execution_provenance")
        if closed_sufficient:
            increment_active_metric("causal_repeated_controller_pattern")
        if open_sufficient:
            increment_active_metric("causal_open_start_provenance")
        return bool(app_sufficient or closed_sufficient or open_sufficient)

    async def _expand_causal_subject_evidence(
        self,
        subject_history: dict[str, Any],
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
    ) -> bool:
        """Gather the fixed non-provenance causal evidence layer host-side.

        Causal reasoning should not spend separate model rounds rediscovering the
        same evidence classes. Native logs are tested first at both observed
        subject boundaries because they are stronger execution provenance than
        room correlation or app configuration. If a repeated physical-controller
        -> subject-command pattern is established at both boundaries, weaker
        discovery is skipped. Otherwise the established room/controller/location
        layer remains the compatibility fallback before one bounded provenance
        round.
        """

        expanded = False
        native_log_sufficient = await self._collect_causal_boundary_logs(
            catalog=catalog,
            completed_calls=completed_calls,
            messages=messages,
        )
        if native_log_sufficient:
            correlations = correlate_native_log_boundaries(
                self.evidence.receipts()
            )
            app_sufficient = native_log_app_execution_sufficient(correlations)
            open_sufficient = native_log_open_start_sufficient(correlations)
            closed_sufficient = native_log_provenance_sufficient(correlations)
            detail = (
                "Native logs contain a direct app Action: On execution targeting "
                "the causal subject immediately before the ON state boundary. "
                "Treat that app execution as direct producer provenance, not mere "
                "configuration evidence."
                if app_sufficient
                else (
                    "The subject interval is still OPEN. Native logs established a "
                    "physical controller/input immediately before the subject ON "
                    "command, with no closing OFF transition observed yet. This direct "
                    "start-boundary execution timing is sufficient for the turn-on "
                    "question; do not invent end-boundary corroboration or a duration."
                    if open_sufficient and not closed_sufficient
                    else (
                        "Repeated native-log provenance established the same physical "
                        "controller/input immediately before both the subject ON command "
                        "and the later OFF command."
                    )
                )
            )
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL EVIDENCE LAYER COMPLETE\n"
                    + detail
                    + " This direct execution evidence outranks room correlation "
                    "and app configuration, so do not fan out to weaker "
                    "device/sensor/location/config discovery. If the evidence is a "
                    "direct app Action: On, present that app as the execution producer "
                    "and preserve same-app Triggered:/Event: context as the bounded "
                    "trigger chain. Otherwise present the physical controller/input as "
                    "the strongest initiating-control candidate and retain the mapping "
                    "and person-identification caveats."
                ),
            })
            return True
        controller_checked = False
        room_arguments = subject_room_filter_arguments(subject_history)
        filter_tool = catalog.declared_tool(_LOCAL_FILTER_TOOL)

        if room_arguments is not None and filter_tool is not None:
            increment_active_metric("causal_room_plan")
            filter_execution = await self.executor.execute(
                _LOCAL_FILTER_TOOL,
                room_arguments,
                tool=filter_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_FILTER_TOOL],
            )
            messages.append({
                "role": "tool",
                "tool_name": _LOCAL_FILTER_TOOL,
                "content": filter_execution.content,
            })
            completed_calls.add(json.dumps(
                [_LOCAL_FILTER_TOOL, room_arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            expanded = True
            filter_data = (
                filter_execution.result.data
                if filter_execution.result is not None
                and isinstance(filter_execution.result.data, dict)
                else {}
            )

            controller_arguments = controller_history_arguments(filter_data)
            controller_tool = catalog.declared_tool(_LOCAL_DEVICE_HISTORY_TOOL)
            if controller_arguments is not None and controller_tool is not None:
                controller_checked = True
                increment_active_metric("causal_provenance_read")
                controller_execution = await self.executor.execute(
                    _LOCAL_DEVICE_HISTORY_TOOL,
                    controller_arguments,
                    tool=controller_tool,
                    supports_live_claim=True,
                    evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
                )
                messages.append({
                    "role": "tool",
                    "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
                    "content": controller_execution.content,
                })
                completed_calls.add(json.dumps(
                    [_LOCAL_DEVICE_HISTORY_TOOL, controller_arguments],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ))

                controller_data = (
                    controller_execution.result.data
                    if controller_execution.result is not None
                    and isinstance(controller_execution.result.data, dict)
                    else {}
                )
                alignments = controller_boundary_alignments(
                    subject_history, controller_data
                )
                alignment_instruction = render_controller_alignment_instruction(
                    alignments
                )
                if alignment_instruction:
                    increment_active_metric(
                        "causal_provenance_aligned", len(alignments)
                    )
                    messages.append({
                        "role": "user",
                        "content": alignment_instruction,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST CONTROLLER CORRELATION RESULT\n"
                            "The highest-ranked same-room controller was checked, "
                            "but no controller event aligned within two seconds of "
                            "any observed subject interval boundary. Treat that as "
                            "a negative correlation result, not proof that the "
                            "controller was uninvolved in every transition."
                        ),
                    })
            else:
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CONTROLLER CORRELATION RESULT\n"
                        "Exact-room discovery found no ranked button/controller "
                        "history candidate. Do not repeat the room scan."
                    ),
                })

            # One motion/presence history is justified only when material START
            # transitions remain unresolved after direct controller evidence.
            # This is capability-grounded from the same room scan and deliberately
            # excludes lux/temperature-only sensors.
            unresolved_after_controller = unresolved_material_timeline_rows(
                self.evidence.receipts()
            )
            sensor_arguments = (
                trigger_sensor_history_arguments(filter_data)
                if unresolved_after_controller
                else None
            )
            if sensor_arguments is not None and controller_tool is not None:
                increment_active_metric("causal_sensor_read")
                sensor_execution = await self.executor.execute(
                    _LOCAL_DEVICE_HISTORY_TOOL,
                    sensor_arguments,
                    tool=controller_tool,
                    supports_live_claim=True,
                    evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
                )
                messages.append({
                    "role": "tool",
                    "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
                    "content": sensor_execution.content,
                })
                completed_calls.add(json.dumps(
                    [_LOCAL_DEVICE_HISTORY_TOOL, sensor_arguments],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ))
                sensor_data = (
                    sensor_execution.result.data
                    if sensor_execution.result is not None
                    and isinstance(sensor_execution.result.data, dict)
                    else {}
                )
                correlations = sensor_transition_correlations(
                    subject_history,
                    sensor_data,
                )
                correlation_instruction = render_sensor_correlation_instruction(
                    correlations
                )
                if correlation_instruction:
                    increment_active_metric(
                        "causal_sensor_aligned",
                        len(correlations),
                    )
                    messages.append({
                        "role": "user",
                        "content": correlation_instruction,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST MOTION/PRESENCE CORRELATION RESULT\n"
                            "The highest-ranked same-room MotionSensor/PresenceSensor "
                            "was checked, but no material subject boundary correlation "
                            "met the deterministic timing windows. Do not fan out to "
                            "additional environmental sensors."
                        ),
                    })

        # Location/mode correlation is a stable evidence class for causal
        # investigations and does not require model-authored tool selection.
        location_tool = catalog.declared_tool(_LOCAL_LOCATION_EVENTS_TOOL)
        if location_tool is not None:
            try:
                history_hours = int(subject_history.get("hoursBack") or 24)
            except (TypeError, ValueError):
                history_hours = 24
            location_arguments = {
                "hours_back": min(168, max(1, history_hours)),
                "limit": 50,
            }
            increment_active_metric("causal_location_read")
            location_execution = await self.executor.execute(
                _LOCAL_LOCATION_EVENTS_TOOL,
                location_arguments,
                tool=location_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_LOCATION_EVENTS_TOOL],
            )
            messages.append({
                "role": "tool",
                "tool_name": _LOCAL_LOCATION_EVENTS_TOOL,
                "content": location_execution.content,
            })
            completed_calls.add(json.dumps(
                [_LOCAL_LOCATION_EVENTS_TOOL, location_arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            expanded = True

        # If material turn-on transitions remain unresolved, give the bounded
        # provenance round app/rule identity context up front. This is navigation
        # only, not causal proof, but it lets the model inspect a relevant app
        # configuration in the SAME provenance round as logs rather than spending
        # a later round listing apps first.
        unresolved_material = unresolved_material_timeline_rows(
            self.evidence.receipts()
        )
        log_windows = causal_log_windows(self.evidence.receipts())
        if log_windows:
            rows = [
                (
                    f"- {item.get('timelineId') or 'transition'}: subject "
                    f"{item.get('subjectStart')} -> native-log UTC window "
                    f"{item.get('since')} .. {item.get('until')}"
                )
                for item in log_windows
            ]
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL NATIVE-LOG WINDOWS\n"
                    + "\n".join(rows)
                    + "\nThese UTC boundaries were derived from the observed "
                    "Hubitat event timestamps. When selecting hub_get_logs, do not "
                    "invent or manually convert a clock time; the host will enforce "
                    "the matching since/until window on the call."
                ),
            })
        if (
            unresolved_material
            and "hub_read_apps_code" in catalog.available_names
        ):
            apps = await self._cached_app_manifest()
            if apps:
                increment_active_metric("causal_app_navigation")
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CAUSAL APP/RULE NAVIGATION\n"
                        + render_app_manifest(apps)
                        + "\nThis installed-app manifest is navigation context, "
                        "not evidence that any app caused the subject transition. "
                        "During the single bounded provenance round, prefer a "
                        "relevant app/rule DETAIL read (for example app config or "
                        "rule execution/config) alongside logs when both materially "
                        "test the unresolved transition. Do not spend the round "
                        "listing apps again."
                    ),
                })

        messages.append({
            "role": "user",
            "content": (
                "HOST CAUSAL EVIDENCE LAYER COMPLETE\n"
                "The host has completed the fixed subject-adjacent evidence "
                "layer: exact-room controller evidence when available; one "
                "capability-grounded motion/presence sensor when unresolved material "
                "turn-ons justified it; plus location/mode history clipped to the "
                "active history window. Do not request more device, sensor, "
                "controller, room, or "
                "location histories merely to be thorough. The next step is one "
                "bounded provenance selection from installed read-only log/rule/"
                "app gateways. When unresolved material transitions remain and "
                "app/rule identities were supplied above, issue up to two "
                "complementary reads in this SAME model round (for example logs "
                "plus one relevant app/rule detail), then synthesize."
            ),
        })
        return expanded

    async def _filter_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.filter_devices(arguments)

    async def _query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.query_devices(arguments)

    async def _device_inventory(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.device_inventory(arguments)

    async def _resolve_device(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.resolve_device(arguments)

    async def _weather_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.weather_snapshot(arguments)

    @staticmethod
    def _attribute_matches(actual: Any, operator: str, expected: Any) -> bool:
        return DeviceQueryService._attribute_matches(actual, operator, expected)

    async def _active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_lights(
            arguments, user_question=self._current_user_objective.get(),
        )

    async def _active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_rooms(arguments)

    async def _active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_switches(
            arguments, user_question=self._current_user_objective.get(),
        )

    async def _home_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.home_snapshot(arguments)

    async def _control_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceControlService(self.mcp, self.evidence.record)
        return await service.execute(arguments)

    @classmethod
    def _needs_device_manifest(cls, prompt: str) -> bool:
        return _matches(prompt, _DEVICE_TERMS) or any(
            re.search(pattern, prompt.lower()) is not None
            for pattern in _HOME_STATE_PATTERNS
        )

    def _include_identity_manifest(self, prompt: str) -> bool:
        """Never preload the full device inventory for a mutation.

        Every model-routed write must resolve its named target through the
        targeted local resolver.  Preloading all devices duplicates that work
        and live testing showed it adds roughly 30 seconds for 124 devices.
        App identity is handled separately by the bounded app manifest.
        """

        return False

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        return ToolExecutor.succeeded(result)

    @staticmethod
    def _is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
        return GroundingPolicy.is_live_log_call(name, arguments)

    @staticmethod
    def _initial_tools(tools: list[MCPTool]) -> list[MCPTool]:
        """Return a stable lean registry without inspecting the user prompt."""

        return ToolDiscoveryCatalog.initial_tools(tools)

    async def _cached_app_manifest(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._app_manifest and now - self._app_manifest_at < 300:
            return list(self._app_manifest)
        names = {tool.name for tool in await self.mcp.list_tools()}
        if "hub_read_apps_code" not in names:
            return []
        try:
            started = time.monotonic()
            result = await self.mcp.call_tool(
                "hub_read_apps_code",
                {"tool": "hub_list_apps", "args": {"scope": "instances"}},
            )
            self.evidence.record(
                "hub_read_apps_code",
                {"tool": "hub_list_apps", "args": {"scope": "instances"}},
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                supports_live_claim=False,
            )
            candidates = HubitatMCPClient._find_device_list(result.data) or []
            self._app_manifest = [item for item in candidates if isinstance(item, dict)]
            self._app_manifest_at = now
        except Exception as exc:
            logger.warning("Could not build app manifest: %s", exc)
        return list(self._app_manifest)

    async def _system_prompt(
        self, user_prompt: str = "", conversation_history: Any = None,
        *, skill_domains: tuple[str, ...] | None = None,
    ) -> str:
        manifest = "Device manifest omitted or unavailable."
        if self._include_identity_manifest(user_prompt):
            try:
                started = time.monotonic()
                devices = await self.mcp.get_cached_devices()
                self.evidence.record(
                    "hub_read_devices",
                    {"tool": "hub_list_devices", "source": "short_ttl_cache"},
                    success=True,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{len(devices)} identity records",
                    supports_live_claim=False,
                    evidence_kind="identity_manifest",
                )
                manifest = render_device_manifest(devices)
            except Exception as exc:
                logger.warning("Could not build live device manifest: %s", exc)
        app_section = ""
        previous_user_prompt = ""
        for message in reversed(self._history(conversation_history)):
            if message.get("role") != "user":
                continue
            content = str(message.get("content") or "")
            if content.strip().casefold() in CONFIRM_WORDS:
                continue
            previous_user_prompt = content
            break
        if (
            "automation" in skill_domains
            if skill_domains is not None
            else (
                _matches(user_prompt, _APP_TERMS)
                or _matches(previous_user_prompt, _APP_TERMS)
            )
        ):
            # App/rule identity context is loaded only when the conversation
            # actually asks for that evidence class. Generic investigations begin
            # from the fixed local history registry and activate the bounded
            # provenance registry later only when subject evidence warrants it.
            apps = await self._cached_app_manifest()
            app_section = render_app_manifest(apps)
        guidance = (
            build_mcp_skill_guidance_for_domains(skill_domains)
            if skill_domains is not None
            else build_mcp_skill_guidance(user_prompt)
        )
        return build_system_prompt(manifest, app_section) + "\n\n" + guidance

    @staticmethod
    def _tool_schema(tool: MCPTool) -> dict[str, Any]:
        return ToolDiscoveryCatalog.tool_schema(tool)

    def _history(self, history: Any) -> list[dict[str, Any]]:
        return self.context_policy.history(history)

    @staticmethod
    def _compact_tool_content(content: str, max_chars: int) -> str:
        return ModelContextPolicy.compact_tool_content(content, max_chars)

    def _bounded_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self.context_policy.bounded_messages(messages)

    def _result_payload(self, result: MCPToolResult) -> str:
        return self.executor.result_payload(result)

    @staticmethod
    def _discovered_tools(result: MCPToolResult, available: dict[str, MCPTool]) -> list[MCPTool]:
        return ToolDiscoveryCatalog.discovered_tools(result, available)

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.transport.chat(redact_model_messages(self._bounded_messages(messages)), tools)

    def _unverified_mutation_guard(self, content: str) -> str:
        if self._review_first_mode.get():
            # The conditional create was downgraded to a read-only review.
            # Keep evidence-based findings instead of manufacturing a
            # failed-write verdict. Never repeat an unsupported write claim.
            wrote = any(
                receipt.get("success") and receipt.get("mutates")
                for receipt in self.evidence.receipts()
            )
            if wrote:
                return (
                    "The rule review unexpectedly recorded a modifying action. "
                    "Its effects need independent Hubitat verification."
                )
            claimed_write = re.search(
                r"(?i)\b(?:i|we|homebrain|the agent)\s+"
                r"(?:(?:have|has)\s+)?"
                r"(?:created|modified|updated|paused|deleted|installed|"
                r"enabled|disabled|blocked|unblocked|queued)\b"
                r"|\b(?:new\s+rule\s+is\s+live|rule\s+created\s+successfully)\b",
                str(content or ""),
            )
            if claimed_write:
                return (
                    "Read-only review completed without a successful Hubitat "
                    "write receipt, but the generated answer made an "
                    "unverified action claim. Nothing was queued or created "
                    "in this review stage. Inspect the existing rule before "
                    "deciding whether changes are needed."
                )
            banner = (
                "**Read-only rule design review — no automation or device was "
                "changed or queued for approval.**\n\n"
                if is_new_rule_design_review_request(
                    self._current_user_objective.get()
                ) else
                "**Read-only existing-rule review — no automation or device "
                "was changed or queued for approval.**\n\n"
            )
            return banner + (
                str(content or "").strip()
                or "No verified rule findings were produced in this attempt."
            )
        mutation_expected = (
            self._mutation_requested_by_user.get()
            or self._mutation_call_seen.get()
        )
        if mutation_expected and not any(
            receipt.get("success") and receipt.get("mutates")
            for receipt in self.evidence.receipts()
        ):
            increment_active_metric("write_unverified_no_confirmation")
            return UNVERIFIED_MUTATION_REFUSAL
        return content

    async def _execute_focal_plan(
        self, plan: dict[str, Any], messages: list[dict[str, Any]],
        *, catalog: ToolDiscoveryCatalog | None = None,
    ) -> None:
        """Host read-only completion, independent of model planning rounds."""
        try:
            live_catalog = catalog or build_request_tool_catalog(
                await self.mcp.list_tools()
            )
            # Archive is a separate historical source. It must never be
            # conflated with a complete Hubitat native history, and socket
            # reception times do not constitute exact source timestamps.
            journal = getattr(self, "historical_journal", None)
            if (
                journal is not None
                and getattr(journal, "enabled", False)
                and getattr(journal, "_started", False)
                and plan.get("deviceId")
            ):
                try:
                    archive_window = plan.get("journalWindow") or plan["sourceWindow"]
                    archived = await asyncio.to_thread(
                        journal.query,
                        since=archive_window["since"],
                        until=archive_window["until"],
                        device_id=str(plan["deviceId"]), attribute="switch",
                        limit=100,
                    )
                    archive_details = project_archived_focal_state(archived, plan)
                    self.evidence.record(
                        "homebrain_evidence_journal",
                        {"device_id": str(plan["deviceId"]),
                         "since": archive_window["since"],
                         "until": archive_window["until"]},
                        success=True, elapsed_ms=0,
                        summary="Journal bounded state query: "
                                f"{archive_details['sourceTimestampedCount']} source-timestamped, "
                                f"{archive_details['collectorReceivedOnlyCount']} reception-only",
                        supports_live_claim=True,
                        evidence_kind="focal_archived_state_history",
                        mutates=False, effect="read",
                        details=archive_details,
                    )
                    increment_active_metric("skills_focal_journal_read")
                    if archive_details["sourceVerifiedOn"]:
                        increment_active_metric("skills_focal_journal_on_recovered")
                except (OSError, ValueError, TypeError, AttributeError):
                    self.evidence.record(
                        "homebrain_evidence_journal",
                        {"device_id": str(plan["deviceId"])},
                        success=False, elapsed_ms=0,
                        summary="Journal source query unavailable",
                        supports_live_claim=False,
                        evidence_kind="focal_archive_unavailable",
                        mutates=False, effect="read",
                    )
                    increment_active_metric("skills_focal_journal_failed")
            await execute_focal_source_plan(
                plan,
                catalog=live_catalog,
                executor=self.executor,
                recorder=self.evidence,
                messages=messages,
                count_metric=increment_active_metric,
            )
            # Do not terminate at a missing source-timestamped ON before
            # pursuing one grounded, accessible command-producer topology read.
            # The bounded next-read planner also queries historical app logs
            # only when that producer was explicitly capture-allowlisted.
            await execute_unverified_next_reads(
                plan,
                receipts=self.evidence.receipts(),
                catalog=live_catalog,
                mcp=getattr(self, "mcp", None),
                journal=journal,
                recorder=self.evidence,
                tool_succeeded=self._tool_succeeded,
                increment_metric=increment_active_metric,
            )
        except Exception:
            self.evidence.record(
                "hub_read_devices",
                {"tool": "hub_list_device_events",
                 "args": plan.get("stateRead") or {}},
                success=False, elapsed_ms=0,
                summary="Focal source catalog unavailable",
                supports_live_claim=False,
                evidence_kind="focal_source_catalog_unavailable",
                mutates=False, effect="read",
            )
            increment_active_metric("skills_focal_read_failed")

    async def _recover_journal_into_discovery(
        self, question: str, messages: list[dict[str, Any]],
    ) -> bool:
        """Read a bounded archive *before* the model selects its next evidence.

        The publication boundary still independently enforces factual source
        union. This cycle hook does not choose tools, add privileges, infer
        sensor IDs or promote collector reception to source time.
        Idempotence is enforced by recover_group_journal's existing receipts.
        """
        if (not is_history_investigation(question)
                or self._mutation_requested_by_user.get()
                or self._mutation_call_seen.get()):
            return False
        report = await recover_group_journal(
            journal=getattr(self, "historical_journal", None),
            recorder=self.evidence, question=question,
            receipts=self.evidence.receipts(),
        )
        if not report.get("attempted"):
            return False
        increment_active_metric("unified_group_journal_recovery")
        checkpoint = cross_source_discovery_checkpoint(
            self.evidence.receipts(), question)
        if checkpoint is None:
            return False
        messages.append({"role": "user", "content": checkpoint})
        increment_active_metric("causal_journal_discovery_checkpoint")
        return True

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        # Complete mandatory read-only source classes BEFORE the final model
        # synthesis. Post-answer coverage warnings alone cannot investigate.
        objective = self._current_user_objective.get() or _original_user_request(messages)
        # Guarantee a request-scoped incident read before deciding causation.
        # Latest-N event pages may have silently evicted an intervening OFF
        # even while an older ON boundary remains in interval history.
        focal_plan = build_focal_source_plan(self.evidence.receipts(), objective)
        baseline_snapshot = self._investigation_baseline.get()
        source_limited_baseline: str | None = (
            baseline_snapshot[0]
            if self._investigation_reflection_used.get() and baseline_snapshot
            else None
        )
        if focal_plan is not None:
            already_checked_focal = any(
                r.get("evidence_kind") in {
                    "focal_archived_state_history", "focal_exact_state_history"
                } and str((r.get("details") or {}).get("deviceId") or "")
                    == str(focal_plan.get("deviceId") or "")
                for r in self.evidence.receipts()
                if isinstance(r, dict) and r.get("success") is True
            )
            if not (self._investigation_reflection_used.get() and already_checked_focal):
                await self._execute_focal_plan(focal_plan, messages)
        # When exact-window recovery returned no uniquely observed ON, do
        # not enter a long model loop that treats the command as physical
        # causation or substitutes newer intervals for the dated event.
        if focal_plan is not None and focal_plan.get("requestedMinuteOnly"):
            missing_focal_answer = render_unverified_focal_outcome(
                focal_plan, self.evidence.receipts(), objective,
            )
            if missing_focal_answer:
                if not self._investigation_reflection_used.get():
                    increment_active_metric("skills_focal_unverified_stop")
                    return missing_focal_answer
                # Synthesis may compare newly discovered, permitted evidence,
                # but it may NOT erase the trusted historical source limit.
                source_limited_baseline = missing_focal_answer
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST HISTORICAL VERIFICATION BOUNDARY (authoritative "
                        "current-request evidence, not a new user request):\n"
                        + missing_focal_answer[:4800]
                        + "\nExplain any new evidence from the investigative "
                          "tool round, with competing hypotheses, while "
                          "preserving that the exact historical ON and "
                          "physical initiator remain unverified."
                    ),
                })
        device_log_args = pending_device_log_read(
            objective, self.evidence.receipts(),
        )
        if device_log_args is not None:
            try:
                live_catalog = build_request_tool_catalog(await self.mcp.list_tools())
                log_tool = live_catalog.declared_tool("hub_read_diagnostics")
                if log_tool is not None:
                    execution = await self.executor.execute(
                        "hub_read_diagnostics",
                        {"tool": "hub_get_logs", "args": device_log_args},
                        tool=log_tool,
                        supports_live_claim=True,
                        evidence_kind="native_device_scoped_logs",
                    )
                    messages.append({
                        "role": "tool", "tool_name": "hub_read_diagnostics",
                        "content": execution.content,
                    })
                    increment_active_metric("skills_required_source_read")
            except Exception as exc:
                # A failed or unavailable source must never masquerade as a
                # checked-empty device history or abort the investigation.
                logger.debug("Required scoped device log read unavailable: %s", exc)
        # Mandatory historical command provenance is a distinct event stream
        # from switch states and app logs. Complete one targeted, verified,
        # read-only command history check before final synthesis when the
        # objective explicitly demands it. This reuses the existing device
        # history source implementation; it is not a new model/tool privilege.
        command_plan = (
            (
                pending_historical_command_read(
                    objective, self.evidence.receipts(),
                )
                or pending_scoped_explanation_command_read(
                    objective, self.evidence.receipts(),
                )
            )
            if not _explicit_mutation_request(objective) else None
        )
        if command_plan is not None:
            try:
                live_catalog = build_request_tool_catalog(
                    await self.mcp.list_tools()
                )
                if live_catalog.available_tool("hub_read_devices") is not None:
                    old_receipt_count = len(self.evidence.receipts())
                    command_rows = await self.device_history._read_command_events(
                        device_id=command_plan["deviceId"],
                        label=command_plan["label"],
                        hours_back=command_plan["hoursBack"],
                        actions=(command_plan["action"],),
                    )
                    new_receipts = self.evidence.receipts()[old_receipt_count:]
                    attempted = any(
                        str(row.get("sub_tool") or "") == "hub_list_device_events"
                        and str((row.get("arguments") or {}).get("args", {}).get("attribute") or "")
                            == f"command-{command_plan['action']}"
                        for row in new_receipts if isinstance(row, dict)
                    )
                    if attempted:
                        increment_active_metric(
                            "historical_command_obligation_reads"
                        )
                    messages.append({
                        "role": "tool",
                        "tool_name": "hub_read_devices",
                        "content": redact_secrets(json.dumps({
                            "requiredHistoricalCommandRead": True,
                            "deviceId": command_plan["deviceId"],
                            "attribute": f"command-{command_plan['action']}",
                            "lookbackHours": command_plan["hoursBack"],
                            "sourceQuerySucceeded": any(
                                row.get("success") is True
                                for row in new_receipts
                                if isinstance(row, dict)
                            ),
                            "returnedCommandEvents": command_rows[:12],
                            "note": (
                                "State event producers and triggered listeners "
                                "are not command issuers or physical ACK proof. "
                                "Empty command-history results, even after a "
                                "successful query, do not prove no historic "
                                "command executed; retention may be incomplete."
                            ),
                        }, default=str, ensure_ascii=False)[:6800]),
                    })
                else:
                    increment_active_metric(
                        "historical_command_obligation_unavailable"
                    )
            except Exception as exc:
                increment_active_metric(
                    "historical_command_obligation_unavailable"
                )
                logger.debug(
                    "Required historical command read unavailable: %s", exc
                )
        # Source-directed historical evidence obligation. Only an actual,
        # successful, target-scoped command-on/off event with a verified app
        # producer and matching device identity can authorize this log read.
        # Prefer the diagnostic log gateway to guessing appId parameters on
        # hub_list_device_events; execute at most once per incident/app/window.
        source_log_plan = (
            pending_provenance_app_log_read(
                objective, self.evidence.receipts(),
            )
            if not _explicit_mutation_request(objective) else None
        )
        if source_log_plan is not None:
            try:
                log_catalog = build_request_tool_catalog(
                    await self.mcp.list_tools()
                )
                log_tool = log_catalog.available_tool("hub_read_diagnostics")
                log_args = {
                    "tool": source_log_plan["tool"],
                    "args": source_log_plan["args"],
                }
                if (
                    log_tool is not None
                    and log_catalog.gateway_operation_error(
                        "hub_read_diagnostics", log_args,
                    ) is None
                    and not classify_tool_effect(log_tool, log_args).mutates
                ):
                    result = await self.executor.execute(
                        "hub_read_diagnostics", log_args, tool=log_tool,
                        supports_live_claim=True,
                        evidence_kind="authoritative_native_app_logs",
                    )
                    messages.append({
                        "role": "tool", "tool_name": "hub_read_diagnostics",
                        "content": result.content,
                    })
                    increment_active_metric(
                        "historical_provenance_app_log_reads"
                    )
                    # A queried log source is not proof of a causal trigger;
                    # report failures/empty rows without inventing absence.
                    if not result.success:
                        increment_active_metric(
                            "historical_provenance_app_log_failures"
                        )
                else:
                    increment_active_metric(
                        "historical_provenance_app_log_unavailable"
                    )
            except Exception as exc:
                increment_active_metric(
                    "historical_provenance_app_log_unavailable"
                )
                logger.debug(
                    "Verified producer's app-log source unavailable: %s", exc,
                )
        content = await self.final_answers.answer(messages)
        # Terminal safety net. Earlier synthesis may skip causal validation if
        # a classifier or repair path fails; never send an unverified external
        # attribution when the exact event has a preceding internal command.
        content, corrected = guard_causal_exclusion_with_command_clue(
            content, self.evidence.receipts(), self._current_user_objective.get() or _original_user_request(messages),
        )
        if corrected:
            increment_active_metric("causal_final_output_reconciled")
        if source_limited_baseline is not None:
            # Never discard stronger, already verified receipt-derived facts
            # when a model's optional follow-up cannot retrieve more history.
            # A new synthesis is supplementary, not a replacement for the
            # trusted historical baseline.
            new_evidence = (
                baseline_snapshot is not None
                and any(
                    isinstance(row, dict)
                    and row.get("success") is True
                    and row.get("evidence_kind") not in {
                        "focal_archived_state_history",
                        "focal_exact_state_history",
                    }
                    for row in self.evidence.receipts()[baseline_snapshot[1]:]
                )
            )
            content = (
                source_limited_baseline + "\n\n**Additional investigation:** " + content
                if new_evidence and content.strip() else source_limited_baseline
            )
            content += (
                "\n\n**Historical verification boundary:** HomeBrain has "
                "archived collector-received state reports, but no "
                "independently verified source-timestamped switch ON in the "
                "requested minute. Neither current configuration nor a prior "
                "command proves the physical initiator."
            )
            increment_active_metric("investigation_reflection_synthesized")
        return redact_secrets(self._unverified_mutation_guard(content))

    def _take_confirmation(self, session_id: str, prompt: str) -> PendingConfirmation | None:
        return self.confirmations.consume(session_id, prompt)

    @staticmethod
    def _rule_result_data(execution: Any) -> dict[str, Any]:
        return ConfirmedActionCoordinator.rule_result_data(execution)

    @classmethod
    def _verified_rule_execution(cls, execution: Any) -> bool:
        return ConfirmedActionCoordinator.verified_rule_execution(execution)

    @staticmethod
    def _queued_rule_name(arguments: dict[str, Any]) -> str:
        return ConfirmedActionCoordinator.queued_rule_name(arguments)

    def _confirmed_rule_report(
        self,
        outcomes: list[tuple[str, dict[str, Any], Any]],
        *,
        queued_count: int,
    ) -> str | None:
        return ConfirmedActionCoordinator.confirmed_rule_report(
            outcomes,
            queued_count=queued_count,
        )

    async def _resume_confirmation(self, pending: PendingConfirmation, catalog: ToolDiscoveryCatalog) -> str:
        return await self.confirmed_actions.resume(pending, catalog)

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> AgentOutcome:
        paid_request_token = set_original_paid_request(user_prompt)
        if explicit_paid_request():
            increment_active_metric("paid_model_requested")
        evidence_token = self.evidence.begin()
        source_cache_token = self._groovy_mcp_cache.set(
            RequestScopedGroovyMcp(self.mcp)
        )
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(False)
        review_token = self._review_first_mode.set(
            RuleAuthoringService.is_existing_rule_review_first(user_prompt)
            or RuleAuthoringService.is_read_only_rule_design_request(user_prompt)
        )
        # The user requested creation ONLY AFTER verifying an existing rule.
        # This invocation performs stage-one review with read-only authority;
        # a later write still needs a fresh structured proposal and approval.
        mutation_request_token = self._mutation_requested_by_user.set(
            _explicit_mutation_request(user_prompt)
            and not self._review_first_mode.get()
        )
        class_token = self._request_class.set("tool-driven")
        objective_token = self._current_user_objective.set(str(user_prompt))
        reflection_token = self._investigation_reflection_used.set(False)
        baseline_token = self._investigation_baseline.set(None)
        hypothesis_token = self._investigation_hypotheses.set(())
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            # Redact deterministic shortcut output only when it contains
            # credential-shaped keys; leave ordinary status snapshots untouched.
            if any(term in str(message).casefold() for term in (
                "password", "passphrase", "secret", "access_token",
                "refresh_token", "api_key", "authorization:", "bearer ",
            )):
                message = redact_secrets(message)
            evidence = self.evidence.receipts()
            # Defence in depth against every early return: a verified
            # inventory/identity lookup still cannot answer a cause question.
            if (not self._mutation_requested_by_user.get()
                    and investigating(user_prompt)
                    and inventory_answer(message)):
                increment_active_metric("investigation_unfulfilled_at_boundary")
                message = honest_partial_answer(user_prompt, evidence)
            # Historical Journal is a separate, weaker and optional source.
            # This one bounded read-only opportunity applies to original
            # multi-device history requests even if the model ended early.
            # It never turns collector-reception timestamps into original
            # event times, grants no new target IDs or write permission.
            if (not self._mutation_requested_by_user.get()
                    and not self._mutation_call_seen.get()
                    and is_history_investigation(user_prompt)):
                journal_recovery = await recover_group_journal(
                    journal=getattr(self, "historical_journal", None),
                    recorder=self.evidence, question=user_prompt,
                    receipts=evidence,
                )
                if journal_recovery["attempted"]:
                    increment_active_metric("unified_group_journal_recovery")
                    evidence = self.evidence.receipts()
                app_decisions = await recover_group_app_decisions(
                    journal=getattr(self, "historical_journal", None),
                    recorder=self.evidence, question=user_prompt,
                    receipts=evidence,
                )
                if app_decisions["app_queries"]:
                    increment_active_metric("unified_group_app_log_checks")
                    evidence = self.evidence.receipts()
                boundary = await recover_recent_edge(
                    journal=getattr(self, "historical_journal", None),
                    recorder=self.evidence, receipts=evidence, question=user_prompt,
                )
                if boundary["attempted"]:
                    increment_active_metric("unified_recent_edge_checked")
                    evidence = self.evidence.receipts()
            # Enforce multi-device source coverage after every original
            # HomeBrain answer path, including early no-tools model exits.
            # The model still owns interpretation; the host checks that all
            # independently returned target switch transitions are reported.
            if (not self._mutation_requested_by_user.get()
                    and not self._mutation_call_seen.get()
                    and is_history_investigation(user_prompt)):
                # This boundary is evidence-triggered, not dependent on the
                # narrower routing-only investigating() predicate. A model-led
                # request classified as general history must still retain
                # every attested source event after an early answer exit.
                message, corrected_group = reconcile_unified_investigation_answer(
                    message, evidence, user_prompt)
                if corrected_group:
                    increment_active_metric("unified_group_timeline_reconciled")
                edge_answer = render_recent_edge(evidence, user_prompt)
                if edge_answer is not None:
                    message = edge_answer
                    increment_active_metric("unified_recent_edge_reconciled")
            # The previous phase may append or replace model text with a
            # source-derived group timeline. Reapply the SAME typed proof
            # contract to the completed answer, including specialized early
            # exits, rather than trusting a previous model-only validation.
            if (not self._mutation_requested_by_user.get()
                    and not self._mutation_call_seen.get()
                    and is_causal_investigation(user_prompt)):
                message, claim_calibrated = guard_unverified_initiator_claims(
                    message, evidence, user_prompt)
                if claim_calibrated:
                    increment_active_metric("evidence_claim_calibrations")
            # This boundary covers every model/fallback path, including a
            # no-more-tool round. Never present an unscoped hub-wide query as
            # proof that named targets had no historic activity.
            if (not self._mutation_requested_by_user.get()
                    and not self._mutation_call_seen.get()):
                message, invalid_absence = guard_unscoped_target_history_denial(
                    message, user_prompt, evidence)
                if invalid_absence:
                    increment_active_metric("unscoped_history_claim_rejected")
            if is_new_rule_design_review_request(user_prompt):
                message = calibrate_rule_design_review(
                    message, evidence, request=user_prompt,
                )
            if (
                self._mutation_requested_by_user.get()
                or self._mutation_call_seen.get()
            ):
                request_class = "write"
            elif (self._is_conversational_prompt(user_prompt)
                  or eligible_tool_free_knowledge(user_prompt)) and not evidence:
                request_class = "conversational"
            else:
                request_class = "live-read"
            pending = self.confirmations.pending.get(str(session_id))
            contract = (
                None if resolve_primary_objective(user_prompt).is_source
                else plan_investigation(user_prompt)
            )
            coverage = (
                assess_investigation(contract, evidence)
                if contract is not None and request_class == "live-read"
                else None
            )
            if (request_class == "live-read" and contract is not None
                    and contract.domain == "existing_rule_verification"):
                message = calibrate_existing_rule_verification(
                    message, evidence, coverage, request=user_prompt,
                )
            if request_class == "live-read":
                target_scope = inspect_target_history_scope(user_prompt, evidence)
                if target_scope and target_scope["missing_target_read_ids"]:
                    coverage = {
                        **(coverage or {}),
                        "targetHistoryScope": target_scope,
                        "sourceScopeComplete": False,
                        "questionResolved": False,
                    }
            candidates = self._investigation_hypotheses.get()
            if candidates and request_class == "live-read":
                checkpoint = build_evidence_checkpoint(
                    user_prompt, evidence, candidate_hypotheses=candidates,
                )
                comparisons = checkpoint["competing_hypothesis_checks"]
                if comparisons:
                    coverage = {
                        **(coverage or {}),
                        "hypothesisComparisons": comparisons,
                        "hypothesisComparisonStatus": (
                            "model-proposed-source-checks-not-causal-verdicts"
                        ),
                    }
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=evidence,
                choices=list(self._choices.get() or []),
                confirmation_required=pending is not None,
                confirmation_count=len(pending.actions) if pending is not None else 0,
                investigation_coverage=coverage,
            )
        finally:
            self._investigation_hypotheses.reset(hypothesis_token)
            self._investigation_baseline.reset(baseline_token)
            self._investigation_reflection_used.reset(reflection_token)
            self._current_user_objective.reset(objective_token)
            self._request_class.reset(class_token)
            self._mutation_requested_by_user.reset(mutation_request_token)
            self._mutation_call_seen.reset(mutation_token)
            self._review_first_mode.reset(review_token)
            self.evidence.reset(evidence_token)
            self._groovy_mcp_cache.reset(source_cache_token)
            self._choices.reset(choices_token)
            reset_original_paid_request(paid_request_token)

    async def process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        return (
            await self.process_user_request_result(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        ).message

    def _render_boundary_with_secondary(
        self,
        transition: str,
    ) -> str | None:
        evidence = self.evidence.receipts()
        base = render_boundary_producer_summary(
            evidence,
            transition=transition,
        )
        competing = render_competing_command_summary(
            evidence, transition=transition,
        )
        if base is None and competing is None:
            return None
        if competing:
            # A bridge-produced switch state can coexist with actual Hubitat
            # command calls from multiple apps. Never say "no direct command"
            # merely because no *unique* command producer can be selected.
            if base is not None:
                base_lines = base.splitlines()
                base = "\n".join([competing, *base_lines[1:]])
            else:
                base = competing
        secondary = render_reporting_source_secondary_summary_evidence(evidence)
        if not secondary:
            return base
        return base + "\n" + secondary

    async def _read_groovy_source(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Read-only evidence tool selected by the model; no host finalizer."""
        app_id = str(arguments.get("appId") or "").strip()
        if not re.fullmatch(r"[0-9]{2,7}", app_id):
            data = {"success": False, "sourceRetrieved": False,
                    "error": "appId must be a numeric installed application ID"}
        else:
            raw_symbols = arguments.get("symbols")
            symbols = raw_symbols if isinstance(raw_symbols, list) else None
            source_proxy = getattr(self, "_groovy_mcp_cache", None)
            request_cached_mcp = (
                source_proxy.get() if source_proxy is not None else None
            )
            if request_cached_mcp is None:
                request_cached_mcp = RequestScopedGroovyMcp(self.mcp)
            before_reuse = request_cached_mcp.reused_count
            report = await GroovySourceService(
                request_cached_mcp, self.evidence
            ).inspect(app_id, symbols=symbols)
            if request_cached_mcp.reused_count > before_reuse:
                increment_active_metric(
                    "groovy_source_reads_reused",
                    request_cached_mcp.reused_count - before_reuse,
                )
            data = {"success": True, "sourceRetrieved": report.retrieved,
                    "fullImplementationVerified": report.complete,
                    "verifiedCharacters": report.verified_characters,
                    "declaredTotalCharacters": report.declared_total,
                    "verifiedPages": report.verified_pages,
                    "sourceCodeId": report.source_code_id,
                    "verifiedCandidateMethodBodies": list(
                        report.verified_candidate_method_bodies
                    ),
                    "report": report.message,
                    "coverage": "partial-or-unverified" if not report.retrieved
                                else "excerpts-returned; verify full-source claim"}
        return MCPToolResult(
            name=_LOCAL_GROOVY_SOURCE_TOOL, arguments=dict(arguments),
            raw={}, text=json.dumps(data, ensure_ascii=False), data=data,
            is_error=False,
        )

    async def _process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        request_started = time.monotonic()
        # Stateful automation requests require live Rule Machine capability
        # discovery, not unconditional refusal or a speculative direct write.
        # Some legacy tool-free tests instantiate the agent with __new__
        # and deliberately bypass normal service/ContextVar initialization.
        review_context = getattr(self, "_review_first_mode", None)
        review_first = bool(review_context.get()) if review_context is not None else False
        # Primary objective wins over overlapping app/rule keywords.
        # "Inspect Groovy source for app 3977 and compare logs" is *not*
        # a Rule Machine action-tree audit, even when "compare" and
        # "configuration" appear in the same request.
        primary_objective = resolve_primary_objective(user_prompt)
        interpreted = active_request_interpretation(user_prompt)
        interpreted_kind = interpreted.objective if interpreted else None
        groovy_source_app = primary_objective.installed_app_id
        source_investigation = primary_objective.is_source
        # Interpreted read intent takes precedence over overlapping
        # diagnostic/app/rule words. On requests not arbitrated by the model,
        # retain the established specialist/factual fallback behavior.
        proposal_only = (
            not source_investigation
            and (
                interpreted_kind == "rule_design_review"
                if interpreted_kind is not None
                else is_new_rule_design_review_request(user_prompt)
            )
        )
        existing_rule_verification = (
            not source_investigation
            and (
                interpreted_kind == "existing_rule_verification"
                if interpreted_kind is not None
                else is_existing_rule_verification_request(user_prompt)
            )
        )
        deep_rule_review = (
            not source_investigation
            and not _explicit_mutation_request(user_prompt)
            and (
                interpreted_kind == "existing_rule_verification"
                if interpreted_kind is not None
                else requires_rule_logic_inspection(user_prompt)
            )
        )
        stateful_authoring = (
            not review_first
            and RuleAuthoringService.is_stateful_authoring_request(user_prompt)
        )
        # Conversation references are answered from the supplied *same-session*
        # transcript, never via Hubitat inventory/tool discovery. Host-owned
        # exact recall uses zero model rounds; interpretation uses one provider
        # round with no MCP tools or write permissions.
        if conversation_reference_intent(user_prompt) and not _explicit_mutation_request(user_prompt):
            recalled, recall_messages = conversation_reference_answer(
                user_prompt, self._history(conversation_history),
            )
            increment_active_metric("conversation_recall_no_mcp")
            if recalled is not None:
                return recalled
            if recall_messages is not None:
                result = await self.transport.chat(recall_messages, [])
                value = str(result.get("content") or "").strip()
                if result.get("tool_calls") or not value:
                    return (
                        "I could not establish that from the available chat "
                        "history; no Hubitat tools were called."
                    )
                return value
        # Explicit tool-free *static* technical questions need no catalog,
        # Hubitat reads, source searches or multi-round tool selection.
        # The classifier rejects live state, device/app IDs and write intents.
        if eligible_tool_free_knowledge(user_prompt) and not _explicit_mutation_request(user_prompt):
            reply = await self.transport.chat(tool_free_messages(user_prompt), [])
            content = str(reply.get("content") or "").strip()
            if reply.get("tool_calls") or not content:
                return "The tool-free technical explanation did not complete; no Hubitat tools were called."
            return content
        # Keep the full live registry searchable; tool_limit bounds *declared*
        # model functions, not the server capabilities retained for discovery.
        # The initial model view remains small and permission-filtered by MCP.
        all_tools = await self.mcp.list_tools()
        catalog = build_request_tool_catalog(all_tools)
        # Inventory-only tools are useful for listing, but not as a model's
        # terminal answer to WHY/diagnostic objectives. This is enforced at
        # the tool catalog boundary, even after later discovery/expansion.
        diagnostic_objective = (
            investigating(user_prompt)
            and not self._mutation_requested_by_user.get()
        )
        if diagnostic_objective:
            catalog.hide_inventory_during_investigation()
        if deep_rule_review:
            # Expose available native rule/config/variables/health readers,
            # not device controls or management gateways. Read-only tool
            # review must be possible without fuzzy discovery guessing.
            catalog.activate_investigation_read_view(max_declared=self.tool_limit)
            catalog.replace_declared([
                *catalog.declared_names,
                "hub_read_rules",
                "hub_read_apps_code",
                "hub_get_tool_guide",
            ])
        if review_first:
            # No rule/device write gateway is visible, even if a fuzzy search
            # later discovers one. A conditional create is NOT authority to
            # bypass a requested review of an existing working automation.
            catalog.activate_investigation_read_view(max_declared=self.tool_limit)
        if stateful_authoring:
            if not self.rule_write_enabled:
                return RULE_WRITES_DISABLED_MESSAGE
            catalog.replace_declared([
                *catalog.declared_names,
                "hub_get_tool_guide",
                "hub_read_devices",
                "hub_read_rules",
                RULE_MACHINE_GATEWAY,
            ])
        # Request-local collector; never share source text between questions.
        source_chunks = SourceChunkCollector(user_prompt)
        adaptive_investigation = (
            (model_led_investigation_request(user_prompt)
             or is_connectivity_root_cause_request(user_prompt))
            and not _explicit_mutation_request(user_prompt)
        )
        if adaptive_investigation or deep_rule_review:
            # Restrict available model tools to actually registered READ
            # capabilities. A planner can choose the next evidence source,
            # never expand permissions or authorise a device mutation.
            catalog.activate_investigation_read_view(max_declared=self.tool_limit)
        if source_investigation:
            # Expose a safe evidence capability; the model decides whether
            # to call it and how to investigate. No deterministic final answer.
            catalog.replace_declared([
                *catalog.declared_names, _LOCAL_GROOVY_SOURCE_TOOL,
            ])
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            pending_names = list(dict.fromkeys(name for name, _ in pending.actions))
            missing = catalog.replace_declared(pending_names)
            if missing:
                return self.confirmation_policy.unavailable_tools_message(missing)
        if pending:
            return await self._resume_confirmation(pending, catalog)
        normalized_prompt = " ".join(str(user_prompt).strip().casefold().split())
        if normalized_prompt in CONFIRM_WORDS:
            return (
                "No Hubitat action is pending confirmation in this browser session. "
                "Nothing was executed. Submit the original request again and only "
                "confirm when the response carries a verified pending action."
            )
        # Current, named-app lockout configuration has an existing read-only
        # gateway. Call it deterministically instead of spending multiple model
        # rounds guessing a sub-operation as an undeclared top-level tool.
        current_lockout = await read_current_lockout_config(
            self, user_prompt, catalog=catalog,
        )
        if current_lockout is not None:
            return current_lockout

        # The legacy deterministic inventory shortcut may serve factual
        # list requests, never consume an AI-interpreted investigation.
        # A source/causal objective needs the model to select evidence that
        # answers WHY, not a list of devices in the same room.
        investigative_ai_objective = bool(
            interpreted_kind in {
                "general_investigation", "device_connectivity",
                "historical_command", "existing_rule_verification",
                "source_code",
            }
        )
        inventory_arguments = (
            None if (investigative_ai_objective or diagnostic_objective)
            else _device_inventory_arguments(user_prompt)
        )
        if inventory_arguments is not None:
            inventory_tool = catalog.available_tool(_LOCAL_DEVICE_INVENTORY_TOOL)
            if inventory_tool is not None:
                execution = await self.executor.execute(
                    _LOCAL_DEVICE_INVENTORY_TOOL,
                    inventory_arguments,
                    tool=inventory_tool,
                    supports_live_claim=False,
                    evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_INVENTORY_TOOL],
                )
                if execution.result is not None:
                    message = present_tool_result(
                        _LOCAL_DEVICE_INVENTORY_TOOL,
                        execution.result.data,
                        failed=not execution.success,
                        fallback_error=execution.result.text,
                    )
                    if message is not None:
                        return message

        # Honor a user's inert-from-birth requirement before any model
        # interpretation or native write. The current rule-creation contract
        # has no independently validated atomic disabled-at-create method;
        # creating active then disabling it violates the user's instruction.
        if (self._mutation_requested_by_user.get()
                and demands_atomic_disabled_rule_creation(user_prompt)):
            increment_active_metric("rule_create_staging_unverified")
            return render_atomic_staging_stop()

        # A supported native night-idle OFF has a deterministic action
        # compiler. Do not run the free model through repeated tool-discovery
        # rounds for this exact authoring grammar. The compiler only builds a
        # proposal, verifies exact devices/current rule names and documented
        # subtypes, then delegates to the existing confirmation gate. Writes
        # are never executed on this path without a new user confirmation.
        if (self._mutation_requested_by_user.get()
                and not review_first
                and recognise_night_idle_creation(user_prompt) is not None):
            if not self.rule_write_enabled:
                return RULE_WRITES_DISABLED_MESSAGE
            intent = await propose_night_idle(
                user_prompt,
                mcp=self.mcp,
                record_evidence=self.evidence.record,
                rules=self.rule_authoring,
                available_gateways=set(catalog.available_names),
            )
            if intent is not None and intent.handled:
                increment_active_metric("rule_night_idle_fastpath")
                return self._rule_proposal_confirmation.resolve(
                    intent, user_prompt=user_prompt, session_id=session_id,
                )

        # The user's explicit time-bound rule command is the authority for
        # authoring intent. Do NOT let the semantic planner's advisory
        # operation="propose" suppress this deterministic compiler: doing so
        # fell through to a model search for the fictional blockInternet
        # command and an unnecessary "what starts the countdown?" question.
        # Pure design questions must still remain read-only.
        if self.rule_authoring.is_action_request(user_prompt) and not review_first:
            if not self.rule_write_enabled:
                return RULE_WRITES_DISABLED_MESSAGE
            if RULE_MACHINE_GATEWAY not in catalog.available_names:
                increment_active_metric("rule_schedule_gateway_missing")
                return (
                    "I understand the scheduled device action, but the "
                    "Hubitat Rule Machine write gateway is unavailable. "
                    "No rule was queued or changed."
                )
            rule_decision = await self.rule_authoring.propose(
                user_prompt,
                available_gateways=set(catalog.available_names),
                can_read_rules=True,
            )
            if rule_decision.handled:
                increment_active_metric("rule_schedule_fastpath")
                return self._rule_proposal_confirmation.resolve(
                    rule_decision,
                    user_prompt=user_prompt,
                    session_id=session_id,
                )
            # An explicitly scheduled request must not degrade into a
            # speculative model-authored Rule Machine payload.
            return (
                "The scheduled action could not be safely compiled into a "
                "verified Hubitat Rule Machine proposal. Nothing was queued."
            )

        # A general task objective is advisory: it guides skill selection and
        # targeted discovery, never effect classification, user authorisation,
        # device identity, tool schema validation or claimed evidence.
        task_plan = (
            await self.general_task_planner.plan(
                user_prompt, history=self._history(conversation_history),
            )
            # Preserve already-corroborated causal/event fast paths without
            # an unnecessary extra planning LLM round. Their existing model
            # reflection handles genuinely unresolved or explicit deep goals.
            if (
                self.general_task_engine_enabled
                or (
                    adaptive_investigation
                    and (source_investigation or not is_causal_investigation(user_prompt))
                )
                or (
                    requests_explicit_hypothesis_comparison(user_prompt)
                    and not _explicit_mutation_request(user_prompt)
                )
            )
            and not self._is_conversational_prompt(user_prompt)
            and not stateful_authoring
            and not review_first
            else None
        )
        # An explicitly requested comparison can use the existing planner
        # even when bounded causal evidence reads remain authoritative.
        # Keep the tentative hypotheses request-scoped and never record them
        # as MCP evidence.
        # Advisory task planning cannot reduce a user-authorised
        # create-with-confirmation request to proposal-only. The actual tool
        # schema, safety requirements and confirmation policy still decide
        # whether any specific write can be queued.
        if (task_plan is not None
                and task_plan.operation == "propose"
                and self._mutation_requested_by_user.get()):
            increment_active_metric("planner_write_intent_corrected")
            task_plan = replace(task_plan, operation="write")
        if task_plan is not None and task_plan.operation == "investigate":
            self._investigation_hypotheses.set(task_plan.candidate_hypotheses)
        stateful_capability_instruction = ""
        if stateful_authoring:
            preflight = await inspect_stateful_rule_capabilities(
                self.mcp,
                self.evidence.record,
                catalog.available_names,
            )
            if not preflight.ready:
                return preflight.instruction
            stateful_capability_instruction = preflight.instruction

        capability_discovery = ""
        capability_additions: list[MCPTool] = []
        search_tool = catalog.declared_tool(SEARCH_TOOL)
        known_history_path = (not source_investigation and uses_known_history_evidence_path(user_prompt))
        if known_history_path:
            increment_active_metric("history_known_tool_fastpath")
        if (
            search_tool is not None
            and not self._is_conversational_prompt(user_prompt)
            and not known_history_path
        ):
            # Search a model-proposed capability rather than using the full
            # original question as a fuzzy tool query. Invalid/missing plans
            # retain the existing discovery behavior.
            discovery_query = (
                task_plan.capability_queries[0]
                if task_plan is not None and task_plan.capability_queries
                else str(user_prompt).strip()
            )
            discovery = await self.executor.execute(
                SEARCH_TOOL,
                {"query": discovery_query},
                tool=search_tool,
                supports_live_claim=False,
                record_evidence=False,
            )
            capability_additions = (
                catalog.expand(discovery.result, query=discovery_query)
                if discovery.result is not None
                else []
            )
            capability_discovery = discovery.content
            if adaptive_investigation or review_first or deep_rule_review:
                # Discovery must not grant the model a mutating gateway.
                catalog.activate_investigation_read_view(max_declared=self.tool_limit)
                if source_investigation:
                    catalog.replace_declared([
                        *catalog.declared_names, _LOCAL_GROOVY_SOURCE_TOOL,
                    ])
            if capability_additions:
                logger.info(
                    "Original-request discovery expanded registry with: %s",
                    ", ".join(item.name for item in capability_additions),
                )
        tools = catalog.schemas()
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(
            user_prompt,
            conversation_history,
            skill_domains=task_plan.skill_domains if task_plan is not None else None,
        )
        if proposal_only:
            system_prompt += (
                "\n\nHOST RULE DESIGN / REVIEW-ONLY BOUNDARY\n"
                "The user explicitly requested a proposed automation plan "
                "and withheld permission to create, modify, queue or execute "
                "any rule or device command. The current request is read-only, "
                "even if the user mentions a future desired creation. "
                "Use live source verification: resolve EACH explicitly named "
                "device ID to its actual current label, room and capabilities "
                "BEFORE describing the planned logic. Never silently substitute "
                "a different sensor when an ID is mismatched. Read the exact "
                "existing rule/app IDs mentioned by the user, plus any other "
                "relevant current controller configured for the same target; "
                "corroborate target refs with a device-dependents query when "
                "available. Prefer config/source read tools to unrelated "
                "history: historical events may prove command producers but "
                "not a rule's complete current trigger/action settings. "
                "Give a complete plan with triggers, modes, time boundaries, "
                "continuously inactive delay cancellation, light-on-while-"
                "already-inactive case, and competition with existing rules. "
                "Validate any proposed native Rule Machine operations against "
                "the actual tool guide; never assume unverified IF/WAIT/"
                "Required Expression support or fabricate write JSON. "
                "State gaps, contradictions and unknowns explicitly, and "
                "never ask for write confirmation in this turn. No Hubitat "
                "writes are authorised.\n"
            )
        elif existing_rule_verification:
            system_prompt += (
                "\n\nHOST EXISTING RULE VERIFICATION BOUNDARY (read-only)\n"
                "This task inspects installed Rule Machine apps, not a proposed "
                "new rule. Never produce a new-rule feasibility gate, a proposed "
                "writer schema, or a confirmation request. Resolve exact app IDs "
                "and exact-name duplicate matches from an appropriately complete "
                "inventory. Read targeted health and persisted configuration. "
                "Extract the actual ordered trigger/action and condition values; "
                "a receipt listing only response field names is not proof of "
                "those values. Reconcile competing controller summaries with "
                "the underlying settings before claiming an effective delay. "
                "Separate configuration verification from observed execution. "
                "Keep missing evidence unverified. No Hubitat writes are "
                "authorised by this investigation.\n"
            )
        elif review_first:
            system_prompt += (
                "\n\nHOST REVIEW-BEFORE-CREATE BOUNDARY (read-only stage)\n"
                "The user made creation CONDITIONAL on first verifying an "
                "existing automation. Do not create, update, pause, delete, "
                "enable or disable ANY rule or device in this request. "
                "First find the exact named installed Rule Machine instance; "
                "inspect its actual trigger and ordered IF/ELSE/action structure, "
                "hub/local variables, enabled/paused status and, when possible, "
                "rule health. Start with hub_read_rules and hub_read_apps_code; "
                "use hub_get_app_config page data and hub_get_rule_health, "
                "hub_list_rule_local_variables, or documented native exports "
                "ONLY when available in the installed read-only catalog. "
                "Page identity, variable existence and a rule name are NOT "
                "proof of the action list or actual 60-minute behaviour. "
                "If content is incomplete, state precisely what is missing "
                "rather than recommending a duplicate or claiming success. "
                "If the rule is already suitable, explain why a second rule "
                "should not be created; if defective, report the exact gaps "
                "and request separate approval before any modification. "
                "No live write is authorized in this stage."
            )
        # Tell the model the exact UTC equivalent of a user-supplied UK
        # historical event clock before it selects log/history tools. This
        # is calendar arithmetic, not proof that an event occurred.
        incident_window = history_window_instruction(user_prompt)
        if incident_window:
            system_prompt += "\n\n" + incident_window
        # Progressive on-demand skill loading (repo-owned instructions only).
        skill_guidance = render_skills_for_request(user_prompt)
        if skill_guidance:
            system_prompt += "\n\n" + skill_guidance
        if task_plan is not None:
            system_prompt += "\n\n" + task_plan.instruction()
        if adaptive_investigation:
            system_prompt += "\n\n" + READ_ONLY_AGENT_DIRECTIVE
            system_prompt += (
                "\n\nEVIDENCE CHAIN FOR THIS QUESTION (ADVISORY, READ-ONLY)\n"
                "Preserve the original requested ANSWER, not merely the type "
                "of entity you looked up. Verify relevant existing settings "
                "only as a supporting step when the goal is an explanation. "
                "For recurring behaviour, distinguish successful examples "
                "from episodes of failure; a normal cycle does not by itself "
                "explain an earlier abnormal cycle. Check source implementation "
                "for input roles, cancellation and timing when reachable; "
                "then compare target-linked device events, commands and app "
                "logs across the relevant windows. Never substitute source "
                "from a different app instance without a verified link. "
                "Stop when accessible evidence no longer discriminates the "
                "remaining explanations. Deliver the most supported answer "
                "with explicit confidence/limits, not a generic audit template."
            )
            if interpreted is not None and investigative_ai_objective:
                # The model has already interpreted the goal. Carry that
                # one decision forward through tool choice and final answer.
                # Its purpose is guidance, NEVER evidence or permission.
                system_prompt += (
                    "\n\nAI-INTERPRETED READ-ONLY TASK (ADVISORY)\n"
                    + "User's exact original question: " + user_prompt[:3000]
                    + "\nInterpretation: " + str(interpreted.objective)
                    + "\nTarget: " + str(interpreted.target or "from user question")
                    + "\nPurpose: " + str(interpreted.purpose or "answer the user's question")
                    + "\nA room/device inventory is background evidence, NOT "
                      "a final answer to a causal investigation. Investigate "
                      "the controlling automation, configured inputs, "
                      "observed events, and relevant implementation when "
                      "required. If not verified, say what remains unknown. "
                      "Do not claim a root cause from inventory alone. "
                      "Do not change any Hubitat devices or rules."
                )
            if is_connectivity_root_cause_request(user_prompt):
                system_prompt += "\n\n" + CONNECTIVITY_EVIDENCE_PLAN
        contract = None if source_investigation else plan_investigation(user_prompt)
        if contract is not None:
            system_prompt += (
                "\n\n" + render_investigation_plan(contract)
                + "\nPrioritise targeted historical evidence and test the "
                  "actual goal; current configuration or successful reads "
                  "alone cannot establish a past execution."
            )
        if source_investigation:
            system_prompt += (
                "\n\nINSTALLED GROOVY IMPLEMENTATION INVESTIGATION\n"
                "This is a source-code investigation, not a Rule Machine "
                "device-health report. You are responsible for the plan, "
                "selecting safe read tools, weighing alternatives and "
                "synthesizing an evidence-backed answer. Installed app ID "
                f"{groovy_source_app} is NOT necessarily the user-code ID. "
                "The homebrain_read_groovy_source tool's appId must be the "
                f"INSTALLED INSTANCE ID {groovy_source_app} from the user's "
                "request, not the distinct source/code ID obtained from "
                "appTypeId or a source result. Only hub_get_source uses the "
                "verified source code ID. Prefer homebrain_read_groovy_source "
                "first for a whole-source inspection. Supply the installed "
                "appId and an optional symbols list "
                "derived from the actual question. This workbench retrieves "
                "contiguous source and returns bounded code excerpts; use it "
                "as evidence while you lead the investigation. If unavailable, "
                "discover alternative read tools via hub_search_tools and "
                "hub_get_tool_guide. Do not make overlapping, repeated manual "
                "hub_get_source reads when one workbench call can cover the "
                "file. Check live tool schemas; never invent sub-operations. "
                "If a reader is missing, consider another read-only route "
                "that the live MCP catalog positively advertises. "
                "Do not inspect unrelated sensors unless the question "
                "explicitly involves them. Never infer Groovy source behavior "
                "from configuration alone. A claim of full-source coverage "
                "requires verified chunk completeness. Report missing "
                "evidence plainly. Never write to Hubitat."
            )
        if deep_rule_review:
            system_prompt += (
                "\n\nHOST DETAILED RULE MACHINE LOGIC REVIEW (READ-ONLY)\n"
                "Inspect the exact installed Rule Machine app ID in the "
                "request. Read actual triggers, ordered conditional actions, "
                "variable definitions/current values and paused/enabled "
                "state via installed Hubitat MCP read tools. Prefer "
                "hub_get_rule_health, hub_list_rule_local_variables, "
                "hub_get_app_config, hub_get_visual_rule and any native rule "
                "export only if the installed guide confirms that it is a "
                "read operation. Never infer condition branches merely from "
                "a successful app configuration identity fetch. "
                "Distinguish verified configuration, actual execution "
                "history and unverified runtime behaviour. If an ordered "
                "action tree cannot be obtained, say so specifically. "
                "A separate reset rule cannot be assumed to modify a "
                "different rule's LOCAL variable just because its name "
                "matches; verify whether the counter is a shared Hub "
                "Variable or a genuinely cross-rule supported reference. "
                "Do not call an initialized-only log proof of minute-by-minute "
                "execution. Do not say the investigation is complete when "
                "execution or variable scope remains unverified. "
                "No changes or confirmations are authorized."
            )
        if (self._mutation_requested_by_user.get()
                and re.search(r"(?i)\\b(?:rule machine|automation|rule)\\b", user_prompt)
                and not proposal_only):
            system_prompt += (
                "\n\nNATIVE RULE MACHINE AUTHORING CONSTRAINTS (HOST VERIFIED)\n"
                "For hub_manage_rule_machine tool=hub_set_rule, put name, "
                "addTriggers and addActions directly under args. Each action "
                "is a FLAT object with an explicit capability, e.g. "
                "{'capability':'ifThen','expression':{'conditions':[...],"
                "'operator':'AND'}}, {'capability':'delay','minutes':10,"
                "'cancelable':true}, {'capability':'cancelDelay'}, "
                "{'capability':'endIf'}, {'capability':'switch','action':'off',"
                "'deviceIds':[lightId]}. Never invent wrapper forms like "
                "{'ifThen':{...}}, {'delay':{...}}, {'cancelDelay':{}}. "
                "Certain Time (and optional date) is a TRIGGER, not a "
                "condition inside IF; use a Between two times condition "
                "with clock start/end objects. When 23:00 and 06:00 BOTH "
                "trigger the rule, every trigger runs the same action list: "
                "cancellation must occur first, and switch-off must be "
                "inside a second final IF guard AFTER a cancelable delay. "
                "Do not submit an incomplete substitute, bypass existing "
                "rule conflict inspection, or claim Hubitat execution from "
                "a validated JSON proposal. The host will reject malformed "
                "and semantically unguarded action plans before confirmation.\n"
            )
        if stateful_capability_instruction:
            system_prompt += "\n\n" + stateful_capability_instruction
        if capability_discovery:
            system_prompt += (
                "\n\nHOST ORIGINAL-REQUEST CAPABILITY DISCOVERY\n"
                + capability_discovery
                + "\nRelevant returned gateways are already declared. Complete the "
                "user's requested operation; do not replace a create/edit request "
                "with a report that the target does not yet exist."
            )
        if _matches(user_prompt, {"weather"}):
            weather_started = time.monotonic()
            weather_result = await self._weather_snapshot({})
            self.evidence.record(
                _LOCAL_WEATHER_TOOL,
                {},
                success=self._tool_succeeded(weather_result),
                elapsed_ms=round((time.monotonic() - weather_started) * 1000),
                summary=self._result_summary(weather_result),
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_WEATHER_TOOL],
            )
            if self._tool_succeeded(weather_result):
                system_prompt += (
                    "\n\nAUTHORITATIVE CURRENT WEATHER SNAPSHOT\n"
                    + self._result_payload(weather_result)
                    + "\nAnswer weather questions only from this snapshot."
                )
        logger.info(
            "System prompt built in %.3fs (%d chars, manifest=%s)",
            time.monotonic() - prompt_started,
            len(system_prompt),
            self._include_identity_manifest(user_prompt),
        )
        if ((interpreted_kind is None or
             interpreted_kind == "existing_rule_verification")
                and is_automation_runtime_diagnostic(user_prompt)):
            system_prompt += AUTOMATION_DIAGNOSTIC_INSTRUCTION
        if is_motion_lockout_investigation(user_prompt):
            system_prompt += (
                "\n\nHISTORICAL MOTION LOCKOUT INVESTIGATION\n"
                "Do not substitute current configuration or sensor health for "
                "the requested past manual-OFF sequence. Match an actual OFF "
                "with controller/button observations and later motion plus "
                "subsequent light states; inspect allowlisted historical app "
                "logs and journal before evaluating any lockout. Configuration "
                "alone cannot prove lockout activation, and the absence of an "
                "ON event cannot prove successful inhibition. Never claim a "
                "manual OFF without independent controller evidence."
            )
        if ((interpreted_kind is None or
             interpreted_kind == "general_investigation")
                and is_integration_runtime_diagnostic(user_prompt)):
            system_prompt += INTEGRATION_DIAGNOSTIC_INSTRUCTION
        messages = [
            {"role": "system", "content": system_prompt},
            *self._history(conversation_history),
            {"role": "user", "content": str(user_prompt).strip()},
        ]
        if deep_rule_review or existing_rule_verification:
            # Explicit coordinated native rules ("apps 4239 and 4241")
            # must BOTH receive read-only health and variable evidence.
            # A device ID referenced later in the prompt is not an app ID.
            for app_id in named_rule_app_ids(user_prompt, max_items=3):
                await prefetch_native_rule_evidence(
                    self.mcp, self.evidence,
                    app_id=app_id,
                    available_names=catalog.available_names,
                    messages=messages,
                )
                if existing_rule_verification:
                    await prefetch_installed_app_settings(
                        self.mcp, self.evidence,
                        app_id=app_id,
                        available_names=catalog.available_names,
                        messages=messages,
                    )
        completed_calls: set[str] = set()
        grounding = GroundingPolicy(
            logs_requested=_matches(user_prompt, _LOG_TERMS),
            conversational=self._is_conversational_prompt(user_prompt),
        )
        capability_grounding = CapabilityGroundingPolicy()
        device_claim_grounding = DeviceClaimGroundingPolicy()
        post_filter_discovery_used = False
        # A proposed rule may mention the manual-off lockout as a safety
        # constraint. That is not a request to replace the rule-design review
        # with a bounded historical lockout investigation.
        lockout_intent = (
            not source_investigation and not proposal_only
            and (interpreted_kind is None
                 or interpreted_kind == "historical_command")
            and is_motion_lockout_investigation(user_prompt)
        )
        lockout_prefetch = (
            await prefetch_motion_lockout(
                self, user_prompt, catalog=catalog, messages=messages
            )
            if lockout_intent else False
        )
        # A missing-telemetry/root-cause question is NOT an observed
        # ON/OFF transition for the historical command-provenance engine.
        # That engine otherwise expands unrelated room/location history and
        # ends after a constrained command-source round, before source logic.
        connectivity_incident = (
            is_connectivity_root_cause_request(user_prompt)
            and not self._mutation_requested_by_user.get()
        )
        causal_request = (
            not connectivity_incident and not source_investigation
            and (interpreted_kind is None
                 or interpreted_kind == "historical_command")
            and is_causal_investigation(user_prompt)
        )
        investigative_request = (
            source_investigation
            or (interpreted_kind is not None and interpreted_kind not in (
                "system_audit", "performance_report",
            ))
            or connectivity_incident
            or (
                interpreted_kind is None
                and (
                    is_history_investigation(user_prompt)
                    or is_automation_runtime_diagnostic(user_prompt)
                    or is_integration_runtime_diagnostic(user_prompt)
                )
            )
            or lockout_intent
            or contract is not None
        )
        set_reasoning_profile(
            "deep" if investigative_request and wants_deep_investigation(user_prompt)
            else "investigative" if investigative_request else "standard"
        )
        investigative_subject_history_key: str | None = None
        causal_subject_evidence_expanded = False
        causal_subject_no_intervals = False
        ungrounded_confirmation_claim_seen = False
        last_proposal_error: tuple[str, dict[str, Any], str] | None = None
        proposal_error_retries = 0
        causal_completion_retry_used = False
        causal_completion_mode = False

        deep_causal_request = causal_request and wants_deep_investigation(user_prompt)
        causal_prefetch = "not_applicable"
        prefetched_subject_key: str | None = None
        prefetched_transition: str | None = None
        if causal_request and not lockout_prefetch:
            causal_prefetch, prefetched_subject_key, prefetched_transition = (
                await self._prefetch_explicit_causal_subject(
                    user_prompt,
                    catalog=catalog,
                    completed_calls=completed_calls,
                    messages=messages,
                )
            )
            # A specifically dated causal ON is always an evidence-first
            # request, regardless of whether the user says "deep". Run the
            # host's bounded state and producer-log reads before provider
            # exploration and before deterministic early exits. Only a
            # verified unique native ON may establish the focal transition.
            if (
                prefetched_subject_key
                and has_explicit_focal_clock(user_prompt)
                and switch_transition_from_prompt(user_prompt) == "on"
            ):
                early_focal_plan = build_focal_source_plan(
                    self.evidence.receipts(), user_prompt,
                )
                if (
                    early_focal_plan is not None
                    and early_focal_plan.get("requestedMinuteOnly")
                ):
                    await self._execute_focal_plan(
                        early_focal_plan, messages, catalog=catalog,
                    )
                    early_outcome = render_unverified_focal_outcome(
                        early_focal_plan,
                        self.evidence.receipts(),
                        user_prompt,
                    )
                    if early_outcome:
                        if (
                            is_investigative_question(user_prompt)
                            and not self._mutation_requested_by_user.get()
                        ):
                            # A partial result must not preempt the existing
                            # model-led, bounded evidence selection loop.
                            # Replace the model-facing registry with installed,
                            # safely classified READ tools only.
                            read_tools = catalog.activate_investigation_read_view(
                                max_declared=self.tool_limit
                            )
                            messages.append({
                                "role": "user",
                                "content": (
                                    "HOST VERIFIED PARTIAL ANSWER (do not overwrite "
                                    "source-clock and causation boundaries):\n"
                                    + early_outcome[:4200] + "\n\n"
                                    + render_investigation_checkpoint(
                                        user_prompt, self.evidence.receipts(),
                                        available_read_tools=read_tools,
                                        candidate_hypotheses=(
                                            task_plan.candidate_hypotheses
                                            if task_plan is not None
                                            and task_plan.operation == "investigate"
                                            else ()
                                        ),
                                    )
                                ),
                            })
                            tools = catalog.schemas()
                            self._investigation_baseline.set(
                                (early_outcome, len(self.evidence.receipts()))
                            )
                            self._investigation_reflection_used.set(True)
                            increment_active_metric("investigation_read_reflection")
                        else:
                            increment_active_metric("skills_focal_unverified_stop")
                            increment_active_metric("skills_early_focal_stop")
                            increment_active_metric("investigative_finalization")
                            return early_outcome

            if prefetched_subject_key:
                investigative_subject_history_key = prefetched_subject_key
                topology_brief = render_topology_plan(
                    self.evidence.receipts(), user_prompt,
                )
                if topology_brief:
                    messages.append({"role": "user", "content": topology_brief})
                    increment_active_metric("skills_topology_plan")
            if causal_prefetch == "sufficient":
                deterministic_answer = (
                    (
                        render_command_producer_summary(
                            self.evidence.receipts(),
                            transition=prefetched_transition or "on",
                        )
                        or self._render_boundary_with_secondary(
                            prefetched_transition or "on"
                        )
                        or render_strong_native_provenance_answer(
                            self.evidence.receipts()
                        )
                    )
                    if self.causal_deterministic_final_enabled
                    else None
                )
                if deterministic_answer:
                    deterministic_answer = await self._lighting_rule_decision_followup(
                        deterministic_answer,
                        transition=prefetched_transition or "on",
                    )
                    if not deep_causal_request and not self._investigation_reflection_used.get():
                        increment_active_metric(
                            "causal_deterministic_finalization"
                        )
                        increment_active_metric("investigative_finalization")
                        return deterministic_answer

                    # A normalized request-scoped causal graph knows what the
                    # host has *already* checked, and what remains a hypothesis.
                    # When a user explicitly requests alternatives involving
                    # mode-dependent app logic, one focused location-event read
                    # is cheaper and more reliable than a model-discovery round.
                    graph = build_causal_evidence_graph(
                        self.evidence.receipts(), user_prompt
                    )
                    if (
                        needs_mode_history(graph, user_prompt)
                        and catalog.available_tool("hub_read_devices") is not None
                    ):
                        args = {"hoursBack": 24, "limit": 20}
                        request = {
                            "tool": "hub_list_device_events", "args": args
                        }
                        start = time.monotonic()
                        try:
                            result = await self.mcp.call_tool(
                                "hub_read_devices", request
                            )
                            ok = self._tool_succeeded(result)
                            location_data = (
                                result.data if isinstance(result.data, dict) else {}
                            )
                        except Exception as error:
                            ok = False
                            location_data = {}
                            logger.debug("Causal mode history read failed: %s", error)
                        mode_events = location_data.get("events")
                        self.evidence.record(
                            "hub_read_devices",
                            request,
                            success=ok,
                            elapsed_ms=round((time.monotonic() - start) * 1000),
                            summary=(
                                "Scoped location/mode event history"
                                if ok else "Location/mode history unavailable"
                            ),
                            supports_live_claim=ok,
                            evidence_kind="authoritative_location_event_history",
                            mutates=False,
                            effect="read",
                            details=(
                                {
                                    "count": location_data.get("count"),
                                    "events": mode_events[:20],
                                }
                                if ok and isinstance(mode_events, list) else None
                            ),
                        )
                        increment_active_metric("causal_graph_mode_reads")
                        graph = build_causal_evidence_graph(
                            self.evidence.receipts(), user_prompt
                        )

                    if supports_one_pass_deep_synthesis(graph, user_prompt):
                        # The requested source classes have been checked and
                        # source limitations are explicitly represented.
                        # One evidence-grounded final model pass replaces
                        # redundant exploratory/re-read/model-repair rounds.
                        increment_active_metric("causal_graph_sufficient")
                        if (
                            (graph.get("transitionEvidence") or {})
                            .get("off", {}).get("observed")
                            and not ((graph.get("transitionEvidence") or {})
                                     .get("off", {}).get("directCommand"))
                        ):
                            increment_active_metric("causal_completed_unresolved")
                        increment_active_metric("investigative_finalization")
                        return await self._final_answer(messages)

                    # A deep investigation is not completed merely because a
                    # command producer is verified. Give the model the observed
                    # baseline plus the live capability search/guide workflow to
                    # decide whether additional upstream evidence is required.
                    evidence_graph_brief = (
                        render_causal_evidence_graph(
                            self.evidence.receipts(), user_prompt
                        ) or ""
                    )[:6500]
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST VERIFIED CAUSAL BASELINE (not a completed "
                            "deep investigation):\n"
                            + deterministic_answer
                            + "\n" + evidence_graph_brief
                            + "\nDo not repeat already-completed reads "
                            "unless a specific missing field requires it. "
                            + "Review the user's full investigative objective. "
                            "The producer, historical trigger, conditions and "
                            "alternatives are distinct. If the existing evidence "
                            "does not support a material requested part, discover "
                            "and read the relevant permitted MCP tool. Do not "
                            "redo proven history or make unrelated scans."
                        ),
                    })
                    # The current registered app/rule/log read gateways are
                    # available without fuzzy search and without enabling writes.
                    catalog.expose_read_gateways(
                        ("hub_read_apps_code", "hub_read_rules",
                         "hub_read_diagnostics"),
                        max_declared=self.tool_limit,
                    )
                    tools = catalog.schemas()
                else:
                    if not deep_causal_request:
                        increment_active_metric("investigative_finalization")
                        return await self._final_answer(messages)
            if causal_prefetch == "empty" and not self._investigation_reflection_used.get():
                increment_active_metric("investigative_finalization")
                return await self._final_answer(messages)

        # Explicit historical source sets can now be finalised directly from
        # typed native/journal/config/log evidence. This preserves source clocks
        # and source absence boundaries without a model inventing provenance.
        # Incomplete source classes and unrelated additional objectives retain
        # the established exploratory/model-led investigation.
        if lockout_prefetch:
            bounded_report = render_bounded_focal_reconstruction(
                user_prompt, self.evidence.receipts(),
            )
            if bounded_report is not None:
                increment_active_metric("lockout_focal_evidence_report")
                increment_active_metric("investigative_finalization")
                return bounded_report

        # 0.17.45: a complete, independently corroborated manual OFF already
        # has its light, physical controller, settings and bounded app-log
        # evidence. Synthesise once from this request's receipts and preserve
        # unresolved enforcement/activation claims. Do not let the model
        # rediscover the same facts through unrelated whole-hub reads.
        if lockout_prefetch and collected_lockout_ready_for_synthesis(
            user_prompt, self.evidence.receipts(),
        ):
            increment_active_metric("lockout_prefetch_sufficiency_stop")
            increment_active_metric("investigative_finalization")
            return await self._final_answer(messages)

        # The requested earlier OFF may have fallen outside native switch
        # retention while its native physical-button and OFF-command rows plus
        # a scoped journal OFF remain. When all relevant sources were checked,
        # synthesise once rather than querying unrelated fresh logs.
        if lockout_prefetch and collected_explicit_focal_ready_for_synthesis(
            user_prompt, self.evidence.receipts(),
        ):
            increment_active_metric("lockout_cross_source_sufficiency_stop")
            increment_active_metric("investigative_finalization")
            return await self._final_answer(messages)

        source_completion_retry_used = False
        device_incident_followup_used = False
        device_incident_progress_retry_used = False
        incident_evidence_checkpoint_used = False
        configuration_semantics_retry_used = False
        inventory_only_retry_used = False
        unified_source_followup_used = False
        target_history_scope_retry_used = False
        # A read-only investigation with an explicit historical causal
        # boundary has already run focused host-side evidence collection.
        # Bound further model-directed exploration, then use the existing
        # evidence-grounded final coordinator. Do not alter budgets for
        # writes, confirmations, generic reads or untimed investigations.
        scoped_causal_round_budget = bool(
            deep_causal_request
            and has_explicit_focal_clock(user_prompt)
            and not self._mutation_requested_by_user.get()
        )
        active_round_budget = (
            min(self.max_tool_rounds, 3)
            if self._investigation_reflection_used.get()
            else min(self.max_tool_rounds, 6)
            if scoped_causal_round_budget else self.max_tool_rounds
        )
        if active_round_budget < self.max_tool_rounds:
            increment_active_metric("causal_read_round_budget")
        for round_index in range(active_round_budget):
            if adaptive_investigation or review_first:
                catalog.activate_investigation_read_view(max_declared=self.tool_limit)
                if source_investigation:
                    catalog.replace_declared([
                        *catalog.declared_names, _LOCAL_GROOVY_SOURCE_TOOL,
                    ])
                tools = catalog.schemas()
            if self._investigation_reflection_used.get() and not causal_completion_mode:
                catalog.activate_investigation_read_view(max_declared=self.tool_limit)
                tools = catalog.schemas()
            if causal_completion_mode:
                catalog.activate_causal_provenance_view()
                tools = catalog.schemas()
            set_request_stage(
                f"AI reasoning (round {round_index + 1}/{active_round_budget})"
            )
            assistant = await self._chat(messages, tools)
            calls = assistant.get("tool_calls") or []
            if not calls:
                # A model's voluntary stop is a source-choice checkpoint.
                # Recover independently timestamped archive events while the
                # existing model still has a bounded read-only tool round.
                # Never delay publication merely to chase an unreachable log.
                if (investigative_request
                        and round_index + 1 < active_round_budget
                        and await self._recover_journal_into_discovery(
                            user_prompt, messages)):
                    messages.insert(len(messages) - 1, assistant)
                    catalog.activate_investigation_read_view(
                        max_declared=self.tool_limit)
                    catalog.expose_read_gateways(
                        ("hub_read_devices", "hub_read_apps_code",
                         "hub_read_rules", "hub_read_diagnostics", SEARCH_TOOL),
                        max_declared=self.tool_limit,
                    )
                    tools = catalog.schemas()
                    continue
                # Source scope is a precondition for any historical zero-event
                # conclusion. A successful hub-wide read cannot answer a
                # question about independently resolved device IDs. The LLM
                # retains tool choice; the host provides a bounded read-only
                # completion opportunity instead of assuming no events.
                if (investigative_request
                        and not target_history_scope_retry_used
                        and not self._mutation_requested_by_user.get()
                        and round_index + 1 < active_round_budget):
                    scoped_followup = render_target_scope_followup(
                        user_prompt, self.evidence.receipts())
                    if scoped_followup:
                        target_history_scope_retry_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit)
                        catalog.expose_read_gateways(
                            ("hub_read_devices", SEARCH_TOOL),
                            max_declared=self.tool_limit,
                        )
                        messages.extend([
                            assistant, {"role": "user", "content": scoped_followup},
                        ])
                        tools = catalog.schemas()
                        increment_active_metric("target_history_scope_retry")
                        continue
                # One source-driven recovery chance for the original HomeBrain
                # investigator, never a second V2 planner or a keyword router.
                # Model chooses the input READ from the existing permissions;
                # the host neither grants a target identity nor executes it.
                if (investigative_request
                        and not self._mutation_requested_by_user.get()
                        and not unified_source_followup_used
                        and round_index + 1 < active_round_budget):
                    followup = unified_investigation_followup(
                        self.evidence.receipts(), user_prompt)
                    if followup:
                        unified_source_followup_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit)
                        catalog.expose_read_gateways(
                            ("hub_read_devices", "hub_read_apps_code",
                             "hub_read_diagnostics", "hub_read_rules",
                             SEARCH_TOOL),
                            max_declared=self.tool_limit)
                        messages.extend([
                            assistant, {"role": "user", "content": followup},
                        ])
                        tools = catalog.schemas()
                        increment_active_metric(
                            "unified_investigation_input_followup")
                        continue
                # Primary diagnostic objective has not been met if all the
                # reads so far are room/identity listings. Give the model ONE
                # further evidence-source choice instead of shipping the
                # successful inventory result as a false diagnosis.
                if (diagnostic_objective
                        and (inventory_without_investigation(
                            user_prompt, self.evidence.receipts()
                        ) or inventory_answer(assistant.get("content") or ""))):
                    if (not inventory_only_retry_used
                            and round_index + 1 < active_round_budget):
                        inventory_only_retry_used = True
                        increment_active_metric("investigation_inventory_only_retry")
                        catalog.hide_inventory_during_investigation()
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit
                        )
                        catalog.expose_read_gateways(
                            ("hub_read_apps_code", "hub_read_devices",
                             "hub_read_diagnostics", "hub_read_rules"),
                            max_declared=self.tool_limit,
                        )
                        messages.extend([
                            assistant,
                            {"role": "user", "content": incomplete_investigation_retry(
                                user_prompt, self.evidence.receipts()
                            )},
                        ])
                        tools = catalog.schemas()
                        continue
                    increment_active_metric("investigation_inventory_only_stopped")
                    return honest_partial_answer(
                        user_prompt, self.evidence.receipts()
                    )
                if last_proposal_error is not None:
                    _name, _rejected_arguments, reason = last_proposal_error
                    increment_active_metric("proposal_validation_failures")
                    return (
                        "No Hubitat action was queued or executed because Rule "
                        f"Machine proposal validation failed. Exact reason: {reason} "
                        "The rejected gateway payload is not shown because it "
                        "may contain private identifiers or tool tokens."
                    )
                if review_first:
                    return self._unverified_mutation_guard(
                        str(assistant.get("content") or "").strip()
                        or (
                            "Read-only inspection did not verify the complete "
                            "rule trigger and action structure. No duplicate "
                            "was created."
                        )
                    )
                if stateful_authoring:
                    return (
                        "No automation was created or queued. Live Rule Machine "
                        "capability guides were checked, but HomeBrain did not "
                        "produce a complete validated structured rule proposal. "
                        "No existing rule or device was changed. "
                        "Retrieve the live addTrigger/addAction discovery schemas "
                        "and retry before requesting any confirmation."
                    )
                # AI-led configuration semantics: if a source-backed
                # investigation is about to conclude that one stored setting
                # establishes runtime behaviour, but no corresponding Groovy
                # implementation was read, offer ONE high-information source
                # opportunity. This runs on actual typed app-config receipts
                # and the model's proposed interpretation, never a keyword
                # to device/tool route. No writes become available.
                if (investigative_request and not configuration_semantics_retry_used
                        and round_index + 1 < active_round_budget
                        and not self._mutation_requested_by_user.get()):
                    semantics_prompt = configuration_semantics_followup(
                        str(assistant.get("content") or ""),
                        self.evidence.receipts(),
                    )
                    if semantics_prompt:
                        configuration_semantics_retry_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit
                        )
                        catalog.replace_declared([
                            *catalog.declared_names,
                            _LOCAL_GROOVY_SOURCE_TOOL,
                            "hub_read_apps_code",
                            SEARCH_TOOL,
                        ])
                        if catalog.schemas():
                            increment_active_metric(
                                "configuration_semantics_source_retry"
                            )
                            messages.extend([
                                assistant,
                                {"role": "user", "content": semantics_prompt},
                            ])
                            tools = catalog.schemas()
                            continue

                # A model that selects no new source must not replace a
                # receipt-grounded partial investigation with an unrelated
                # generic refusal (for example, a fresh-log retry when the
                # historical app-log window was already checked).
                baseline_snapshot = self._investigation_baseline.get()
                if self._investigation_reflection_used.get() and baseline_snapshot:
                    new_successful_read = any(
                        isinstance(item, dict)
                        and item.get("success") is True
                        and item.get("effect") == "read"
                        and item.get("evidence_kind") not in {
                            "focal_archived_state_history",
                            "focal_exact_state_history",
                        }
                        for item in self.evidence.receipts()[baseline_snapshot[1]:]
                    )
                    if not new_successful_read:
                        increment_active_metric("skills_focal_unverified_stop")
                        return baseline_snapshot[0]
                answer = str(assistant.get("content") or "")
                resolver_used = any(
                    json.loads(signature)[0] == _LOCAL_RESOLVE_TOOL
                    for signature in completed_calls
                )
                if (
                    re.search(
                        r"\b(?:could not|couldn't|cannot|can't|still cannot|still can't)\s+find\b",
                        answer,
                        re.I,
                    )
                    and not resolver_used
                ):
                    messages.extend([
                        assistant,
                        {
                            "role": "user",
                            "content": (
                                "HOST TARGET-RESOLUTION REQUIREMENT: Do not conclude "
                                "that the named device is absent yet. Call "
                                "homebrain_resolve_device with the user's device "
                                "wording; it performs bounded punctuation-tolerant "
                                "label searches without loading the full inventory."
                            ),
                        },
                    ])
                    continue
                if re.search(
                    r"\b(?:please confirm|ready to queue|have queued)\b",
                    answer,
                    re.I,
                ):
                    ungrounded_confirmation_claim_seen = True
                    messages.extend([
                        assistant,
                        {
                            "role": "user",
                            "content": (
                                "HOST CONFIRMATION ERROR: No structured sensitive "
                                "tool call was submitted, so no action is queued and "
                                "you must not ask for confirmation or claim it was "
                                "queued. Submit the complete tool call group now."
                            ),
                        },
                    ])
                    continue
                capability_decision = capability_grounding.decide(answer)
                if capability_decision.action is CapabilityAction.DISCOVER:
                    if capability_discovery:
                        capability_grounding.record_discovery(
                            len(capability_additions)
                        )
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    f"{capability_decision.message}\n\n"
                                    "HOST DISCOVERY RESULT\n"
                                    f"{capability_discovery}"
                                ),
                            },
                        ])
                        continue
                    search_tool = catalog.declared_tool(SEARCH_TOOL)
                    if search_tool is not None:
                        execution = await self.executor.execute(
                            SEARCH_TOOL,
                            {"query": str(user_prompt).strip()},
                            tool=search_tool,
                            supports_live_claim=False,
                        )
                        additions = (
                            catalog.expand(execution.result, query=user_prompt)
                            if execution.result is not None
                            else []
                        )
                        capability_grounding.record_discovery(len(additions))
                        if additions:
                            if adaptive_investigation:
                                catalog.activate_investigation_read_view(
                                    max_declared=self.tool_limit
                                )
                            tools = catalog.schemas()
                            logger.info(
                                "Capability recovery expanded registry with: %s",
                                ", ".join(item.name for item in additions),
                            )
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    f"{capability_decision.message}\n\n"
                                    "HOST DISCOVERY RESULT\n"
                                    f"{execution.content}"
                                ),
                            },
                        ])
                        continue
                if (
                    capability_decision.action
                    is CapabilityAction.REJECT_UNGROUNDED
                ):
                    return str(capability_decision.message)
                receipt_device_ids = extract_receipt_device_ids(
                    self.evidence.receipts()
                )
                if receipt_device_ids:
                    # Device-claim grounding is an auxiliary final-answer guard;
                    # it must not trigger a new complete-inventory read after the
                    # model has already synthesized its answer. Reuse any detailed
                    # manifest already cached for another reason and supplement it
                    # with id/label pairs from this turn's structured tool results.
                    # The latter covers common targeted reads such as
                    # homebrain_device_history even when the full cache is empty.
                    peek_cached = getattr(self.mcp, "peek_cached_devices", None)
                    known_devices = (
                        list(peek_cached()) if callable(peek_cached) else []
                    )
                    known_devices.extend(
                        extract_tool_message_device_identities(messages)
                    )
                    mismatched_label = find_named_device_mismatch(
                        answer,
                        known_devices,
                        receipt_device_ids | extract_event_reporter_device_ids(messages),
                    )
                    if mismatched_label:
                        # A broad unrelated log row is not a new user target.
                        # Preserve a truthful, source-grounded explanation for
                        # the explicitly requested device, without spending
                        # another model round chasing a stray named sensor.
                        focused_explanation = render_requested_device_explanation(
                            user_prompt, self.evidence.receipts(),
                            mismatched_label,
                        )
                        if focused_explanation is not None:
                            increment_active_metric("requested_device_drift_guard")
                            # Don't let a fallback short-circuit the mandatory
                            # read-only command source completion in _final_answer.
                            if pending_scoped_explanation_command_read(
                                user_prompt, self.evidence.receipts(),
                            ) is not None:
                                completed = await self._final_answer(messages)
                                if not re.search(
                                    r"(?<![\w-])" + re.escape(mismatched_label)
                                    + r"(?![\w-])",
                                    completed, re.IGNORECASE,
                                ):
                                    return completed
                                # If final synthesis still reintroduces the
                                # unrelated subject, render the verified
                                # target after the command read has completed.
                                refreshed = render_requested_device_explanation(
                                    user_prompt, self.evidence.receipts(),
                                    mismatched_label,
                                )
                                return refreshed or focused_explanation
                            return focused_explanation
                    device_claim_decision = device_claim_grounding.decide(
                        mismatched_label
                    )
                    if device_claim_decision.action is DeviceClaimAction.RETRY:
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": str(device_claim_decision.message),
                            },
                        ])
                        continue
                    if device_claim_decision.action is DeviceClaimAction.REFUSE:
                        # For delegated incident selection, a model may drift
                        # onto an unrelated device after collecting a valid
                        # device-specific history. Retain the actual observed
                        # evidence rather than ending with an empty refusal.
                        partial = render_grounded_incident_fallback(
                            user_prompt, self.evidence.receipts()
                        )
                        if partial:
                            increment_active_metric(
                                "investigation_grounded_fallback"
                            )
                            return partial
                        return str(device_claim_decision.message)
                # Host-owned investigative prefetches may have already read
                # scoped logs before the model loop. Grounding must consume
                # the SAME current-request receipts as final synthesis, or it
                # incorrectly refuses despite a successful log query.
                if (
                    getattr(grounding, "logs_requested", False)
                    and not getattr(grounding, "logs_checked", False)
                    and callable(getattr(grounding, "is_live_log_call", None))
                    and callable(getattr(grounding, "record_tool_outcome", None))
                ):
                    for receipt in self.evidence.receipts():
                        if (
                            not isinstance(receipt, dict)
                            or receipt.get("success") is not True
                        ):
                            continue
                        gateway = str(receipt.get("tool") or "")
                        arguments = receipt.get("arguments") or {}
                        if not isinstance(arguments, dict):
                            continue
                        if grounding.is_live_log_call(gateway, arguments):
                            grounding.record_tool_outcome(
                                gateway, arguments, success=True,
                            )
                            break
                decision = grounding.decide_no_tool_calls(
                    has_live_evidence=self.evidence.has_live_evidence()
                )
                if decision.action is GroundingAction.RETRY:
                    messages.extend([
                        assistant,
                        {"role": "user", "content": str(decision.message)},
                    ])
                    continue
                if decision.action is GroundingAction.REFUSE:
                    return str(decision.message)

                # A model-led root-cause investigation needs a read that
                # discriminates between the leading explanations, not another
                # generic history or unrelated log sample. Allow ONE extra
                # evidence-choice round after a substantive target device read.
                # This is NOT a keyword tool router: the interpreted objective
                # controls eligibility; the model chooses among advertised
                # read-only tools, with existing safety/round gates intact.
                if (connectivity_incident
                        and not incident_evidence_checkpoint_used
                        and round_index + 1 < active_round_budget
                        and not self._mutation_requested_by_user.get()):
                    target_checkpoint = evidence_progress_checkpoint(
                        user_prompt, self.evidence.receipts(),
                    )
                    if target_checkpoint:
                        incident_evidence_checkpoint_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit
                        )
                        catalog.expose_read_gateways(
                            ("hub_read_apps_code", "hub_read_rules",
                             "hub_read_devices", "hub_read_diagnostics",
                             SEARCH_TOOL),
                            max_declared=self.tool_limit,
                        )
                        if catalog.schemas():
                            increment_active_metric(
                                "incident_evidence_checkpoint_retry"
                            )
                            messages.extend([
                                assistant,
                                {"role": "user", "content": target_checkpoint},
                            ])
                            tools = catalog.schemas()
                            continue

                # General evidence-sufficiency checkpoint: across device
                # telemetry, motion, scheduler or other declared domain plans,
                # an important source never queried is an opportunity for one
                # more targeted read, not proof the question is unanswerable.
                # Checked-but-empty and truly unavailable sources are not
                # automatic retry triggers.
                if (
                    contract is not None
                    and not self._investigation_reflection_used.get()
                    and not self._mutation_requested_by_user.get()
                ):
                    assessment = assess_investigation(
                        contract, self.evidence.receipts()
                    )
                    missing_unchecked = any(
                        item.get("necessary") is True
                        and item.get("state") == "not-checked"
                        for item in assessment.get("requirements") or []
                    )
                    if missing_unchecked:
                        read_tools = catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit
                        )
                        if read_tools:
                            self._investigation_reflection_used.set(True)
                            increment_active_metric(
                                "investigation_general_evidence_retry"
                            )
                            messages.extend([
                                assistant,
                                {"role": "user", "content": (
                                    render_investigation_checkpoint(
                                        user_prompt, self.evidence.receipts(),
                                        available_read_tools=read_tools,
                                        candidate_hypotheses=(
                                            task_plan.candidate_hypotheses
                                            if task_plan is not None
                                            and task_plan.operation == "investigate"
                                            else ()
                                        ),
                                    )
                                    + "\nHOST MISSING SOURCE REQUIREMENTS: "
                                    + json.dumps(
                                        assessment.get("nextMissingSources") or [],
                                        ensure_ascii=False,
                                    )
                                    + "\nFind the most decisive feasible "
                                      "read-only source; do not repeat already "
                                      "checked sources or invent tool leaves."
                                )},
                            ])
                            tools = catalog.schemas()
                            continue

                # A single-device offline/MQTT investigation cannot be
                # completed merely from status, a bounded event page and
                # watchdog logs. Give the model ONE additional read-only
                # opportunity to inspect installed driver code or controlling
                # automation, or state which upstream capability is unavailable.
                if (not device_incident_followup_used
                        and not self._mutation_requested_by_user.get()):
                    followup = device_incident_followup(
                        user_prompt, self.evidence.receipts()
                    )
                    if followup:
                        device_incident_followup_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit
                        )
                        catalog.expose_read_gateways(
                            ("hub_read_apps_code", "hub_read_rules",
                             "hub_read_devices", "hub_read_diagnostics",
                             SEARCH_TOOL),
                            max_declared=self.tool_limit,
                        )
                        if catalog.schemas():
                            increment_active_metric(
                                "device_incident_depth_retry"
                            )
                            messages.extend([
                                assistant,
                                {"role": "user", "content": followup},
                            ])
                            tools = catalog.schemas()
                            continue

                # A targeted dependency lookup is a useful investigative
                # lead but not proof of a controlling automation. Give the AI
                # at most one progress-gated chance to inspect the actual
                # stored configuration or driver source before stopping. Do
                # not waste a retry after the last allotted model round.
                if (connectivity_incident and device_incident_followup_used
                        and not device_incident_progress_retry_used
                        and round_index + 1 < active_round_budget
                        and not self._mutation_requested_by_user.get()):
                    followthrough = incident_progress_followup(
                        user_prompt, self.evidence.receipts(),
                    )
                    if followthrough:
                        device_incident_progress_retry_used = True
                        catalog.activate_investigation_read_view(
                            max_declared=self.tool_limit,
                        )
                        catalog.expose_read_gateways(
                            ("hub_read_apps_code", "hub_read_rules",
                             "hub_read_devices", "hub_read_diagnostics",
                             SEARCH_TOOL),
                            max_declared=self.tool_limit,
                        )
                        if catalog.schemas():
                            increment_active_metric(
                                "device_incident_progress_retry"
                            )
                            messages.extend([
                                assistant,
                                {"role": "user", "content": followthrough},
                            ])
                            tools = catalog.schemas()
                            continue

                # A semantic investigation declares source *classes*, not
                # conclusions. Check actual read receipts before allowing the
                # model to stop after only an identity/room lookup. One bounded
                # retry is permitted; absence of a source remains unresolved.
                if (task_plan is not None and task_plan.operation == "investigate"
                        and task_plan.required_evidence_kinds):
                    source_coverage = assess_task_source_coverage(
                        task_plan.required_evidence_kinds, self.evidence.receipts(),
                    )
                    if source_coverage.missing and not source_completion_retry_used:
                        source_completion_retry_used = True
                        increment_active_metric("task_evidence_retry")
                        messages.extend([
                            assistant,
                            {"role": "user", "content": source_coverage.retry_instruction()},
                        ])
                        continue
                    if source_coverage.missing:
                        increment_active_metric("task_evidence_incomplete")
                        missing_sources = ", ".join(source_coverage.missing)
                        note = (
                            "\n\n**Evidence coverage incomplete:** Required "
                            "read-source classes not verified as checked: "
                            f"{missing_sources}. These gaps prevent treating the "
                            "investigation as comprehensive; read-tool success "
                            "alone cannot prove any specific historical cause."
                        )
                        if investigative_request:
                            increment_active_metric("investigative_finalization")
                            completed_answer = await self._final_answer(messages)
                            # Late mandatory host reads can fill the precise
                            # source gap that caused this retry. Never append
                            # stale "app_logs unchecked" after an app-ID log
                            # query has now succeeded.
                            final_coverage = assess_task_source_coverage(
                                task_plan.required_evidence_kinds,
                                self.evidence.receipts(),
                            )
                            if not final_coverage.missing:
                                return completed_answer
                            current_missing = ", ".join(final_coverage.missing)
                            return completed_answer + (
                                "\\n\\n**Evidence coverage incomplete:** Required "
                                "read-source classes not verified as checked: "
                                f"{current_missing}. This does not prove the "
                                "historical event or cause."
                            )
                        return self._unverified_mutation_guard(
                            str(assistant.get("content") or
                                "The investigation is incomplete.")
                        ) + note

                # A causal investigation with observed boundary commands still has
                # one unresolved provenance slot until an app/rule/log source is
                # checked. Give the tool loop one bounded chance to fill that slot.
                # If the model declines or no stronger source exists, final
                # synthesis will explicitly preserve the gap instead of guessing.
                if causal_request and not causal_completion_retry_used:
                    followup = render_command_source_followup(
                        self.evidence.receipts()
                    )
                    if followup:
                        causal_completion_retry_used = True
                        causal_completion_mode = True
                        increment_active_metric("causal_completion_retry")
                        messages.extend([
                            assistant,
                            {"role": "user", "content": followup},
                        ])
                        continue

                # All investigative completions go through the shared final
                # coordinator. Previously a voluntary no-tool model response
                # bypassed the evidence brief, causal timeline, and validators,
                # so production could gather strong evidence and still omit it.
                if investigative_request:
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

                return self._unverified_mutation_guard(
                    str(assistant.get("content") or "Done.")
                )
            if self._investigation_reflection_used.get():
                # Defence in depth: a discovered tool cannot bypass the read-
                # only view by using a mutating gateway or structured subcall.
                forbidden = []
                for proposed in calls:
                    func = proposed.get("function") or {}
                    name = str(func.get("name") or "")
                    arguments = func.get("arguments") or {}
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except (ValueError, TypeError):
                            arguments = {}
                    if name.startswith(("hub_manage_", "hub_set_")) or classify_tool_effect(
                        catalog.available_tool(name),
                        arguments if isinstance(arguments, dict) else {},
                    ).mutates:
                        forbidden.append(name)
                if forbidden:
                    increment_active_metric("investigation_write_blocked")
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST READ-ONLY ENFORCEMENT: A proposed tool "
                            "is write-capable or unavailable. No write was "
                            "executed. Continue only with available read "
                            "tools, or state the evidence limitation."
                        ),
                    })
                    continue

            if causal_completion_mode:
                allowed_completion_tools = set(catalog.causal_provenance_names())
                disallowed_completion_calls = [
                    call
                    for call in calls
                    if str((call.get("function") or {}).get("name") or "")
                    not in allowed_completion_tools
                ]
                if disallowed_completion_calls:
                    messages.append(assistant)
                    for call in calls:
                        function = call.get("function") or {}
                        name = str(function.get("name") or "")
                        messages.append({
                            "role": "tool",
                            "tool_name": name,
                            "content": json.dumps({
                                "error": (
                                    "Causal completion is restricted to read-only "
                                    "app/rule/log provenance tools. Device, sensor, "
                                    "location, and mutation tools are not available "
                                    "in this bounded phase."
                                ),
                            }),
                        })
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

            sensitive: list[tuple[str, dict[str, Any]]] = []
            round_actions: list[tuple[str, dict[str, Any]]] = []
            proposal_errors: list[tuple[str, str]] = []
            blocked_proposal_writes: list[str] = []
            blocked_unauthorized_writes: list[str] = []
            round_has_mutation = False
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                arguments = normalize_rule_machine_proposal(name, arguments)
                round_actions.append((name, arguments))
                tool = catalog.declared_tool(name)
                effect = classify_tool_effect(tool, arguments)
                if (task_plan is not None and task_plan.operation == "propose"
                        and not self._mutation_requested_by_user.get()
                        and effect.mutates):
                    blocked_proposal_writes.append(name)
                    continue
                if effect.mutates and not self._mutation_requested_by_user.get():
                    # Model-generated actions do not grant authority to
                    # mutate. Refuse the entire proposal round, including
                    # companion reads, and keep this request read-only.
                    blocked_unauthorized_writes.append(name)
                    continue
                if (
                    not self.rule_write_enabled
                    and name == ConfirmedActionCoordinator.RULE_GATEWAY
                    and effect.mutates
                ):
                    return RULE_WRITES_DISABLED_MESSAGE
                proposal_error = rule_machine_proposal_error(
                    name, arguments,
                    # A cumulative elapsed-usage budget is NOT a single
                    # delay step. Its separate topology validator enforces
                    # periodic accumulation and reset instead.
                    user_prompt=None if stateful_authoring else user_prompt,
                )
                if (
                    proposal_error is None
                    and stateful_authoring
                    and name == RULE_MACHINE_GATEWAY
                    and arguments.get("tool") == "hub_set_rule"
                ):
                    proposal_error = cumulative_rule_proposal_error(arguments)
                if proposal_error is not None and effect.mutates:
                    proposal_errors.append((name, proposal_error))
                if tool is not None and effect.mutates:
                    round_has_mutation = True
                    self._mark_mutation()
                if (
                    tool
                    and self.confirmation_policy.requires_confirmation(effect)
                ):
                    sensitive.append((name, arguments))
            if blocked_unauthorized_writes or blocked_proposal_writes:
                # Prevent a model-selected write from silently converting a
                # read-only design request into a mutation or confirmation.
                # Reject the complete model round atomically, including any
                # companion reads, to preserve a coherent tool transcript.
                if blocked_unauthorized_writes:
                    increment_active_metric("read_only_model_write_blocked")
                else:
                    increment_active_metric("proposal_write_attempts_blocked")
                blocked_message = (
                    "Read-only user request: model-proposed write was blocked. "
                    "No Hubitat command was executed or queued. Continue "
                    "with read-only evidence tools and a grounded conclusion."
                    if blocked_unauthorized_writes else
                    "Proposal-only task: no tool calls in this round "
                    "were executed. Continue using read-only discovery "
                    "and provide a proposal without changing Hubitat."
                )
                messages.append(assistant)
                for call in calls:
                    name = str((call.get("function") or {}).get("name") or "")
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps({
                            "error": (
                                blocked_message
                            ),
                        }),
                    })
                continue
            if proposal_errors:
                failed_name, failed_reason = proposal_errors[0]
                failed_arguments = next(
                    (
                        arguments
                        for name, arguments in round_actions
                        if name == failed_name
                    ),
                    {},
                )
                last_proposal_error = (
                    failed_name,
                    failed_arguments,
                    failed_reason,
                )
                proposal_error_retries += 1
                if proposal_error_retries >= 2:
                    increment_active_metric("proposal_validation_failures")
                    # Never echo the model's full proposed native write payload:
                    # it can contain identifiers, tool-guide best-practice
                    # tokens, user rule labels and potentially sensitive data.
                    # The validator reason is sufficient for corrective work.
                    return (
                        "No Hubitat action was queued or executed because Rule "
                        "Machine proposal validation failed twice. Exact reason: "
                        f"{failed_reason} The proposed write is retained only "
                        "in the in-request validator, not reflected back as "
                        "a raw gateway payload."
                    )
                messages.append(assistant)
                errors_by_name = dict(proposal_errors)
                for call in calls:
                    function = call.get("function") or {}
                    name = str(function.get("name") or "")
                    content = errors_by_name.get(
                        name,
                        (
                            "This action group was not executed because another "
                            "Rule Machine proposal in the group was invalid. "
                            "Resubmit the complete group after correcting it."
                        ),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps({"error": content}),
                    })
                continue
            rule_create_error = (
                await self.rule_authoring.duplicate_create_group_error([
                    arguments
                    for name, arguments in round_actions
                    if name == ConfirmedActionCoordinator.RULE_GATEWAY
                ])
            )
            if rule_create_error is not None:
                return rule_create_error
            if sensitive:
                last_proposal_error = None
                decision = self.confirmation_policy.decide(session_id, sensitive)
                if decision.action is ConfirmationAction.REJECT:
                    return str(decision.message)
                self.confirmations.queue(
                    session_id,
                    round_actions,
                    messages,
                    assistant,
                )
                return str(decision.message)
            messages.append(assistant)
            duplicate_signature_seen = False
            round_history_evidence_sufficient = False
            set_request_stage(
                f"Executing tool calls (round {round_index + 1}/{active_round_budget})"
            )
            round_tool_failure = False
            causal_subject_to_expand: dict[str, Any] | None = None
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                original_tool_name = name
                gateway_repair = None
                if name.startswith("hub_read_"):
                    gateway_repair = catalog.compatible_read_gateway(
                        name, arguments,
                    )
                    if gateway_repair is not None:
                        name = gateway_repair[0]
                        increment_active_metric("gateway_read_rerouted")
                if causal_request:
                    if name == _LOCAL_DEVICE_HISTORY_TOOL:
                        arguments = causal_subject_history_arguments(
                            user_prompt,
                            arguments,
                        )
                    arguments = _normalize_causal_log_call(
                        name,
                        arguments,
                        self.evidence.receipts(),
                        original_user=user_prompt,
                    )
                signature = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False, default=str)
                if signature in completed_calls:
                    duplicate_signature_seen = True
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps({
                            "note": (
                                "Skipped: identical to a call already "
                                "executed earlier this turn."
                            ),
                        }),
                    })
                    continue
                completed_calls.add(signature)
                # Every call gets fresh history-reasoning flags.  Keeping
                # these per call avoids state leaking from a prior tool in a
                # mixed round or an undeclared-tool branch.
                history_reasoning_bypass = False
                investigative_history_bypass = False
                tool = catalog.declared_tool(name)
                if tool is None and gateway_repair is not None:
                    # The model called a declared read gateway; the corrected
                    # gateway is positively established by the same live MCP
                    # catalog. Never expose or execute any write gateway here.
                    tool = gateway_repair[1]
                requested_history_name = str(arguments.get("name") or "").strip()
                requested_history_key = re.sub(
                    r"[^a-z0-9]", "", requested_history_name.casefold()
                )
                redundant_causal_room_filter = bool(
                    causal_request
                    and causal_subject_evidence_expanded
                    and name == _LOCAL_FILTER_TOOL
                    and str(arguments.get("attribute") or "").strip().casefold() == "room"
                )
                broad_causal_inventory = bool(
                    causal_request
                    and _is_broad_device_inventory_call(name, arguments)
                )
                missing_related_attribute = bool(
                    investigative_request
                    and name == _LOCAL_DEVICE_HISTORY_TOOL
                    and investigative_subject_history_key
                    and requested_history_key
                    and requested_history_key != investigative_subject_history_key
                    and not str(arguments.get("attribute") or "").strip()
                )
                gateway_error = (
                    catalog.gateway_operation_error(name, arguments)
                    if tool is not None
                    else None
                )
                source_scope_error = source_app_scope_error(
                    name, arguments, self.evidence.receipts(), user_prompt,
                ) if investigative_request else None
                if not tool:
                    round_tool_failure = True
                    content = json.dumps({"error": f"Undeclared MCP tool: {name}"})
                elif redundant_causal_room_filter:
                    content = json.dumps({
                        "note": (
                            "Skipped: exact-room causal evidence discovery was already "
                            "completed host-side from the resolved subject metadata. "
                            "Use the gathered controller/provenance evidence and move "
                            "to a different evidence class."
                        )
                    })
                elif broad_causal_inventory:
                    round_tool_failure = True
                    increment_active_metric("causal_broad_inventory_blocked")
                    content = json.dumps({
                        "error": (
                            "Broad hub_list_devices inventory reads are not a causal "
                            "provenance source and are blocked for this investigation. "
                            "Use homebrain_device_history/homebrain_resolve_device for "
                            "the named subject, or a scoped labelFilter/roomFilter when "
                            "a genuinely new device identity is required."
                        )
                    })
                elif block_unscoped_historical_logs(
                    user_prompt, self.evidence.receipts(), name, arguments,
                ):
                    round_tool_failure = True
                    increment_active_metric("unscoped_historical_logs_blocked")
                    content = json.dumps({
                        "error": (
                            "This question names one device and a historical "
                            "date. Unfiltered recent hub logs are unrelated to "
                            "that time and cannot establish its command actor. "
                            "Use target-scoped device event/command history "
                            "and matching historical app logs if available."
                        )
                    })
                elif missing_related_attribute:
                    round_tool_failure = True
                    increment_active_metric("investigative_attribute_required")
                    content = json.dumps({
                        "error": (
                            "Investigative related-device history requires an explicit "
                            "attribute. Choose the material capability you intend to "
                            "compare (for example motion, illuminance, contact, switch) "
                            "and retry homebrain_device_history with attribute=... . "
                            "Do not infer absence of an attribute from generic history."
                        )
                    })
                elif source_scope_error is not None:
                    # No model-selected source can silently drift to an
                    # unverified app identity during this investigation.
                    # Discard the rejected signature so a later corroborated
                    # relation can authorize a fresh READ, not a mutation.
                    completed_calls.discard(signature)
                    round_tool_failure = True
                    increment_active_metric("investigation_source_target_mismatch")
                    content = json.dumps({"error": source_scope_error})
                elif gateway_error is not None:
                    # An invalid gateway operation was never executed. Do not
                    # poison duplicate-call deduplication: after exact tool
                    # discovery, the model may retry with a validated mapping.
                    completed_calls.discard(signature)
                    round_tool_failure = True
                    increment_active_metric("gateway_operation_rejected")
                    content = json.dumps({
                        "error": (
                            f"Gateway/sub-tool compatibility check rejected this call: "
                            f"{gateway_error}"
                        )
                    })
                else:
                    execution = await self.executor.execute(
                        name,
                        dict(arguments),
                        tool=tool,
                        supports_live_claim=name != "hub_search_tools",
                        evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),
                    )
                    if execution.effect.mutates:
                        self._mark_mutation()
                    grounding.record_tool_outcome(
                        name,
                        dict(arguments),
                        success=execution.success,
                    )

                    # A causal subject read may begin attribute-less, infer one
                    # binary state from a full mixed page, yet still establish
                    # no bounded interval because the older opposite boundary
                    # was crowded out by noisy telemetry. Before the host is
                    # allowed to declare an empty causal subject, deterministically
                    # retry that same canonical device once with the inferred
                    # state attribute. This is host-generated, so it consumes no
                    # additional model round or model-directed read budget.
                    if (
                        causal_request
                        and name == _LOCAL_DEVICE_HISTORY_TOOL
                        and execution.success
                        and execution.result is not None
                    ):
                        retry_arguments = inferred_state_retry_arguments(
                            name,
                            arguments,
                            execution.result,
                        )
                        if retry_arguments is not None:
                            retry_signature = json.dumps(
                                [name, retry_arguments],
                                sort_keys=True,
                                ensure_ascii=False,
                                default=str,
                            )
                            if retry_signature not in completed_calls:
                                completed_calls.add(retry_signature)
                                increment_active_metric(
                                    "causal_inferred_attribute_retry"
                                )
                                retry_execution = await self.executor.execute(
                                    name,
                                    retry_arguments,
                                    tool=tool,
                                    supports_live_claim=True,
                                    evidence_kind=_EVIDENCE_KINDS.get(
                                        name, "tool_result"
                                    ),
                                )
                                grounding.record_tool_outcome(
                                    name,
                                    dict(retry_arguments),
                                    success=retry_execution.success,
                                )
                                if (
                                    retry_execution.success
                                    and retry_execution.result is not None
                                ):
                                    execution = retry_execution

                    content = execution.content
                    result = execution.result
                    if not execution.success:
                        round_tool_failure = True
                    if result is not None:
                        if name == "hub_search_tools":
                            additions = catalog.expand(
                                result, query=str(arguments.get("query") or "")
                            )
                            if additions:
                                tools = catalog.schemas()
                                logger.info("Tool search expanded registry with: %s", ", ".join(item.name for item in additions))
                        deterministic_message = present_tool_result(
                            name,
                            result.data,
                            failed=not self._tool_succeeded(result),
                            fallback_error=result.text,
                        )
                        if (
                            name == _LOCAL_CONTROL_TOOL
                            and isinstance(result.data, dict)
                            and isinstance(result.data.get("choices"), list)
                        ):
                            self._choices.set([
                                str(choice)
                                for choice in result.data["choices"]
                                if str(choice).strip()
                            ])
                        direct_home_snapshot = (
                            name == _LOCAL_HOME_SNAPSHOT_TOOL
                            and any(
                                re.search(pattern, user_prompt.casefold()) is not None
                                for pattern in _HOME_STATE_PATTERNS
                            )
                        )
                        history_reasoning_bypass = (
                            name == _LOCAL_DEVICE_HISTORY_TOOL
                            and self._tool_succeeded(result)
                        )
                        temporal_history_answer_ready = (
                            history_reasoning_bypass
                            and isinstance(result.data, dict)
                            and isinstance(result.data.get("temporalAnalysis"), dict)
                        )
                        investigative_history_bypass = (
                            history_reasoning_bypass and investigative_request
                        )
                        first_investigative_subject = bool(
                            investigative_history_bypass
                            and investigative_subject_history_key is None
                        )
                        if first_investigative_subject:
                            resolved_subject = str(
                                result.data.get("label")
                                or result.data.get("requested")
                                or requested_history_name
                                or ""
                            ).strip()
                            investigative_subject_history_key = re.sub(
                                r"[^a-z0-9]", "", resolved_subject.casefold()
                            ) or None
                            if causal_request and isinstance(result.data, dict):
                                causal_subject_to_expand = dict(result.data)
                                if not subject_has_observed_intervals(result.data):
                                    causal_subject_no_intervals = True
                        if (
                            deterministic_message is not None
                            and not history_reasoning_bypass
                            and (
                                (
                                    name not in {_LOCAL_FILTER_TOOL, _LOCAL_QUERY_TOOL, _LOCAL_HOME_SNAPSHOT_TOOL, _LOCAL_WEATHER_TOOL}
                                    or direct_home_snapshot
                                )
                                or not self._tool_succeeded(result)
                            )
                        ):
                            return deterministic_message
                messages.append({
                    "role": "tool", "tool_name": original_tool_name,
                    "content": content,
                })
                if gateway_repair is not None:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST VERIFIED READ-GATEWAY CORRECTION: the "
                            "requested operation was executed through the "
                            "live-advertised, compatible read gateway "
                            + name + " instead of " + original_tool_name
                            + ". This is tool-routing evidence only, not "
                            "proof of any physical-device event."
                        ),
                    })
                # The compact final evidence packet retains a short prefix
                # per tool. Collect verified contiguous source pages within
                # this request; only on full reconstruction project complete
                # relevant candidate method bodies, including late-file code.
                # No new MCP read, command, or Groovy evaluation occurs.
                if (source_investigation
                        or (connectivity_incident and adaptive_investigation)):
                    if (
                        name == "hub_read_apps_code"
                        and arguments.get("tool") == "hub_get_source"
                        and result is not None
                        and self._tool_succeeded(result)
                    ):
                        method_packet = source_chunks.observe(
                            result.data, arguments,
                        )
                        if method_packet:
                            messages.append({
                                "role": "user", "content": method_packet,
                            })
                            increment_active_metric(
                                "source_method_projection_added"
                            )
                if history_reasoning_bypass and not investigative_history_bypass:
                    if temporal_history_answer_ready:
                        round_history_evidence_sufficient = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST HISTORY-SYNTHESIS HINT\n"
                            "The successful device-history result is evidence, not the "
                            "finished answer. Answer the user's original question "
                            "directly from the current-turn history evidence. When "
                            "temporalAnalysis is present, use its pre-computed interval "
                            "and reliability fields instead of redoing timestamp "
                            "arithmetic yourself. Treat durationReliability="
                            "unverified-event-stream or sourceIntegrityVerified=false "
                            "as an estimate only: do not call it exact, continuous, or "
                            "a mathematical lower bound. Do not call unrelated context "
                            "tools merely to be thorough. State changes do not prove "
                            "which automation or person caused them."
                        ),
                    })
                elif history_reasoning_bypass and investigative_history_bypass:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST INVESTIGATIVE-HISTORY REQUIREMENT\n"
                            "The user asked for analysis beyond a duration/event list. "
                            "Use the recorded rows to identify concrete patterns, but "
                            "keep observation separate from interpretation. Gather "
                            "additional evidence by quality, not by exhaustiveness: "
                            "(1) direct provenance/log evidence, when available; "
                            "(2) rule/app state or app event history tied to the subject; "
                            "(3) location/mode events close to the subject transition; "
                            "(4) same-room controller/button/remote event history when "
                            "the room discovery result exposes controller candidates; "
                            "(5) a small number of materially relevant environmental "
                            "sensor histories. For why/cause/trigger questions, prefer "
                            "controller events such as pushed, held, released, or "
                            "doubleTapped over motion/illuminance when both are available, "
                            "because an aligned control event is closer to direct provenance. "
                            "When checking any related device with multiple capabilities, "
                            "request the specific history attribute you intend to reason "
                            "about; generic device history is not evidence "
                            "that an omitted attribute had no events. Prefer a stronger "
                            "source over several weaker correlations and stop once the "
                            "available evidence "
                            "can support a bounded conclusion. If a needed gateway "
                            "sub-tool is not already established by the declared schema "
                            "or discovery result, use hub_search_tools for that exact "
                            "operation instead of guessing a gateway. For a why/cause/trigger "
                            "question, device history proves what changed but not the "
                            "cause; do not attribute a cause without direct or materially "
                            "corroborating current-turn evidence. For normal/abnormal/"
                            "expected/unusual wording, do not invent a generic notion "
                            "of normality: describe objective patterns that stand out, "
                            "and say a baseline or explicit expected rule is needed for "
                            "a stronger normality judgement. For comparison/correlation, "
                            "obtain the other requested side of the comparison. Avoid "
                            "room-wide or whole-hub evidence sweeps merely to be "
                            "thorough. Any unverified-event-stream duration remains an "
                            "estimate, not an exact total or proof of continuity."
                        ),
                    })
                if name == _LOCAL_FILTER_TOOL and not post_filter_discovery_used:
                    search_tool = catalog.declared_tool(SEARCH_TOOL)
                    if search_tool is not None:
                        post_filter_discovery_used = True
                        messages.append({
                            "role": "user",
                            "content": (
                                "HOST POST-FILTER DISCOVERY RESULT\n"
                                f"{capability_discovery}\n"
                                "The local filter was an intermediate read, not proof that "
                                "the original request is complete. Use any newly declared "
                                "gateway needed to finish the original task."
                            ),
                        })
            # Feed newly recovered journal evidence into the SAME model
            # investigation, rather than first discovering it after answer
            # generation. Following rounds retain the model's own read choice.
            if investigative_request and round_actions:
                await self._recover_journal_into_discovery(
                    user_prompt, messages)
            # Source-led device investigation: once real contiguous code,
            # device configuration, scoped history and logs are collected,
            # stop model-driven duplicate page reads and synthesize once.
            # This asserts tool-read sufficiency, NOT source method behaviour
            # or causal verification. Writes never enter this route.
            if (
                not round_has_mutation
                and source_trace_ready_for_synthesis(
                    user_prompt, self.evidence.receipts(),
                )
            ):
                increment_active_metric("source_trace_sufficiency_stop")
                increment_active_metric("investigative_finalization")
                return await self._final_answer(messages)

            if (causal_subject_no_intervals
                    and not is_connectivity_root_cause_request(user_prompt)):
                increment_active_metric("causal_subject_empty_stop")
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CAUSAL SUBJECT EVIDENCE STOP\n"
                        "The current-turn subject history did not establish any "
                        "bounded active interval in the requested window. Do not "
                        "expand to controller, sensor, location, app, rule, or log "
                        "evidence to reconstruct an older or hypothetical causal "
                        "timeline. Finalize from CURRENT-TURN evidence only. State "
                        "that no bounded subject interval was established and that "
                        "an unverified/incomplete event stream does not prove the "
                        "device stayed inactive."
                    ),
                })
                return await self._final_answer(messages)

            if (
                causal_subject_to_expand is not None
                and not causal_subject_evidence_expanded
            ):
                requested_transition = switch_transition_from_prompt(user_prompt)
                if requested_transition in {"on", "off"}:
                    current_evidence = self.evidence.receipts()
                    requested_boundary = prompt_focal_transition_boundary(
                        current_evidence,
                        requested_transition,
                        user_prompt,
                    )
                    command_correlations = correlate_command_producers(
                        current_evidence
                    )
                    if command_producer_transition_sufficient(
                        command_correlations,
                        requested_transition,
                        requested_boundary=requested_boundary,
                    ):
                        increment_active_metric(
                            "causal_command_producer_provenance"
                        )
                        deterministic_command_answer = (
                            render_command_producer_summary(
                                current_evidence,
                                transition=requested_transition,
                            )
                            if self.causal_deterministic_final_enabled
                            else None
                        )
                        if deterministic_command_answer:
                            deterministic_command_answer = await self._lighting_rule_decision_followup(
                                deterministic_command_answer,
                                transition=requested_transition,
                            )
                            increment_active_metric(
                                "causal_deterministic_finalization"
                            )
                            increment_active_metric("investigative_finalization")
                            return deterministic_command_answer
                        instruction = render_command_producer_evidence(
                            command_correlations
                        )
                        if instruction:
                            messages.append({
                                "role": "user",
                                "content": instruction,
                            })

                causal_subject_evidence_expanded = (
                    await self._expand_causal_subject_evidence(
                        causal_subject_to_expand,
                        catalog=catalog,
                        completed_calls=completed_calls,
                        messages=messages,
                    )
                )
                if native_log_causal_provenance_sufficient(
                    correlate_native_log_boundaries(
                        self.evidence.receipts()
                    )
                ):
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

                if not causal_completion_retry_used:
                    # Once the subject has real transitions, all stable
                    # subject-adjacent evidence is gathered host-side. Never
                    # reopen the unrestricted general tool loop: move directly
                    # into one constrained provenance-selection round.
                    followup = render_command_source_followup(
                        self.evidence.receipts()
                    ) or (
                        "HOST BOUNDED CAUSAL PROVENANCE PHASE\n"
                        "Observed subject transitions are established and the "
                        "fixed controller/location evidence layer is complete. "
                        "Choose only the materially strongest installed read-only "
                        "log/rule/app provenance source(s) from the tools now "
                        "declared. Do not search for device/sensor context and do "
                        "not request mutations. After this one tool round, the "
                        "host will synthesize from the complete current-turn "
                        "evidence."
                    )
                    causal_completion_retry_used = True
                    causal_completion_mode = True
                    increment_active_metric("causal_completion_retry")
                    messages.append({"role": "user", "content": followup})
                    continue

            if causal_completion_mode:
                # Installed provenance gateways are offered directly. As soon as
                # the bounded completion round attempts a provenance read,
                # synthesize from what it returned instead of opening another
                # exploratory round. Search remains only a sparse-registry
                # compatibility fallback.
                completion_read_attempted = any(
                    name != SEARCH_TOOL
                    for name, _arguments in round_actions
                )
                if completion_read_attempted:
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

            if duplicate_signature_seen:
                if (diagnostic_objective and inventory_without_investigation(
                    user_prompt, self.evidence.receipts()
                )):
                    increment_active_metric("investigation_inventory_only_stopped")
                    return honest_partial_answer(
                        user_prompt, self.evidence.receipts()
                    )
                return await self._final_answer(messages)
            if (
                round_history_evidence_sufficient
                and not round_has_mutation
                and not round_tool_failure
            ):
                # The model already chose the complete native tool round for this
                # step. If that round produced a successful deterministic temporal
                # history and the request is not investigative, the history evidence is
                # sufficient for synthesis. Execute every call the model requested
                # in the round, then stop tool expansion instead of letting a later
                # round wander into location/motion/rule reads merely for context.
                increment_active_metric("evidence_sufficiency_stop")
                return await self._final_answer(messages)
        if active_round_budget < self.max_tool_rounds:
            increment_active_metric("causal_read_round_budget_exhausted")
        logger.warning("Agent reached tool-round limit after %.3fs", time.monotonic() - request_started)
        if ungrounded_confirmation_claim_seen:
            return (
                "No Hubitat action was queued or executed because the model did not "
                "submit a complete structured action group. Please retry the original "
                "request."
            )
        if last_proposal_error is not None:
            _name, _rejected_arguments, reason = last_proposal_error
            increment_active_metric("proposal_validation_failures")
            return (
                "No Hubitat action was queued or executed because Rule Machine "
                f"proposal validation failed. Exact reason: {reason} "
                "The rejected gateway payload is withheld from this reply."
            )
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent", "_controller_followup_arguments"]
