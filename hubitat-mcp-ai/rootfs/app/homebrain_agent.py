from __future__ import annotations

import json
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
    is_pronoun_reference,
    parse_bare_attribute,
    parse_contextual_attribute,
    parse_device_selection,
    parse_motion_activity,
    parse_named_attribute,
    present_attribute,
    present_motion_activity,
)
from confirmation_policy import ConfirmationAction
from confirmation_store import CONFIRM_WORDS
from deterministic_tool_presenter import present_tool_result
from device_query_service import DeviceQueryService
from device_target_resolver import resolve_capable_device_candidate
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
    parse_hub_health_intent,
    parse_immediate_internet_access_intent,
)
from request_metrics import RequestMetrics
from request_observation import RequestObservationCoordinator
from time_expressions import AT_TIME
from token_aware_context_policy import TokenAwareModelContextPolicy
from tool_catalog_assembly import build_request_tool_catalog
from tool_registry import (
    EVIDENCE_KINDS,
    HUB_UPDATE_FIRMWARE_TOOL,
    LOCAL_HUB_INFO_TOOL,
    LOCAL_RESOLVE_TOOL,
)


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
                        else DeviceQueryService._unit_for(target, attribute, source_attribute)
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
                        DeviceQueryService._unit_for(selected, attribute),
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

    async def _hub_health_outcome(self, *, session_key: str) -> AgentOutcome:
        """Deterministically answer "check the hub health status" style
        questions from the Hub Info snapshot, without a model round.

        Live-observed bug: this used to reach the model unfiltered, which
        chose a raw `hub_read_diagnostics`/`hub_get_metrics` tool call and
        then wrote free-text prose from the result. The underlying data was
        correct (the hub's own Hub Info page confirmed "DB Size: 126 MB"),
        but the model's own summary mislabelled it "126 KB" -- and also
        added a "Cloud Backup: Successful" line with no corresponding field
        in the tool result at all, i.e. an outright fabrication. Routing
        this through `homebrain_hub_info_snapshot` and formatting its
        already-unit-tagged fields directly (see `hub_info_service.py`'s
        `database_size_unit`, `free_memory_unit`, `temperature_unit`)
        removes the model from the unit-labelling and fact-selection
        decision entirely -- every line below traces to a real field in the
        snapshot, and nothing is reported that the snapshot didn't return.

        Live re-test of this exact fast path (0.10.387) surfaced a second,
        smaller live bug: "Internal Temperature: 46.9 °C °C". The real
        Hub Info driver's `temperatureC` attribute already reports its
        `currentValue` as a display string with the unit baked in (e.g.
        "46.9 °C"), not a bare number -- the mock fixture this fast path
        shipped with used a bare numeric `currentValue`, which is why the
        duplication was never caught in tests. `field()` below now strips
        a trailing occurrence of the unit already present in the raw value
        before appending the tracked unit, so it renders correctly whether
        a given field/driver reports a bare number or a pre-unit-suffixed
        string.
        """

        async def operation() -> str:
            started = time.monotonic()
            result = await self._hub_info_snapshot({"scope": "resources"})
            self.evidence.record(
                LOCAL_HUB_INFO_TOOL,
                {"scope": "resources"},
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                evidence_kind=EVIDENCE_KINDS[LOCAL_HUB_INFO_TOOL],
            )
            data = result.data if isinstance(result.data, dict) else {}
            if not self._tool_succeeded(result):
                return present_tool_result(
                    LOCAL_HUB_INFO_TOOL, data, failed=True, fallback_error=result.text
                ) or "I could not read the hub health status."

            def field(name: str, unit_name: str | None = None) -> str | None:
                raw = data.get(name)
                if raw is None or str(raw).strip() == "":
                    return None
                text = str(raw).strip()
                unit = str(data.get(unit_name) or "").strip() if unit_name else ""
                if not unit:
                    return text
                # The raw value itself sometimes already carries the unit
                # suffix baked in (see docstring above -- live-observed
                # "46.9 °C °C"). Strip a trailing occurrence of the same
                # unit before appending it once, so it renders correctly
                # whether the underlying driver reports a bare number or a
                # pre-formatted display string.
                deduped = re.sub(
                    rf"\s*{re.escape(unit)}\s*$", "", text, flags=re.I
                ).strip()
                return f"{deduped or text} {unit}".strip()

            def health_word(raw: Any) -> str | None:
                # Live-observed regression: the real Hub Info driver reports
                # zbHealthy/zwHealthy as the literal strings "true"/"false"
                # (Hubitat attribute values are almost always transmitted as
                # strings, the same way a switch reports "on"/"off" rather
                # than a JSON boolean), not a Python bool -- the mock
                # fixture this shipped with used an actual bool, so the
                # isinstance(raw, bool) check alone never fired against the
                # real hub and the raw string leaked straight through.
                if raw is None:
                    return None
                if isinstance(raw, bool):
                    return "Healthy" if raw else "Not healthy"
                text = str(raw).strip()
                if text.casefold() == "true":
                    return "Healthy"
                if text.casefold() == "false":
                    return "Not healthy"
                return text or None

            alerts_raw = data.get("hub_alerts")
            # Live-observed regression: this originally only recognised
            # hub_alerts as a Python list. device_query_service.py's own
            # empty-alerts sentinel check (`hub_alerts not in (None, "",
            # "[]", [])`) proves the real Hub Info driver reports
            # hubAlerts as a STRING, not a list -- so a genuine active
            # alert here would have failed `isinstance(alerts_raw, list)`
            # and been silently reported as "no active alerts", masking
            # exactly what this feature exists to surface. A string value
            # is now parsed the same way: try it as a JSON array first
            # (covers a driver that serialises a real list into a string),
            # then fall back to treating the whole non-empty string as one
            # alert message.
            if isinstance(alerts_raw, list):
                alerts_list = alerts_raw
            elif isinstance(alerts_raw, str):
                text = alerts_raw.strip()
                if not text or text in {"[]", "none", "None"}:
                    alerts_list = []
                else:
                    try:
                        parsed = json.loads(text)
                    except (ValueError, TypeError):
                        parsed = None
                    alerts_list = parsed if isinstance(parsed, list) else [text]
            else:
                alerts_list = []
            alerts = [
                str(item).strip() for item in alerts_list if str(item).strip()
            ]
            if alerts:
                headline = f"The hub has {len(alerts)} active alert(s): {', '.join(alerts)}."
            elif alerts_raw is None:
                headline = "The hub did not report an alert status."
            else:
                headline = "The hub is healthy with no active alerts."

            cpu_percent = field("cpu_percent")
            rows: list[tuple[str, str | None]] = [
                ("Uptime", field("uptime")),
                ("Free Memory", field("free_memory", "free_memory_unit")),
                ("CPU Load", f"{cpu_percent}%" if cpu_percent is not None else None),
                ("Internal Temperature", field("temperature", "temperature_unit")),
                ("Database Size", field("database_size", "database_size_unit")),
                ("Zigbee", health_word(data.get("zigbee_healthy"))),
                ("Z-Wave", health_word(data.get("zwave_healthy"))),
                ("Matter", field("matter_status")),
            ]
            lines = [f"- **{label}:** {value}" for label, value in rows if value is not None]
            if not lines:
                return headline
            return headline + "\n\n**Current Status:**\n" + "\n".join(lines)

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
            actions: list[tuple[str, dict[str, Any]]] = [(HUB_UPDATE_FIRMWARE_TOOL, {})]
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
                    "function": {"name": HUB_UPDATE_FIRMWARE_TOOL, "arguments": {}},
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

    def _resolve_pronoun_control_target(
        self, arguments: dict[str, Any], *, session_key: str
    ) -> dict[str, Any]:
        """Substitute a bare pronoun target with the session's last device.

        Live-observed regression: "turn on Livingroom Light 2" immediately
        followed by "turn it off" returned "Unresolved" -- routine_control_
        arguments() parses "it" as a literal device_names entry, and
        DeviceControlService's fuzzy name resolver has no idea "it" means
        anything, so it fell through to a failed/ambiguous name lookup
        instead of the just-controlled device. The read-side follow-up path
        ("what's its temperature") already solves this by remembering the
        last resolved device in _selected_devices; _routine_control_outcome
        now writes to that same session slot on every single-device control
        success, so this only has to read it back for the pronoun case.
        When nothing has been controlled/selected yet this session, the
        arguments are returned unchanged and resolution fails exactly as
        before -- there is nothing honest to substitute.
        """

        names = arguments.get("device_names")
        if (
            not isinstance(names, list)
            or len(names) != 1
            or not is_pronoun_reference(str(names[0]))
        ):
            return arguments
        last_device = self._selected_devices.get(session_key)
        if not last_device:
            return arguments
        substituted = dict(arguments)
        substituted["device_names"] = [last_device]
        return substituted

    async def _routine_control_outcome(
        self, arguments: dict[str, Any], *, session_key: str
    ) -> AgentOutcome:
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
            # Remember exactly which device this command actually landed on
            # so an immediate pronoun follow-up ("turn it off") can resolve
            # against it, the same way _selected_devices already lets a
            # follow-up reading ("what's its temperature") resolve after a
            # named read. Only recorded when the command resolved to a
            # single device -- a room-wide or multi-device command has no
            # single "it" to remember, and remembering the wrong one would
            # be worse than making the follow-up ask again.
            succeeded = data.get("succeeded") or []
            if isinstance(succeeded, list) and len(succeeded) == 1:
                label = str(succeeded[0].get("label") or "").strip()
                if label:
                    self._selected_devices[session_key] = label
            return present_tool_result(
                "homebrain_control_devices",
                data,
                failed=not self._tool_succeeded(result),
                fallback_error=result.text,
            ) or result.text

        return await self._direct_outcome(operation, request_class="write")

    async def _internet_access_outcome(
        self, target_name: str, command: str, *, session_key: str
    ) -> AgentOutcome:
        """Deterministically execute an immediate (non-scheduled)
        block/allow-internet request against a device that actually
        advertises the command (see parse_immediate_internet_access_intent's
        docstring for the live failure this closes).

        `command` is always "blockInternet" or "allowInternet". Resolution
        is scoped to devices that advertise the command first
        (resolve_capable_device_candidate), then executed directly via
        hub_call_device_command with waitFor-based verification against
        the internetAccess attribute -- the same pattern already used for
        on/off/toggle device control, just with the attribute name real
        network-integration devices actually report instead of "switch".
        """

        async def operation() -> str:
            started = time.monotonic()
            try:
                candidates = await self.mcp.get_cached_devices()
            except Exception as exc:
                return f"I could not read the device list: {exc}"
            resolution = resolve_capable_device_candidate(
                target_name, list(candidates or []), required_command=command
            )
            self.evidence.record(
                LOCAL_RESOLVE_TOOL,
                {"name": target_name, "required_command": command},
                success=resolution.target is not None,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=resolution.reason,
                evidence_kind=EVIDENCE_KINDS[LOCAL_RESOLVE_TOOL],
            )
            verb = "block" if command == "blockInternet" else "allow"
            if resolution.target is None:
                if resolution.alternatives:
                    alternatives = list(resolution.alternatives)
                    self._choices.set(alternatives)
                    self.request_metrics.increment("device_resolution_ambiguous")
                    return self._choice_message(alternatives)
                return (
                    f'I could not find a device that supports {verb}ing '
                    f'internet access matching "{target_name}".'
                )
            device = resolution.target
            device_id = str(device.get("id") or device.get("deviceId") or "")
            label = str(device.get("label") or device.get("name") or target_name)
            if not device_id:
                return f"The resolved device **{label}** has no stable Hubitat ID."
            expected_value = "blocked" if command == "blockInternet" else "allowed"
            call_started = time.monotonic()
            result = await self.mcp.call_tool(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {
                        "deviceId": device_id,
                        "command": command,
                        "waitFor": {
                            "attribute": "internetAccess",
                            "expectedValue": expected_value,
                            "timeoutMs": 5000,
                        },
                    },
                },
            )
            command_success = self._tool_succeeded(result)
            wait_for = (
                result.data.get("waitFor") if isinstance(result.data, dict) else None
            )
            verified = bool(wait_for.get("converged")) if isinstance(wait_for, dict) else False
            self.evidence.record(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {"deviceId": device_id, "command": command},
                },
                success=command_success and verified,
                elapsed_ms=round((time.monotonic() - call_started) * 1000),
                summary=(
                    f"{command} {label}: "
                    f"{'verified' if verified else 'sent' if command_success else 'failed'}"
                ),
                evidence_kind="device_command_result",
            )
            if command_success and verified:
                verb_past = "blocked" if command == "blockInternet" else "unblocked"
                return f"{label} internet access {verb_past}."
            if command_success:
                return (
                    f"Sent the {command} command to {label}, but could not verify "
                    "internet access actually changed within 5 seconds."
                )
            return (
                f"Could not {verb} internet access for {label}: "
                f"{result.text or 'unknown error'}"
            )

        return await self._direct_outcome(operation, request_class="write")

    async def _resolve_pending_confirmation(
        self, user_prompt: str, *, session_key: str
    ) -> AgentOutcome | None:
        """Give any pending sensitive-action confirmation first refusal on
        every turn, before any deterministic fast path runs.

        Live debugging found a real gap: every fast path below (including
        the ones this session added -- firmware install/status, bare
        attribute, etc.) returns straight from `operation()` without ever
        reaching the base orchestrator's `_take_confirmation` /
        `ConfirmationStore.consume()`, which is where a pending
        confirmation actually gets consumed or cancelled. That meant: (1)
        a fast path could fire on an unrelated turn (e.g. "turn off the
        kitchen light") while a sensitive action was still pending,
        leaving it untouched instead of cancelled, so a *later* unrelated
        affirmative reply ("yes") could silently resume a stale action the
        user had long since moved on from; and (2) a fast path that queues
        its own confirmation (e.g. `_firmware_install_outcome`) could
        silently clobber a still-pending confirmation from an earlier,
        different request with no notice to the user.

        Mirrors `ConfirmationStore.consume()`'s own semantics exactly: any
        message consumes (and, if it isn't a recognised confirm word,
        thereby cancels) whatever is pending for this session, matching
        `mcp_agent_orchestrator.py`'s `_process_user_request` ordering.
        Only actually resumes the sensitive action, or reports "nothing
        pending" for a bare confirm word, when there is a real pending
        confirmation (or the prompt is unambiguously a confirm word with
        no live device-clarification also in flight -- see
        `test_homebrain_agent.py` for the "do it" collision this guards
        against) -- otherwise returns None so the normal fast-path chain
        proceeds untouched, exactly as it did before this method existed.
        """

        pending_now = self.confirmations.pending.get(session_key)
        if pending_now is not None:
            resolved = self.confirmations.consume(session_key, user_prompt)
            if resolved is None:
                # Not a confirm word -- already cancelled as a side effect
                # of consume(). Let this turn's fast path / model handle
                # the actual prompt normally.
                return None
            all_tools = (await self.mcp.list_tools())[: self.tool_limit]
            catalog = build_request_tool_catalog(all_tools)
            pending_names = list(dict.fromkeys(name for name, _ in resolved.actions))
            missing = catalog.replace_declared(pending_names)
            if missing:
                message = self.confirmation_policy.unavailable_tools_message(missing)
            else:
                message = await self._resume_confirmation(resolved, catalog)
            return AgentOutcome(
                message=message, request_class="write", evidence=[], choices=[]
            )

        normalized_prompt = " ".join(str(user_prompt).strip().casefold().split())
        if (
            normalized_prompt in CONFIRM_WORDS
            and not self._clarification_choices.get(session_key)
        ):
            return AgentOutcome(
                message=(
                    "No Hubitat action is pending confirmation in this browser "
                    "session. Nothing was executed. Submit the original request "
                    "again and only confirm when the response carries a "
                    "verified pending action."
                ),
                request_class="live-read",
                evidence=[],
                choices=[],
            )
        return None

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> ObservedAgentOutcome:
        session_key = str(session_id)

        async def operation() -> AgentOutcome:
            pending_confirmation = await self._resolve_pending_confirmation(
                user_prompt, session_key=session_key
            )
            if pending_confirmation is not None:
                return pending_confirmation

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

            if parse_hub_health_intent(user_prompt):
                return await self._hub_health_outcome(session_key=session_key)

            if parse_firmware_status_intent(user_prompt):
                return await self._firmware_status_outcome(session_key=session_key)

            if parse_firmware_install_intent(user_prompt):
                return await self._firmware_install_outcome(session_key=session_key)

            internet_access = parse_immediate_internet_access_intent(user_prompt)
            if internet_access is not None:
                return await self._internet_access_outcome(
                    internet_access[0], internet_access[1], session_key=session_key
                )

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
                control_arguments = self._resolve_pronoun_control_target(
                    control_arguments, session_key=session_key
                )
                return await self._routine_control_outcome(
                    control_arguments, session_key=session_key
                )

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
