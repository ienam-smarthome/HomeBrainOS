from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from automation_diagnostic_policy import (
    is_automation_runtime_diagnostic,
    is_integration_runtime_diagnostic,
)
from causal_native_logs import (
    correlate_native_log_boundaries,
    render_native_log_correlation,
)
from causal_timeline import render_causal_timeline, explicitly_focused_event_rows
from evidence_ledger import build_current_turn_evidence_ledger
from causal_answer_plan import render_causal_answer_plan
from motion_lockout_investigation import is_motion_lockout_investigation
from unified_investigation_bridge import unified_investigation_instruction
from causal_evidence_graph import (
    build_causal_evidence_graph,
    render_causal_evidence_graph,
    supports_one_pass_deep_synthesis,
)
from investigation_policy import (
    is_causal_investigation,
    is_history_investigation,
)
from investigation_intelligence import plan_investigation, render_investigation_assessment
from performance_host_plan import is_scheduler_only_evidence_request
from performance_causality_guard import performance_validation_needed
from performance_evidence_first import build_performance_synthesis_contract
from reasoning_policy import FINAL_SYNTHESIS_INSTRUCTION
from adaptive_investigation_policy import source_evidence_request
from source_evidence_metadata import contiguous_source_coverage
from request_metrics import increment_active_metric
from synthesis_context import build_tool_evidence_packet
from skill_investigation import render_skill_investigation
from skill_grounded_answer import render_grounded_causal_answer
from synthesis_validator import validate_synthesis
from investigation_objective import resolve_primary_objective
from ai_investigation_routing import active_request_interpretation
from device_incident_depth import is_connectivity_root_cause_request
from source_analysis_completion import source_answer_focus
from analytical_answer_quality import (
    QUESTION_FIRST_CONTRACT, answer_quality_issues,
    quality_repair_instruction,
)
from causal_fail_closed_summary import render_failed_causal_synthesis


FINAL_ANSWER_INSTRUCTION = FINAL_SYNTHESIS_INSTRUCTION
DEFAULT_FINAL_ANSWER = "The MCP request completed without a written answer."
_PERFORMANCE_TOOL = "hub_get_performance_stats"
_LOG_TOOL = "hub_get_logs"


def _original_user_request(messages: list[dict[str, Any]]) -> str:
    """Return the most recent non-host user objective."""

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if not content or content.lstrip().startswith("HOST "):
            continue
        return content
    return ""


def _current_turn_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return system context plus messages from the latest real user turn onward.

    Conversation history remains useful during tool selection, especially for
    follow-up requests. It is not evidence. Final investigative synthesis must not
    see a previous assistant conclusion as if it were a current-turn observation.
    """

    current_user_index: int | None = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if not content or content.lstrip().startswith("HOST "):
            continue
        current_user_index = index
        break

    if current_user_index is None:
        return [dict(message) for message in messages if isinstance(message, dict)]

    system_messages = [
        dict(message)
        for message in messages[:current_user_index]
        if isinstance(message, dict) and message.get("role") == "system"
    ]
    current = [
        dict(message)
        for message in messages[current_user_index:]
        if isinstance(message, dict)
    ]
    return [*system_messages, *current]


def _performance_evidence_only_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop untrusted assistant prose while preserving native tool-call envelopes.

    The production performance API performs an early provider pass to choose/read
    tools and later performs one evidence-scoped synthesis pass. Feeding the prose
    draft from that early pass back into final synthesis primes the final model with
    unsupported mechanisms and recommendations. Tool-call assistant messages remain
    because their matching tool messages require the native envelope; prose-only
    assistant conclusions are context, not evidence, and are excluded.
    """

    filtered: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            filtered.append(dict(message))
            continue
        calls = message.get("tool_calls")
        if isinstance(calls, list) and calls:
            filtered.append(dict(message))
    return filtered


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _successful_evidence(evidence: list[dict[str, Any]], sub_tool: str) -> bool:
    return any(
        isinstance(row, dict)
        and row.get("success") is not False
        and _sub_tool(row) == sub_tool
        for row in evidence
    )


def _performance_semantic_validation_needed(evidence: list[dict[str, Any]]) -> bool:
    """Performance semantics must be guarded even when the log read failed."""

    return _successful_evidence(evidence, _PERFORMANCE_TOOL)


def _broad_performance_recommendation_request(text: str) -> bool:
    """Conservative request classifier for the mandatory recent-log breadth path."""

    folded = " ".join(str(text or "").casefold().split())
    performance = any(
        token in folded
        for token in (
            "performance",
            "slow hub",
            "hub load",
            "resource consumer",
            "resource consumers",
            "optimisation",
            "optimization",
        )
    )
    recommendations = any(
        token in folded
        for token in (
            "recommend",
            "improve",
            "improvement",
            "optimise",
            "optimize",
            "what else can be improved",
        )
    )
    return performance and recommendations


def _synthesis_instruction(original_user: str, *, focused_event: bool = False) -> str:
    """Build the shared final reasoning contract from request class."""

    causal = is_causal_investigation(original_user)
    plan = plan_investigation(original_user)
    # The shared investigation goal is the authoritative intent classifier
    # across collection AND final synthesis; a narrower history regex should
    # not return generic synthesis for the same recognised investigation.
    investigative = is_history_investigation(original_user) or plan is not None
    lockout_goal = plan is not None and plan.domain == "manual_motion_lockout"
    # The user asked about one focal OFF/lockout, not daily device-usage
    # durations. Treating every duration phrase as a request for all-day
    # interval tables leads to repetitive, irrelevant material.
    if lockout_goal:
        focused_event = True
    if not investigative:
        return FINAL_SYNTHESIS_INSTRUCTION

    text = (
        "Answer the ORIGINAL user request now using only CURRENT-TURN MCP evidence. "
        "Do not request another tool and do not answer a narrower substitute "
        "question merely because one source is easy to summarize. "
    )
    if causal:
        text += (
            "This is a causal investigation. Lead with the best-supported "
            "explanation and calibrate confidence. Reconstruct the important "
            "timeline by correlating timestamps across sources. "
            + (
                "The user identified one specific recorded event. Analyse that "
                "event only; do not require a full-day table or describe other "
                "intervals as unexplained unless asked. "
                if focused_event else
                "Account for every MATERIAL row in the HOST CAUSAL TIMELINE; "
                "adjacent short minor unresolved rows may be grouped, but do "
                "not omit a material interval with aligned provenance. "
            )
            + "Separate a likely trigger/provenance event "
            "from downstream automation effects. A controller event aligned to an "
            "interval END is end/turn-off-adjacent evidence and must not be cited "
            "as the cause of that interval's earlier turn-on. If an OPEN timeline "
            "row exists, mention the recorded active transition and that no closing "
            "transition was observed; do not infer a duration from it. Explain what "
            "remains unproven or unexplained. Only suggest a configuration change "
            "when the evidence makes it relevant. A device state transition or "
            "close timestamp alone is correlation, not proof of a person or "
            "automation causing it. App/rule configuration proves only that an automation "
            "is configured or capable of managing the device; configuration alone "
            "must never be described as the most likely trigger for a specific "
            "transition. Require controller timing, execution/log provenance, or "
            "other direct current-turn evidence before naming an initiating source. "
            "Distinguish the command producer from the upstream initiator: an "
            "app-issued command does not, by itself, rule out manual input "
            "to that app or an external controller. Exclude an alternative "
            "only if evidence actually checks it; otherwise say it was not "
            "identified as the immediate command producer. A successful app "
            "log query with zero entries establishes an empty searched window, "
            "not disabled debug logging or a missing source. Cite settings "
            "such as debugLogging only when returned configuration actually "
            "shows them. For an observed bounded focal ON run, use its recorded "
            "integer durationSeconds without adding a second by rounding. "
            "When HOST NATIVE-LOG BOUNDARY CORRELATION shows the same physical "
            "controller/input immediately preceding both the subject ON command "
            "and later OFF command, present that repeated controller/input as the "
            "strongest initiating-control candidate rather than dismissing it as "
            "an unrelated coincidence. Keep the explicit caveat that repeated "
            "timestamp correlation does not independently prove the configured "
            "button-to-device mapping. An observed OFF state immediately after "
            "sensor inactivity is not proof that the same app issued an OFF "
            "command or that its configured inactivity timer executed. If "
            "the structured causal graph lacks an OFF-command source, call "
            "the OFF linkage temporally consistent only and keep its actor "
            "unverified. A Hubitat event's triggered[] list names "
            "listeners invoked by that state event; if the event is physical and "
            "producedBy names a bridge/device, an app appearing only in triggered[] "
            "must be described as downstream, never as the initiating trigger. "
            "If an app reaction appears only after the subject command, describe "
            "it as downstream handling, not initiation. The actor of any claimed "
            "setLevel/brightness action must match that command's own producedBy "
            "app identity, not a different app merely present as a listener. "
            "An empty event-time app log cannot confirm that no internal rule "
            "logic executed or initiated an action; it means no entries were "
            "returned for the searched window. Preserve signed timestamps: "
            "when one occupancy sensor became inactive before OFF and another "
            "after OFF, state their individual order, never collapse both into "
            "one earlier sensor event. A bounded ON interval contains two "
            "independently investigated transitions. Use the separate ON and "
            "OFF objects in transitionEvidence: OFF requires its own compatible "
            "command producer, scoped app logs, potential sensor inputs and "
            "uncertainty. A sensor reporting inactive milliseconds before OFF "
            "does not establish the OFF trigger or execution of a configured "
            "inactivity timer. Even if the same app handled ON, do not transfer "
            "its command ownership or initiating logic to OFF. A successful "
            "zero-row command-off history lookup is a bounded negative "
            "observation, not proof that the bridge or an external automation "
            "could not switch the light off. Keep an unknown OFF actor unknown. "
        )
    elif investigative:
        text += (
            "This is an analytical history request. Compare the relevant evidence "
            "classes directly, preserve objective patterns and uncertainty, and do "
            "not invent a causal explanation or normality baseline that the "
            "current-turn evidence does not establish. "
        )
    if lockout_goal:
        text += (
            "Reconcile three independent stages: issued command, textual "
            "app decision declaration, and observed suppression of an "
            "eligible activation. A log declaration alone can substantiate "
            "that a decision was REPORTED, but does not establish effective "
            "suppression of a later motion-triggered ON; and backend-filter "
            "only provenance is not independent per-row source verification. "
            "If the user-specified duration and source-reported duration "
            "conflict, quote both with their original units and distinguish "
            "them from verified configuration. Focus on the focal lockout "
            "and its evidence; don't add daily light-on interval tables "
            "unless requested. "
        )
    text += (
        "Synthesize rather than dump raw fields. For unverified device-event "
        "streams, describe durations/counts as recorded-event estimates rather "
        "than exact physical history. A timestamp present in a returned event row "
        "is itself a recorded observation, not an estimated timestamp; source "
        "integrity uncertainty applies to completeness and continuity. If the "
        "original user explicitly asks how long, for a duration, or for total time, "
        "lead with the deterministic temporal duration when current-turn evidence "
        "provides it. "
        + (
            "Present the requested focal event in plain language rather than "
            "reporting whole-day totals or unrelated historical intervals. "
            if focused_event else
            "When several bounded intervals are available, prefer a compact "
            "Markdown table with start state/time, end state/time, and duration. "
        )
        + "When the retained page reaches the requested window start, avoid routine "
        "boilerplate about an unverified event stream if the duration is already "
        "qualified as about/estimated; instead add one short practical context sentence "
        "covering the window start and latest recorded state/event. Say a device is "
        "currently on/off only when separate current-turn live-state evidence supports "
        "that claim; otherwise say latest recorded state. When retained history is known "
        "not to reach the requested window start, keep an explicit missing-history "
        "warning. Do not dump raw JSON fields. Preserve useful supported analysis instead "
        "of reducing the answer to a duration or event list. "
        "Be concise but complete and do not reveal hidden reasoning."
    )
    return text


class FinalAnswerCoordinator:
    """Own the single no-tools reasoning/synthesis path for every agent layer.

    Investigation gathers evidence; this coordinator converts that evidence into
    one model-authored answer, then uses deterministic guards only as validators.
    The production wrapper and base orchestrator intentionally share this class so
    their final-answer behavior cannot diverge.
    """

    def __init__(
        self,
        chat: Callable[
            [list[dict[str, Any]], list[dict[str, Any]]],
            Awaitable[dict[str, Any]],
        ],
        evidence_supplier: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._chat = chat
        self._evidence_supplier = evidence_supplier

    async def _ensure_broad_performance_logs(
        self,
        original_user: str,
        evidence: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Host-enforce one bounded recent-log read before broad performance synthesis.

        This deliberately runs after performance evidence exists and before the
        no-more-tools synthesis round. It does not depend on the model selecting the
        correct gateway. The production chat callable is a bound agent method, so the
        same request-scoped executor/evidence recorder remains authoritative here.
        """

        if is_scheduler_only_evidence_request(original_user):
            return evidence
        if not _broad_performance_recommendation_request(original_user):
            return evidence
        if not _successful_evidence(evidence, _PERFORMANCE_TOOL):
            return evidence
        if _successful_evidence(evidence, _LOG_TOOL):
            return evidence

        agent = getattr(self._chat, "__self__", None)
        executor = getattr(agent, "executor", None)
        if executor is None:
            messages.append({
                "role": "user",
                "content": (
                    "HOST BROAD PERFORMANCE LOG STATUS\n"
                    "The required bounded recent-log read could not be executed by the host. "
                    "State this limitation explicitly and do not present the analysis as log-complete."
                ),
            })
            increment_active_metric("broad_performance_log_host_unavailable")
            return evidence

        increment_active_metric("broad_performance_log_host_attempt")
        attempts = (
            "hub_manage_logs",
            "hub_read_diagnostics",
        )
        successful_content = ""
        for gateway in attempts:
            execution = await executor.execute(
                gateway,
                {
                    "tool": _LOG_TOOL,
                    "args": {"since": "30m", "limit": 100},
                },
                supports_live_claim=True,
                evidence_kind="authoritative_recent_performance_logs",
            )
            if execution.success and execution.result is not None:
                successful_content = execution.content
                increment_active_metric("broad_performance_log_host_success")
                break
            increment_active_metric("broad_performance_log_host_retry")

        refreshed = (
            list(self._evidence_supplier() or [])
            if self._evidence_supplier is not None
            else evidence
        )
        if successful_content and _successful_evidence(refreshed, _LOG_TOOL):
            messages.append({
                "role": "user",
                "content": (
                    "HOST BROAD PERFORMANCE LOG READ\n"
                    "A bounded recent Hubitat log window was read host-side specifically for this "
                    "performance analysis. Treat it as current observations, not automatic causation:\n"
                    + successful_content
                ),
            })
            return refreshed

        messages.append({
            "role": "user",
            "content": (
                "HOST BROAD PERFORMANCE LOG STATUS\n"
                "The required bounded recent-log read was attempted host-side but did not succeed. "
                "State this limitation explicitly and do not present the analysis as log-complete."
            ),
        })
        increment_active_metric("broad_performance_log_host_failed")
        return refreshed

    async def _revise_incomplete_answer(
        self,
        original_user: str,
        draft: str,
        evidence: list[dict[str, Any]],
        final_messages: list[dict[str, Any]],
        *,
        causal: bool,
    ) -> str:
        """One evidence-scoped, no-tools repair for unanswered analytical goals.

        The ordinary synthesis validator is authoritative for factual claims;
        quality assessment does not relax it or invent a verified source.
        """
        issues = answer_quality_issues(original_user, draft, evidence)
        if not issues:
            return draft
        increment_active_metric("answer_quality_gaps_found")
        revision_messages = [
            *final_messages,
            {"role": "assistant", "content": draft},
            {"role": "user", "content": quality_repair_instruction(issues)},
        ]
        increment_active_metric("answer_quality_revision_rounds")
        revised = await self._chat(revision_messages, [])
        content = str(revised.get("content") or "").strip()
        if not content:
            increment_active_metric("answer_quality_revision_rejected")
            return draft
        corrected, factual_issues = validate_synthesis(
            content, evidence, original_user=original_user, causal=causal,
        )
        if factual_issues:
            # A more fluent but factually unsupported answer is a regression.
            # Return the previously validated answer, not a speculative repair.
            increment_active_metric("answer_quality_revision_rejected")
            return draft
        # A revision may legitimately state "unknown"; do not force extra
        # rounds. Nonetheless, a still-unanswered question gains no value.
        if answer_quality_issues(original_user, content, evidence):
            increment_active_metric("answer_quality_revision_incomplete")
            return draft
        increment_active_metric("answer_quality_revision_accepted")
        return content

    async def answer(self, messages: list[dict[str, Any]]) -> str:
        evidence = (
            list(self._evidence_supplier() or [])
            if self._evidence_supplier is not None
            else []
        )
        original_user = _original_user_request(messages)
        objective = resolve_primary_objective(original_user)
        interpreted = active_request_interpretation(original_user)
        interpreted_kind = interpreted.objective if interpreted else None
        contract = (
            None if objective.is_source else plan_investigation(original_user)
        )
        if not objective.is_source:
            evidence = await self._ensure_broad_performance_logs(
                original_user, evidence, messages,
            )
        # A Groovy method causing expensive app execution is not a historic
        # device ON/OFF causal investigation. Preserve its code-level question
        # and source evidence across final synthesis.
        causal = (
            not objective.is_source
            and not is_connectivity_root_cause_request(original_user)
            and (interpreted_kind is None
                 or interpreted_kind == "historical_command")
            and is_causal_investigation(original_user)
        )
        lockout_request = (
            (interpreted_kind is None or interpreted_kind == "historical_command")
            and is_motion_lockout_investigation(original_user)
        )
        investigative = (
            lockout_request
            or is_history_investigation(original_user)
            or is_automation_runtime_diagnostic(original_user)
            or is_integration_runtime_diagnostic(original_user)
        )
        performance_semantic_validation = (
            not objective.is_source
            and _performance_semantic_validation_needed(evidence)
        )
        performance_log_validation = (
            not objective.is_source
            and performance_validation_needed(evidence)
        )
        evidence_scoped = (
            objective.is_source or investigative
            or performance_semantic_validation or contract is not None
        )
        current_turn = _current_turn_messages(messages)
        if performance_semantic_validation:
            current_turn = _performance_evidence_only_messages(current_turn)
        brief = build_current_turn_evidence_ledger(evidence)
        focused_event = bool(
            explicitly_focused_event_rows(evidence, original_user)
        ) if causal else False
        causal_timeline = (
            render_causal_timeline(evidence, original_user=original_user)
            if causal else None
        )
        causal_graph = (
            build_causal_evidence_graph(evidence, original_user)
            if causal else {}
        )
        # A source-ranked causal conclusion is a decision from typed receipts,
        # not text that a model can override by choosing different wording.
        # Only use this direct path for an exact focal ON event with a recorded
        # preceding command but no established upstream causal chain.
        if (
            causal
            and (investigative or contract is not None)
            and causal_graph.get("scope") == "single-observed-event"
            and not causal_graph.get("ready")
            and not causal_graph.get("physicalEvidenceComplete")
        ):
            grounded_answer = render_grounded_causal_answer(
                evidence, original_user,
            )
            if grounded_answer:
                increment_active_metric("skills_grounded_answer_selected")
                return grounded_answer
        causal_graph_brief = (
            render_causal_evidence_graph(evidence, original_user)
            if causal_graph.get("scope") == "single-observed-event"
            else None
        )
        causal_answer_plan = (
            render_causal_answer_plan(causal_graph, original_user)
            if causal_graph.get("scope") == "single-observed-event"
            else None
        )
        skill_investigation = (
            render_skill_investigation(evidence, original_user)
            if causal else None
        )
        native_log_correlation = (
            render_native_log_correlation(
                correlate_native_log_boundaries(evidence)
            )
            if causal
            else None
        )
        tool_packet = (
            build_tool_evidence_packet(current_turn)
            if evidence_scoped
            else None
        )

        # Final evidence-heavy synthesis is scoped to this request. Prior
        # conversation remains available to earlier reasoning/tool selection but is
        # intentionally excluded here so an old conclusion cannot become evidence.
        final_messages = [*current_turn] if evidence_scoped else [*messages]
        if brief:
            final_messages.append({"role": "user", "content": brief})
        if causal_timeline:
            final_messages.append({"role": "user", "content": causal_timeline})
        if causal_graph_brief:
            final_messages.append({"role": "user", "content": causal_graph_brief})
        # Consolidated path: original agent authors an unrestricted natural
        # explanation using independently attested source relationships from
        # V2's reusable projection primitives. No second V2 planner, forced
        # final JSON, claims catalog or host-executed source reads.
        unified_brief = (
            unified_investigation_instruction(evidence, original_user)
            if evidence_scoped and not objective.is_source else None
        )
        if unified_brief:
            final_messages.append({"role": "user", "content": unified_brief})
            increment_active_metric("unified_investigation_evidence_bridge")
        if lockout_request:
            lockout_rows = [
                row.get("details") or {}
                for row in evidence
                if row.get("tool") == "homebrain_motion_lockout_investigation"
            ]
            final_messages.append({
                "role": "user",
                "content": (
                    "TEMPORAL LOCKOUT EVIDENCE CONTRACT: The task is to "
                    "investigate a historical manual-OFF, motion and "
                    "three-minute inhibition sequence, NOT to describe "
                    "present device health or Rule Machine required expressions. "
                    "Report the selected OFF timestamp and whether its manual "
                    "source was verified, contemporaneous button and motion "
                    "observations, subsequent light ON/OFF observations, "
                    "bounded app-log results and gaps, and separately label "
                    "whether a lockout execution or failure was proven. "
                    "Absence of light ON and current 'lockout inactive' status "
                    "cannot establish past lockout activation. If any essential "
                    "event stream is unavailable, explicitly state which "
                    "verification is still needed. "
                    + ("Focal sequence status: " + str(
                        lockout_rows[-1].get("status")
                    ) if lockout_rows else
                       "No historical sequence evidence receipt was available.")
                ),
            })
        if causal_answer_plan:
            # Highest-priority causal synthesis guidance: typed precomputed
            # relationships before the model authors its one final answer.
            final_messages.append({"role": "user", "content": causal_answer_plan})
        if skill_investigation:
            final_messages.append({
                "role": "user", "content": skill_investigation,
            })
        if native_log_correlation:
            final_messages.append({
                "role": "user",
                "content": native_log_correlation,
            })
        if tool_packet:
            final_messages.append({"role": "user", "content": tool_packet})
        if performance_semantic_validation:
            final_messages.append({
                "role": "user",
                "content": build_performance_synthesis_contract(evidence),
            })
        if contract is not None:
            final_messages.append({
                "role": "user",
                "content": render_investigation_assessment(contract, evidence),
            })
        if evidence_scoped and evidence:
            # Shared quality contract complements, but never replaces, the
            # receipt-based factual validator or domain-specific guards.
            final_messages.append({
                "role": "user", "content": QUESTION_FIRST_CONTRACT,
            })
        if objective.is_source or source_evidence_request(original_user):
            spans = contiguous_source_coverage(evidence)
            final_messages.append({
                "role": "user",
                "content": (
                    "HOST SOURCE ANALYSIS FINALISATION (no tool calls allowed): "
                    "The user requested explanation of the actual driver "
                    "implementation and correlation with observations. "
                    + (
                        "Full contiguous source-offset coverage has been verified. "
                        if spans.get("fullImplementationVerified") else
                        "Only partial or unverified source coverage is available. "
                    )
                    + "Source retrieval alone is not code-path review. "
                      "Explain only those methods and branches that appear "
                      "in the source text present in this current-turn transcript. "
                      "Tie specific driver operations to scoped logs/events "
                      "when the connection is supported. Explicitly distinguish "
                      "the driver's MQTT client session from the physical "
                      "endpoint ONLY if the source establishes that distinction. "
                      "If exact getter/write/watchdog methods were not examined, "
                      "name the missing analysis; do not invent it. "
                      "When a HOST SOURCE-DERIVED METHOD EVIDENCE packet "
                      "is present, prioritize its line-numbered candidate "
                      "method bodies over a truncated raw MCP tool-result "
                      "prefix. State which specific method bodies support "
                      "each implementation claim and which relevant bodies "
                      "were not shown in full. Do not treat an unknown "
                      "method body as absent merely because it was omitted "
                      "from the bounded excerpt. There are NO tools in "
                      "this final phase, so do not request another function "
                      "or complain about missing structured actions. "
                      "Produce a useful read-only evidence-qualified "
                      "explanation now."
                ),
            })
        if objective.is_source:
            final_messages.append({
                "role": "user",
                "content": (
                    "PRIMARY INVESTIGATION OBJECTIVE — GROOVY SOURCE. "
                    f"Installed app ID: {objective.installed_app_id}. "
                    + (
                        f"Explicit method: {objective.method_symbol}. "
                        if objective.method_symbol else ""
                    )
                    + "Inspect the requested method's real source excerpt and "
                    "possible callers before attributing any cause. "
                    "Relate measured app runtimes and device-originated "
                    "LimitExceededException records to specific supported "
                    "code-path hypotheses. A load exception is not a historic "
                    "device ON/OFF command. A Hubitat exception explicitly "
                    "stating 'generates excessive hub load' is NOT evidence "
                    "by itself of Zigbee/Z-Wave packet overflow, reportText "
                    "character limits or a device buffer error. Do not infer "
                    "a transport or command timeout merely from averageMs. "
                    "If the code calls a method on a device reference, "
                    "distinguish the app's verified call site from a driver "
                    "method body, and do not claim the reference resolves to "
                    "a specific device ID without typed configuration. "
                    "Do not switch to Rule Machine "
                    "trigger/action-tree review or generic performance rankings. "
                    "If relevant method/caller excerpts are unavailable or "
                    "runtime execution cannot be linked, explain the gap and "
                    "give the next read-only verification step. "
                    "The current-turn source excerpts—not the configured "
                    "model's assumptions—are the only code evidence."
                ),
            })
        if interpreted_kind is not None:
            final_messages.append({
                "role": "user",
                "content": (
                    "INTERPRETED ORIGINAL USER OBJECTIVE (request-scoped): "
                    + interpreted_kind + ". "
                    "Keep the final answer within the original question's "
                    "goal. A mention of an automation is not permission to "
                    "design new rules; a connectivity fault is not proof of "
                    "a historical ON/OFF command. If the available evidence "
                    "does not establish causation, say what is missing. "
                    "Do not replace the task with an unrelated workflow."
                ),
            })
        if is_connectivity_root_cause_request(original_user):
            final_messages.append({
                "role": "user",
                "content": (
                    "PRIMARY OBJECTIVE: investigate the target device's "
                    "offline/connected-MQTT and stale-telemetry contradiction, "
                    "NOT Rule Machine authoring, lighting, sensor-motion "
                    "lockouts, or reconstruction of an ON/OFF command unless "
                    "verified relevant to this device's connectivity. "
                    "Do not include a Rule design feasibility gate, a "
                    "new-rule proposal, cross-midnight OFF design or unrelated "
                    "time-window advice. The checked device attributes, "
                    "watchdog age and lastSeen refer to different reported "
                    "clocks; explain these conflicts without equating any "
                    "cached value to physical telemetry. If no driver source "
                    "or broker evidence was retrieved, do NOT assert the "
                    "driver's internal MQTT semantics or a physical root "
                    "cause as proven. Give specific next safe read checks."
                ),
            })
        final_messages.append({
            "role": "user",
            "content": _synthesis_instruction(
                original_user, focused_event=focused_event
            ),
        })

        response = await self._chat(final_messages, [])
        draft = str(response.get("content") or DEFAULT_FINAL_ANSWER)
        if objective.is_source:
            focus = source_answer_focus(original_user, draft)
            if focus["required"] and not focus["satisfied"]:
                # One bounded, no-tools repair using the same current-turn
                # code evidence and the *original* objective. A vague
                # answer should not be declared resolved just because the
                # raw file was retrieved. Do not fabricate a method body.
                increment_active_metric("source_focus_repair_attempted")
                needs = ", ".join(focus["missing"])
                reminder = (
                    "SOURCE-OBJECTIVE REPAIR: the previous answer missed "
                    "required aspects of the user's original question: "
                    + needs + ". "
                    + (
                        "Address the explicit Groovy method "
                        + objective.method_symbol + " by name. "
                        if objective.method_symbol else ""
                    )
                    + "Use only the verified current-turn source excerpts. "
                    "Discuss supported code-path possibilities and which "
                    "runtime evidence is unavailable. If the method body was "
                    "not shown, say that explicitly; do not invent one. "
                    "Avoid Rule Machine and physical-device-history digressions. "
                    "Produce the requested read-only explanation or a clear "
                    "method-specific evidence gap."
                )
                repaired = await self._chat([
                    *final_messages,
                    {"role": "assistant", "content": draft},
                    {"role": "user", "content": reminder},
                ], [])
                revised = str(repaired.get("content") or "").strip()
                if revised and source_answer_focus(
                    original_user, revised
                )["satisfied"]:
                    draft = revised
                    increment_active_metric("source_focus_repair_satisfied")
                else:
                    increment_active_metric("source_focus_repair_unresolved")
        if not investigative and not performance_semantic_validation and contract is None:
            # Ordinary simple answers keep their established one-pass behavior.
            # Any answer containing measured performance statistics enters the
            # semantic validator even when a log call failed or was rejected.
            return draft

        corrected, issues = validate_synthesis(
            draft,
            evidence,
            original_user=original_user,
            causal=causal,
            **({"primary_objective": "source_code"} if objective.is_source else {}),
        )
        if not issues:
            # Existing causal/focal analyzers already enforce their own one-pass
            # or bounded specialized repairs. Avoid extra rounds for those paths.
            if contract is not None and not causal:
                return await self._revise_incomplete_answer(
                    original_user, draft, evidence, final_messages, causal=causal,
                )
            return draft

        # Fixed categories only: telemetry must not include private query
        # words, device names, event IDs or arbitrary validation issue text.
        increment_active_metric("synthesis_validation_issues", len(issues))

        # When a fully scoped event graph exists and every issue was already
        # corrected by an evidence-backed, localized deterministic guard,
        # another provider round can only repeat the evidence or reintroduce
        # the original error. Keep the corrected answer, not a new rewrite.
        deterministic_causal_repairs = {
            "focal_interval_duration", "upstream_manual_exclusion",
            "causal_source_attribution", "checked_source_consistency",
            "positive_source_attribution", "controller_boundary_direction",
            "triggered_listener_causal_attribution",
            "configuration_only_causal_attribution",
            "causal_controller_history_coverage",
            "causal_action_ownership", "causal_empty_log_inference",
            "causal_sensor_event_order", "causal_off_trigger_overclaim",
            "causal_off_certainty_contract", "off_hypothesis_summary",
            "causal_history_gap_claims",
            "causal_answer_claim_boundaries",
            "archived_sensor_not_absent",
            "archived_sensor_source_disclosure",
            "causal_on_button_initiation_not_proven",
            "unsupported_math_status_notation",
        }
        if (
            causal
            and (
                causal_graph.get("ready")
                or causal_graph.get("physicalEvidenceComplete")
                or supports_one_pass_deep_synthesis(causal_graph, original_user)
            )
            and set(issues).issubset(deterministic_causal_repairs)
        ):
            increment_active_metric("synthesis_localized_corrections")
            return corrected

        # Attribute every additional provider round to one coarse, stable
        # reason, rather than silently reporting model_rounds=2.
        if any(str(issue).startswith("causal_timeline_coverage") for issue in issues):
            increment_active_metric("synthesis_repair_causal_coverage")
        elif any(str(issue).startswith("performance") for issue in issues):
            increment_active_metric("synthesis_repair_performance")
        elif causal and any(
            issue in {
                "controller_boundary_direction", "triggered_listener_causal_attribution",
                "configuration_only_causal_attribution", "upstream_manual_exclusion",
                "causal_source_attribution", "causal_controller_history_coverage",
                "causal_action_ownership", "causal_empty_log_inference",
                "causal_sensor_event_order", "causal_off_trigger_overclaim",
                "causal_off_certainty_contract", "off_hypothesis_summary",
            "causal_history_gap_claims",
            }
            for issue in issues
        ):
            increment_active_metric("synthesis_repair_causal_provenance")
        else:
            increment_active_metric("synthesis_repair_other")

        performance_repair = ""
        if performance_semantic_validation:
            performance_repair = (
                " Performance semantic validation is fail-closed whenever current-turn "
                "performance statistics exist, even if a recent-log read failed. Keep "
                "measured performance facts separate from hypotheses and configuration "
                "prescriptions. Do not promote job counts into CPU/load attribution, do "
                "not describe database size qualitatively without an evidence-backed "
                "threshold, do not make backup severity/data-loss claims beyond the alert, "
                "and do not prescribe scheduler interval changes without configuration evidence."
            )
        if performance_log_validation:
            performance_repair += (
                " Recent logs are observations, not proof that a logged rule/device causes "
                "busy percentage, load, latency, or execution time without direct linking "
                "evidence. Do not infer threshold crossing/oscillation from repeated reports "
                "that all remain on the same qualifying side."
            )

        # Validators identify factual conflicts; they do not author the answer.
        # Give the model one no-tools repair pass so supported analysis and
        # uncertainty survive a localized correction.
        repair_messages = [
            *final_messages,
            {"role": "assistant", "content": draft},
            {
                "role": "user",
                "content": (
                    "HOST SYNTHESIS VALIDATION REPAIR\n"
                    f"Detected deterministic issues: {', '.join(issues)}.\n"
                    "Rewrite the draft answer, preserving every supported useful "
                    "explanation, timeline, and uncertainty statement while fixing "
                    "only the factual conflicts. Do not request tools."
                    + performance_repair
                    + " The following is a deterministic localized baseline showing "
                    "corrections that must be respected; it is NOT a replacement "
                    "answer:\n"
                    + corrected
                ),
            },
        ]
        increment_active_metric("synthesis_repair_rounds")
        repaired = await self._chat(repair_messages, [])
        repaired_content = str(repaired.get("content") or "").strip()
        if not repaired_content:
            increment_active_metric("synthesis_repair_failed")
            if causal:
                safe = render_failed_causal_synthesis(evidence, original_user)
                if safe is not None:
                    increment_active_metric("synthesis_causal_fail_closed")
                    return safe
            return corrected

        repaired_corrected, remaining = validate_synthesis(
            repaired_content,
            evidence,
            original_user=original_user,
            causal=causal,
            **({"primary_objective": "source_code"} if objective.is_source else {}),
        )
        if remaining:
            increment_active_metric("synthesis_repair_failed")
            if causal:
                # A failed source-bound repair must not return another
                # incompatible causal story merely because it now has
                # an appended partial-coverage warning.
                safe = render_failed_causal_synthesis(evidence, original_user)
                if safe is not None:
                    increment_active_metric("synthesis_causal_fail_closed")
                    return safe
        return repaired_content if not remaining else repaired_corrected


__all__ = [
    "DEFAULT_FINAL_ANSWER",
    "FINAL_ANSWER_INSTRUCTION",
    "FinalAnswerCoordinator",
    "_broad_performance_recommendation_request",
    "_current_turn_messages",
    "_original_user_request",
    "_performance_evidence_only_messages",
    "_performance_semantic_validation_needed",
    "_synthesis_instruction",
]
