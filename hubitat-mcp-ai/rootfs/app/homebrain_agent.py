from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from deterministic_tool_presenter import present_tool_result
from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import (
    reset_grounding_policy_factory,
    set_grounding_policy_factory,
)
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent
from natural_datetime import format_natural_datetime
from observed_agent_outcome import ObservedAgentOutcome
from request_metrics import RequestMetrics
from request_observation import RequestObservationCoordinator
from token_aware_context_policy import TokenAwareModelContextPolicy


class UnifiedMCPAgent(BaseUnifiedMCPAgent):
    """Production agent with delegated synthesis, grounding, and observability."""

    _FOLLOW_UP_PRONOUN = re.compile(
        r"\b(?:it|its|that|this|which one|the one|one of them)\b",
        re.I,
    )
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
        self._clarification_choices: dict[str, list[str]] = {}

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
        for part in parts:
            cleaned = re.sub(r"^or\s+", "", part.strip(" .?!"), flags=re.I)
            if cleaned:
                choices.append(cleaned)
        return choices

    async def _direct_outcome(self, operation: Callable[[], Awaitable[str]], *, request_class: str) -> AgentOutcome:
        evidence_token = self.evidence.begin()
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(request_class == "write")
        class_token = self._request_class.set(request_class)
        try:
            message = await operation()
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=self.evidence.receipts(),
                choices=list(self._choices.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._mutation_call_seen.reset(mutation_token)
            self.evidence.reset(evidence_token)
            self._choices.reset(choices_token)

    async def _contact_event_outcome(self, name: str, state: str, *, explain_cause: bool) -> AgentOutcome:
        async def operation() -> str:
            result = await self.device_history.history({
                "name": name,
                "hours_back": 168,
                "attribute": "contact",
                "limit": 50,
            })
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    "homebrain_device_history",
                    data,
                    failed=True,
                    fallback_error=result.text,
                ) or "I could not read the device history."
            events = [item for item in data.get("events", []) if isinstance(item, dict)]
            matching = next((
                item for item in events
                if str(item.get("name") or "").casefold() == "contact"
                and str(item.get("value") or "").casefold() == state
            ), None)
            label = str(data.get("label") or name)
            if matching is None:
                return f"No {state} contact event was reported for {label} in the last 7 days."
            timestamp = format_natural_datetime(matching.get("date"))
            verb = "opened" if state == "open" else "closed"
            if explain_cause:
                article = "an" if state == "open" else "a"
                return (
                    f"{label} reported {article} {state} contact event at {timestamp}. "
                    "The device history does not identify which person or automation caused it."
                )
            return f"{label} last {verb} at {timestamp}."

        return await self._direct_outcome(operation, request_class="live-read")

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

            last_contact = self._last_contact_request(user_prompt)
            if last_contact is not None:
                return await self._contact_event_outcome(*last_contact, explain_cause=False)

            why_contact = self._why_contact_request(user_prompt)
            if why_contact is not None:
                return await self._contact_event_outcome(*why_contact, explain_cause=True)

            control_arguments = self._routine_control_arguments(user_prompt)
            if control_arguments is not None:
                return await self._routine_control_outcome(control_arguments)

            base_process = super(UnifiedMCPAgent, self).process_user_request_result
            return await base_process(user_prompt, conversation_history, session_id=session_id)

        outcome = await self.request_observation.run(operation)
        choices = list(outcome.choices or []) or self._choices_from_message(outcome.message)
        if choices:
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
            return await super()._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        finally:
            reset_grounding_policy_factory(factory_token)


__all__ = ["AgentOutcome", "ObservedAgentOutcome", "UnifiedMCPAgent"]
