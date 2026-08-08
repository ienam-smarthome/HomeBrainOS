from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from contact_history_queries import (
    HistoryReference,
    contact_events,
    events_in_window,
    find_after_reference,
    find_before_reference,
    parse_after_that,
    parse_before_that,
    parse_count_yesterday,
    parse_list_yesterday,
    present_count,
    present_yesterday_events,
    yesterday_bounds,
)
from contextual_read_fast_path import (
    capability_choice_labels,
    clean_choice_label,
    parse_bare_attribute,
    parse_contextual_attribute,
    parse_device_selection,
    parse_motion_activity,
    parse_named_attribute,
    present_attribute,
    present_motion_activity,
)
from confirmation_policy import ConfirmationAction
from deterministic_tool_presenter import present_tool_result
from device_query_service import DeviceQueryService
from direct_outcome_context import DirectOutcomeContext
from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import reset_grounding_policy_factory, set_grounding_policy_factory
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent
from natural_datetime import format_natural_datetime
from observed_agent_outcome import ObservedAgentOutcome
from request_classification import (
    parse_firmware_install_intent,
    parse_firmware_status_intent,
)
from request_metrics import RequestMetrics
from request_observation import RequestObservationCoordinator
from time_expressions import AT_TIME
from token_aware_context_policy import TokenAwareModelContextPolicy
from tool_registry import EVIDENCE_KINDS, LOCAL_HUB_INFO_TOOL


class UnifiedMCPAgent(BaseUnifiedMCPAgent):
    """Production agent with delegated synthesis, grounding, and observability."""

    _FOLLOW_UP_PRONOUN = re.compile(r"\b(?:it|its|that|this|which one|the one|one of them)\b", re.I)
    _LAST_CONTACT = re.compile(
        r"^\s*when\s+did\s+(?P<name>.+?)\s+last\s+(?P<state>open|close|closed)\s*[?.!]*\s*$",
        re.I,
    )
    _WHY_CONTACT = re.compile(
        r"^\s*why\s+did\s+(?P<name>.+?)\s+(?P<state>open|close|closed)(?:\s+.+?)?\s*[?.!]*\s*$",
        re.I,
    )
    _CHOICE_LIST = re.compile(
        r"(?:which device.*?:|possible matches:)\s*(?P<choices>.+?)[?.!]*$",
        re.I | re.S,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context_policy = TokenAwareModelContextPolicy(
            model_name=self.model_name,
            max_history_messages=self.context_policy.max_history_messages,
            max_history_chars=self.context_policy.max_history_chars,
            max_tool_context_chars=self.context_policy.max_tool_context_chars,
            compacted_tool_result_chars=self.context_policy.compacted_tool_result_chars,
        )
        self.max_history_messages = self.context_policy.max_history_messages
        self.max_history_chars = self.context_policy.max_history_chars
        self.max_tool_context_chars = self.context_policy.max_tool_context_chars
        self.compacted_tool_result_chars = self.context_policy.compacted_tool_result_chars
        self.final_answers = FinalAnswerCoordinator(self._chat)
        self.request_metrics = RequestMetrics()
        self.request_observation = RequestObservationCoordinator(self.request_metrics)
        self.direct_outcomes = DirectOutcomeContext(
            self.evidence,
            self._choices,
            self._mutation_call_seen,
            self._request_class,
        )
        self._clarification_choices: dict[str, list[str]] = {}
        self._selected_devices: dict[str, str] = {}
        self._history_references: dict[str, HistoryReference] = {}

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        started = time.monotonic()
        self.request_metrics.increment("model_rounds")
        try:
            return await super()._chat(messages, tools)
        finally:
            self.request_metrics.observe_ms("provider", (time.monotonic() - started) * 1000)

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        return await self.final_answers.answer(messages)

    def _create_grounding_policy(self, *, logs_requested: bool, conversational: bool) -> LiveEvidenceAuthority:
        return LiveEvidenceAuthority(
            self.evidence,
            logs_requested=logs_requested,
            conversational=conversational,
            record_metric=self.request_metrics.increment,
        )

    @staticmethod
    def _literal_device_name(name: str) -> str:
        return re.sub(r"^(?:the|a|an)\s+", "", name.strip(), flags=re.I)

    @classmethod
    def _last_contact_request(cls, prompt: str) -> tuple[str, str] | None:
        match = cls._LAST_CONTACT.fullmatch(prompt)
        if match is None:
            return None
        state = match.group("state").casefold()
        return cls._literal_device_name(match.group("name")), "closed" if state.startswith("clos") else "open"

    @classmethod
    def _why_contact_request(cls, prompt: str) -> tuple[str, str] | None:
        match = cls._WHY_CONTACT.fullmatch(prompt)
        if match is None:
            return None
        state = match.group("state").casefold()
        return cls._literal_device_name(match.group("name")), "closed" if state.startswith("clos") else "open"

    @classmethod
    def _is_choice_follow_up(cls, prompt: str) -> bool:
        return cls._FOLLOW_UP_PRONOUN.search(prompt) is not None

    @staticmethod
    def _choice_message(choices: list[str]) -> str:
        if len(choices) == 1:
            return f"Do you mean {choices[0]}?"
        return "Which device do you mean: " + ", ".join(choices[:-1]) + f", or {choices[-1]}?"

    @classmethod
    def _choices_from_message(cls, message: str) -> list[str]:
        match = cls._CHOICE_LIST.search(message.strip())
        if match is None:
            return []
        text = re.sub(r"[*_`]", "", match.group("choices"))
        parts = re.split(r",\s*|\s+or\s+", text)
        choices: list[str] = []
        seen: set[str] = set()
        for part in parts:
            cleaned = clean_choice_label(
                re.sub(r"^(?:or|and)\s+", "", part.strip(" .?!"), flags=re.I)
            )
            key = cleaned.casefold()
            if cleaned and key not in seen:
                choices.append(cleaned)
                seen.add(key)
        return choices

    async def _direct_outcome(self, operation: Callable[[], Awaitable[str]], *, request_class: str) -> AgentOutcome:
        return await self.direct_outcomes.run(operation, request_class=request_class)

    async def _selection_outcome(self, name: str, *, session_key: str) -> AgentOutcome:
        async def operation() -> str:
            result = await self._resolve_device({"name": name})
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_resolve_device", data, failed=True, fallback_error=result.text
                ) or "I could not select that device."
            target = data.get("target") if isinstance(data.get("target"), dict) else None
            label = str(data.get("label") or name)
            if target is None:
                alternatives = [
                    clean_choice_label(str(item))
                    for item in data.get("alternatives") or []
                    if str(item).strip()
                ]
                if alternatives:
                    self._choices.set(alternatives)
                    self.request_metrics.increment("device_resolution_ambiguous")
                    return self._choice_message(alternatives)
                self.request_metrics.increment("device_resolution_missing")
                return f'I could not find a device named "{name}".'
            self._selected_devices[session_key] = label
            self._clarification_choices.pop(session_key, None)
            return f"Selected {label}."

        return await self._direct_outcome(operation, request_class="live-read")

    async def _contextual_attribute_outcome(
        self,
        name: str,
        attribute: str,
        *,
        session_key: str,
    ) -> AgentOutcome:
        async def operation() -> str:
            result = await self._resolve_device({"name": name})
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_resolve_device", data, failed=True, fallback_error=result.text
                ) or "I could not read the current device state."
            target = data.get("target") if isinstance(data.get("target"), dict) else None
            label = str(data.get("label") or name)
            if target is not None:
                source_attribute, value = DeviceQueryService._attribute_value(
                    target, attribute, allow_generic_value_fallback=True
                )
                if value is not None:
                    self._selected_devices[session_key] = label
                    # valueStr is already a human-formatted reading with its
                    # own unit baked in ("231 W") -- appending _unit_for's
                    # unit on top would double it up ("231 WW").
                    unit = (
                        None
                        if source_attribute == "valueStr"
                        else DeviceQueryService._unit_for(attribute)
                    )
                    return present_attribute(label, attribute, value, unit)

            filtered = await self._filter_devices({
                "attribute": attribute,
                "operator": "exists",
            })
            filtered_data = filtered.data if isinstance(filtered.data, dict) else {}
            if not self._tool_succeeded(filtered):
                return present_tool_result(
                    "homebrain_filter_devices",
                    filtered_data,
                    failed=True,
                    fallback_error=filtered.text,
                ) or "I could not read the current device state."
            matches = [
                item for item in filtered_data.get("matches") or [] if isinstance(item, dict)
            ]
            alternatives = capability_choice_labels(name, matches)
            if len(alternatives) > 1:
                self._choices.set(alternatives)
                self.request_metrics.increment("device_resolution_ambiguous")
                return self._choice_message(alternatives)
            if len(alternatives) == 1:
                selected_label = alternatives[0]
                selected = next(
                    (item for item in matches if str(item.get("label") or "").casefold() == selected_label.casefold()),
                    None,
                )
                if selected is not None:
                    self._selected_devices[session_key] = selected_label
                    return present_attribute(
                        selected_label,
                        attribute,
                        selected.get("value"),
                        DeviceQueryService._unit_for(attribute),
                    )
            if target is not None:
                self._selected_devices[session_key] = label
                return f"{label} does not report a current {attribute} value."
            alternatives = [
                clean_choice_label(str(item))
                for item in data.get("alternatives") or []
                if str(item).strip()
            ]
            if alternatives:
                self._choices.set(alternatives)
                self.request_metrics.increment("device_resolution_ambiguous")
                return self._choice_message(alternatives)
            self.request_metrics.increment("device_resolution_missing")
            return f'I could not find a device named "{name}".'

        return await self._direct_outcome(operation, request_class="live-read")

    async def _motion_activity_outcome(self, state: str, *, count_only: bool) -> AgentOutcome:
        async def operation() -> str:
            result = await self._filter_devices({
                "attribute": "motion",
                "operator": "eq",
                "value": state,
            })
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_filter_devices", data, failed=True, fallback_error=result.text
                ) or "I could not read the current motion sensor states."
            matches = [item for item in data.get("matches") or [] if isinstance(item, dict)]
            return present_motion_activity(matches, state=state, count_only=count_only)

        return await self._direct_outcome(operation, request_class="live-read")

    async def _read_contact_history(self, name: str, *, hours_back: int = 168) -> tuple[Any, dict[str, Any]]:
        result = await self.device_history.history({
            "name": name,
            "hours_back": hours_back,
            "attribute": "contact",
            "limit": 100,
        })
        return result, result.data if isinstance(result.data, dict) else {}

    async def _contact_event_outcome(
        self,
        name: str,
        state: str,
        *,
        explain_cause: bool,
        session_key: str,
    ) -> AgentOutcome:
        async def operation() -> str:
            result, data = await self._read_contact_history(name)
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_device_history", data, failed=True, fallback_error=result.text
                ) or "I could not read the device history."
            events = contact_events([item for item in data.get("events", []) if isinstance(item, dict)])
            matching = next(
                (item for item in events if str(item.get("value") or "").casefold() == state),
                None,
            )
            label = str(data.get("label") or name)
            if matching is None:
                return f"No {state} contact event was reported for {label} in the last 7 days."
            raw_timestamp = str(matching.get("date") or "")
            self._history_references[session_key] = HistoryReference(label, state, raw_timestamp)
            timestamp = format_natural_datetime(raw_timestamp)
            verb = "opened" if state == "open" else "closed"
            if explain_cause:
                article = "an" if state == "open" else "a"
                return (
                    f"{label} reported {article} {state} contact event at {timestamp}. "
                    "The device history does not identify which person or automation caused it."
                )
            return f"{label} last {verb} at {timestamp}."

        return await self._direct_outcome(operation, request_class="live-read")

    async def _relative_that_outcome(
        self,
        name: str | None,
        state: str,
        direction: str,
        session_key: str,
    ) -> AgentOutcome:
        async def operation() -> str:
            reference = self._history_references.get(session_key)
            if reference is None:
                self.request_metrics.increment("device_resolution_missing")
                return "I do not have a previous history event to use as the reference."
            target_name = name or reference.label
            result, data = await self._read_contact_history(target_name)
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_device_history", data, failed=True, fallback_error=result.text
                ) or "I could not read the device history."
            events = [item for item in data.get("events", []) if isinstance(item, dict)]
            finder = find_before_reference if direction == "before" else find_after_reference
            matching = finder(events, state=state, reference_timestamp=reference.timestamp)
            label = str(data.get("label") or target_name)
            if matching is None:
                return f"No {direction} {state} contact event was reported for {label}."
            raw_timestamp = str(matching.get("date") or "")
            self._history_references[session_key] = HistoryReference(label, state, raw_timestamp)
            verb = "opened" if state == "open" else "closed"
            return f"{label} {verb} {direction} that at {format_natural_datetime(raw_timestamp)}."

        return await self._direct_outcome(operation, request_class="live-read")

    async def _count_yesterday_outcome(self, name: str, state: str) -> AgentOutcome:
        async def operation() -> str:
            result, data = await self._read_contact_history(name, hours_back=48)
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_device_history", data, failed=True, fallback_error=result.text
                ) or "I could not read the device history."
            events = [item for item in data.get("events", []) if isinstance(item, dict)]
            start, end = yesterday_bounds(datetime.now().astimezone())
            selected = events_in_window(events, start, end)
            count = sum(1 for item in selected if str(item.get("value") or "").casefold() == state)
            return present_count(str(data.get("label") or name), state, count)

        return await self._direct_outcome(operation, request_class="live-read")

    async def _list_yesterday_outcome(self, name: str) -> AgentOutcome:
        async def operation() -> str:
            result, data = await self._read_contact_history(name, hours_back=48)
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_device_history", data, failed=True, fallback_error=result.text
                ) or "I could not read the device history."
            events = [item for item in data.get("events", []) if isinstance(item, dict)]
            start, end = yesterday_bounds(datetime.now().astimezone())
            selected = events_in_window(events, start, end)
            return present_yesterday_events(str(data.get("label") or name), selected)

        return await self._direct_outcome(operation, request_class="live-read")

    async def _firmware_status_outcome(self, *, session_key: str) -> AgentOutcome:
        """Deterministically answer "how's the firmware update going" style
        questions from the same firmware snapshot the install/propose flow
        uses, without a model round.

        Hubitat's Hub Info driver does not expose a live download
        percentage (see parse_firmware_status_intent's docstring for the
        live evidence), so this reports the only thing the data actually
        supports: whether the installed version has caught up with the
        available one yet.
        """

        async def operation() -> str:
            started = time.monotonic()
            result = await self._hub_info_snapshot({"scope": "firmware"})
            self.evidence.record(
                LOCAL_HUB_INFO_TOOL,
                {"scope": "firmware"},
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                evidence_kind=EVIDENCE_KINDS[LOCAL_HUB_INFO_TOOL],
            )
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    LOCAL_HUB_INFO_TOOL, data, failed=True, fallback_error=result.text
                ) or "I could not read the hub firmware status."
            installed = data.get("installed_firmware")
            available = data.get("available_firmware")
            if not data.get("update_available"):
                # hub_info_service computes update_available from whether
                # installed still trails available, so this branch covers
                # both "nothing was ever pending" and "an update just
                # finished and the versions caught up" -- the snapshot data
                # can't distinguish the two, and the phrasing below reads
                # correctly either way.
                return (
                    f"Firmware is up to date -- the hub is running "
                    f"{installed or 'its current version'}. No update is pending."
                )
            return (
                f"Still in progress: the hub is on {installed or 'its current version'}, "
                f"and {available or 'the newer version'} is still shown as available. "
                "Hubitat doesn't expose a live download percentage through this "
                "reading, only whether the versions have converged -- if it's been "
                "more than 10-15 minutes, check Settings > Check for Updates on the "
                "hub directly, since a stalled update usually needs a manual retry."
            )

        return await self._direct_outcome(operation, request_class="live-read")

    async def _firmware_install_outcome(self, *, session_key: str) -> AgentOutcome:
        """Deterministically propose the sensitive `hub_update_firmware`
        write once an explicit install directive is recognised, instead of
        trusting the model to chain a second tool call after reading the
        firmware snapshot (see parse_firmware_install_intent's docstring
        for the live failure this fixes). This only ever queues the
        existing confirmation gate -- the actual firmware write still does
        not run until the user replies "confirm", exactly as it would if
        the model had proposed it itself.
        """

        async def operation() -> str:
            started = time.monotonic()
            result = await self._hub_info_snapshot({"scope": "firmware"})
            self.evidence.record(
                LOCAL_HUB_INFO_TOOL,
                {"scope": "firmware"},
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                evidence_kind=EVIDENCE_KINDS[LOCAL_HUB_INFO_TOOL],
            )
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    LOCAL_HUB_INFO_TOOL, data, failed=True, fallback_error=result.text
                ) or "I could not read the hub firmware status."
            installed = data.get("installed_firmware") or "the installed version"
            if not data.get("update_available"):
                return (
                    f"Hub firmware {installed} is already the latest version. "
                    "No update is available to install."
                )
            actions: list[tuple[str, dict[str, Any]]] = [("hub_update_firmware", {})]
            decision = self.confirmation_policy.decide(session_key, actions)
            if decision.action is ConfirmationAction.REJECT:
                return str(decision.message)
            # queue() stores this alongside the confirmed-action replay path
            # (ConfirmedActionCoordinator.resume) -- it executes every entry
            # in `actions` directly rather than re-parsing tool_calls back
            # out of assistant_message, so this synthetic message only needs
            # to read sensibly as chat history for the post-confirm
            # narration round, not carry any binding structure of its own.
            assistant_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {"name": "hub_update_firmware", "arguments": {}},
                }],
            }
            self.confirmations.queue(
                session_key,
                actions,
                [{
                    "role": "user",
                    "content": "Install the available Hubitat firmware update.",
                }],
                assistant_message,
            )
            return str(decision.message)

        outcome = await self._direct_outcome(operation, request_class="write")
        pending = self.confirmations.pending.get(str(session_key))
        if pending is not None:
            outcome.confirmation_required = True
            outcome.confirmation_count = len(pending.actions)
        return outcome

    async def _routine_control_outcome(self, arguments: dict[str, Any]) -> AgentOutcome:
        async def operation() -> str:
            started = time.monotonic()
            result = await self._control_devices(arguments)
            self.evidence.record(
                "homebrain_control_devices",
                arguments,
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                evidence_kind="deterministic_device_control",
            )
            data = result.data if isinstance(result.data, dict) else {}
            choices = [str(choice) for choice in data.get("choices") or [] if str(choice).strip()]
            if choices:
                self._choices.set(choices)
                self.request_metrics.increment("device_resolution_ambiguous")
            return present_tool_result(
                "homebrain_control_devices",
                data,
                failed=not self._tool_succeeded(result),
                fallback_error=result.text,
            ) or result.text

        return await self._direct_outcome(operation, request_class="write")

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> ObservedAgentOutcome:
        session_key = str(session_id)

        async def operation() -> AgentOutcome:
            before_that = parse_before_that(user_prompt)
            if before_that is not None:
                return await self._relative_that_outcome(before_that[0], before_that[1], "before", session_key)

            after_that = parse_after_that(user_prompt)
            if after_that is not None:
                return await self._relative_that_outcome(after_that[0], after_that[1], "after", session_key)

            selection = parse_device_selection(user_prompt)
            if selection is not None:
                return await self._selection_outcome(selection, session_key=session_key)

            prior_choices = list(self._clarification_choices.get(session_key) or [])
            if prior_choices:
                normalized = user_prompt.casefold()
                explicit = next((choice for choice in prior_choices if choice.casefold() in normalized), None)
                if explicit is None and self._is_choice_follow_up(user_prompt):
                    self.request_metrics.increment("device_resolution_ambiguous")
                    return AgentOutcome(
                        message=self._choice_message(prior_choices),
                        request_class="live-read",
                        evidence=[],
                        choices=prior_choices,
                    )
                if explicit is not None:
                    self._clarification_choices.pop(session_key, None)
                    self._selected_devices[session_key] = explicit

            contextual_attribute = parse_contextual_attribute(user_prompt)
            selected_device = self._selected_devices.get(session_key)
            if contextual_attribute is not None and selected_device:
                return await self._contextual_attribute_outcome(
                    selected_device,
                    contextual_attribute,
                    session_key=session_key,
                )

            named_attribute = parse_named_attribute(user_prompt)
            if named_attribute is not None:
                return await self._contextual_attribute_outcome(
                    named_attribute[0],
                    named_attribute[1],
                    session_key=session_key,
                )

            # A bare, unqualified reading word ("temperature", "humidity",
            # "what's the battery") carries no device name at all, so it
            # can't go through parse_named_attribute above. Resolving it
            # with the attribute word standing in for both the requested
            # name and the attribute reaches DeviceQueryService.resolve_device
            # unchanged -- its existing bare-attribute guard (0.10.369) is
            # what actually disambiguates across multiple indoor reporters
            # or resolves a device literally labelled e.g. "Temperature".
            # This bypasses the model's tool-selection loop entirely for
            # this case, so it can no longer choose
            # homebrain_weather_snapshot for an indoor reading no matter how
            # the prompt is worded that day.
            bare_attribute = parse_bare_attribute(user_prompt)
            if bare_attribute is not None:
                return await self._contextual_attribute_outcome(
                    bare_attribute,
                    bare_attribute,
                    session_key=session_key,
                )

            motion_activity = parse_motion_activity(user_prompt)
            if motion_activity is not None:
                return await self._motion_activity_outcome(motion_activity[0], count_only=motion_activity[1])

            count_yesterday = parse_count_yesterday(user_prompt)
            if count_yesterday is not None:
                return await self._count_yesterday_outcome(count_yesterday[0], count_yesterday[1])

            list_yesterday = parse_list_yesterday(user_prompt)
            if list_yesterday is not None:
                return await self._list_yesterday_outcome(list_yesterday)

            last_contact = self._last_contact_request(user_prompt)
            if last_contact is not None:
                return await self._contact_event_outcome(
                    last_contact[0],
                    last_contact[1],
                    explain_cause=False,
                    session_key=session_key,
                )

            why_contact = self._why_contact_request(user_prompt)
            if why_contact is not None:
                return await self._contact_event_outcome(
                    why_contact[0],
                    why_contact[1],
                    explain_cause=True,
                    session_key=session_key,
                )

            if parse_firmware_status_intent(user_prompt):
                return await self._firmware_status_outcome(session_key=session_key)

            if parse_firmware_install_intent(user_prompt):
                return await self._firmware_install_outcome(session_key=session_key)

            # A prompt carrying an "at <time>" clause (e.g. "turn on X at
            # 10am", "turn on X every day at 10am") must reach
            # RuleAuthoringService via base_process() below, not this
            # instant fast path -- routine_control_arguments() has no
            # concept of scheduling and would otherwise silently execute
            # the command right now (a "daily"/"every day" request) or hand
            # a mangled device name into DeviceControlService's own
            # smuggled-time refusal (a one-time request), preempting the
            # rule-authoring grammar that can actually honour either one.
            control_arguments = self._routine_control_arguments(user_prompt)
            if control_arguments is not None and AT_TIME.search(user_prompt) is None:
                return await self._routine_control_outcome(control_arguments)

            base_process = super(UnifiedMCPAgent, self).process_user_request_result
            return await base_process(user_prompt, conversation_history, session_id=session_id)

        outcome = await self.request_observation.run(operation)
        choices = list(outcome.choices or []) or self._choices_from_message(outcome.message)
        if choices:
            choices = [clean_choice_label(choice) for choice in choices]
            outcome.choices = choices
            self._clarification_choices[session_key] = choices
        return outcome

    async def _process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        factory_token = set_grounding_policy_factory(self._create_grounding_policy)
        try:
            return await super()._process_user_request(user_prompt, conversation_history, session_id=session_id)
        finally:
            reset_grounding_policy_factory(factory_token)


__all__ = ["AgentOutcome", "ObservedAgentOutcome", "UnifiedMCPAgent"]
