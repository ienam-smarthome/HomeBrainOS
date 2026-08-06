"""Deterministic compiler for common Rule Machine schedules.

The model may identify an automation goal, but it must not invent Hubitat's
``hub_set_rule`` JSON.  This service recognises a deliberately small,
high-confidence schedule grammar, resolves the target through the shared
device resolver, verifies the requested commands, and emits validated atomic
Rule Machine calls for the existing confirmation pipeline.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from device_query_service import DeviceQueryService
from mcp_client import HubitatMCPClient
from time_expressions import AT_TIME as _SHARED_AT_TIME, parse_clock as _shared_parse_clock
from tool_registry import rule_machine_proposal_error


RULE_MACHINE_GATEWAY = "hub_manage_rule_machine"


@dataclass(frozen=True, slots=True)
class RuleAuthoringDecision:
    """Result of attempting the bounded deterministic rule grammar."""

    handled: bool
    message: str | None = None
    actions: tuple[dict[str, Any], ...] = ()
    rule_names: tuple[str, ...] = ()
    target: dict[str, Any] | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class _ScheduleIntent:
    target: str
    start_time: str
    start_command: str
    start_label: str
    end_time: str | None = None
    end_command: str | None = None
    end_label: str | None = None


class RuleAuthoringService:
    """Compile supported daily device schedules without model-authored JSON."""

    _AUTHORING = re.compile(
        r"\b(?:add|build|create|make|schedule|set up|setup|write)\b"
        r"[\s\S]{0,40}\b(?:automation|rule|schedule)\b",
        re.I,
    )
    _WINDOW = re.compile(
        r"\bfrom\s+(?P<start>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
        r"\s+(?:to|until|through|-)\s+"
        r"(?P<end>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
        re.I,
    )
    _DAILY = re.compile(r"\b(?:daily|every\s*day|everyday)\b", re.I)
    _PREFIX = re.compile(
        r"^.*?\b(?:automation|rule|schedule)\b\s+(?:that\s+|to\s+)?",
        re.I,
    )
    _AT_TIME = _SHARED_AT_TIME

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence

    @staticmethod
    def _clock(value: str) -> str | None:
        return _shared_parse_clock(value)

    @classmethod
    def _clean_goal(cls, text: str, cut: int) -> str:
        """Strip the authoring prefix and the daily marker from a goal slice.

        The daily marker ("daily" / "every day" / "everyday") can precede
        or follow the time clause in natural phrasing -- "block internet
        every day from 10pm to 6am" is at least as common as "...from 10pm
        to 6am every day". Whichever side it lands on within this slice,
        it must not survive into the goal text or the verb-pattern
        fullmatch below will spuriously fail.
        """

        goal = cls._PREFIX.sub("", text[:cut])
        goal = cls._DAILY.sub("", goal)
        return " ".join(goal.split()).strip(" ,.-")

    @classmethod
    def _intent(cls, prompt: str) -> _ScheduleIntent | None:
        text = " ".join(str(prompt).strip().split())
        if not cls._AUTHORING.search(text) or not cls._DAILY.search(text):
            return None
        window = cls._WINDOW.search(text)
        if window is not None:
            return cls._window_intent(text, window)
        return cls._single_intent(text)

    @classmethod
    def _window_intent(cls, text: str, window: re.Match[str]) -> _ScheduleIntent | None:
        start = cls._clock(window.group("start"))
        end = cls._clock(window.group("end"))
        if start is None or end is None or start == end:
            return None

        goal = cls._clean_goal(text, window.start())
        patterns = (
            (re.compile(r"^(?:block|disable)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I),
             "blockInternet", "allowInternet", "Block", "Unblock"),
            (re.compile(r"^(?:turn|switch)\s+(?P<target>.+?)\s+off$", re.I),
             "off", "on", "Turn off", "Turn on"),
            (re.compile(r"^lock\s+(?P<target>.+)$", re.I),
             "lock", "unlock", "Lock", "Unlock"),
            (re.compile(r"^(?:close|shut)\s+(?P<target>.+)$", re.I),
             "close", "open", "Close", "Open"),
        )
        for pattern, start_command, end_command, start_label, end_label in patterns:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if target:
                return _ScheduleIntent(
                    target=target,
                    start_time=start,
                    start_command=start_command,
                    start_label=start_label,
                    end_time=end,
                    end_command=end_command,
                    end_label=end_label,
                )
        return None

    _SINGLE_PATTERNS = (
        (re.compile(r"^turn\s+on\s+(?P<target>.+)$", re.I), "on", "Turn on"),
        (re.compile(r"^turn\s+(?P<target>.+?)\s+on$", re.I), "on", "Turn on"),
        (re.compile(r"^switch\s+on\s+(?P<target>.+)$", re.I), "on", "Turn on"),
        (re.compile(r"^switch\s+(?P<target>.+?)\s+on$", re.I), "on", "Turn on"),
        (re.compile(r"^turn\s+off\s+(?P<target>.+)$", re.I), "off", "Turn off"),
        (re.compile(r"^turn\s+(?P<target>.+?)\s+off$", re.I), "off", "Turn off"),
        (re.compile(r"^switch\s+off\s+(?P<target>.+)$", re.I), "off", "Turn off"),
        (re.compile(r"^switch\s+(?P<target>.+?)\s+off$", re.I), "off", "Turn off"),
        (re.compile(r"^lock\s+(?P<target>.+)$", re.I), "lock", "Lock"),
        (re.compile(r"^unlock\s+(?P<target>.+)$", re.I), "unlock", "Unlock"),
        (re.compile(r"^(?:close|shut)\s+(?P<target>.+)$", re.I), "close", "Close"),
        (re.compile(r"^open\s+(?P<target>.+)$", re.I), "open", "Open"),
        (re.compile(
            r"^(?:block|disable)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "blockInternet", "Block"),
        (re.compile(
            r"^(?:allow|enable)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "allowInternet", "Unblock"),
    )

    @classmethod
    def _single_intent(cls, text: str) -> _ScheduleIntent | None:
        """Recognise a single daily trigger with no auto-revert window.

        Deliberately narrower than the window grammar: exactly one
        advertised command is required and verified, exactly one atomic
        rule is emitted. "Turn on X every day at 7am" is the intended
        shape; it must not be confused with the window grammar's
        auto-reverting "turn X off from A to B" pattern, so this path only
        runs when `_window_intent` found no window clause at all.
        """

        at_match = cls._AT_TIME.search(text)
        if at_match is None:
            return None
        at_time = cls._clock(at_match.group("time"))
        if at_time is None:
            return None

        goal = cls._clean_goal(text, at_match.start())
        for pattern, command, label in cls._SINGLE_PATTERNS:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if target:
                return _ScheduleIntent(
                    target=target,
                    start_time=at_time,
                    start_command=command,
                    start_label=label,
                )
        return None

    @staticmethod
    def _commands(device: dict[str, Any]) -> set[str]:
        values = device.get("commands") or device.get("supportedCommands") or []
        if isinstance(values, dict):
            values = list(values)
        commands: set[str] = set()
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("command")
            if item:
                commands.add(str(item).casefold())
        return commands

    @staticmethod
    def _capability_filter(device: dict[str, Any]) -> str:
        values = device.get("capabilities") or []
        if isinstance(values, dict):
            values = list(values)
        names = []
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("capability")
            if item:
                names.append(str(item))
        for preferred in ("Switch", "Lock", "DoorControl", "GarageDoorControl"):
            if any(name.casefold() == preferred.casefold() for name in names):
                return preferred
        return names[0] if names else "Switch"

    @staticmethod
    def _rule_name(label: str, target_label: str, suffix: str) -> str:
        clean = re.sub(r"[-_]+", " ", target_label)
        clean = " ".join(clean.split())
        base = clean if clean.casefold().startswith(label.casefold() + " ") else f"{label} {clean}"
        return f"{base} ({suffix})"

    @classmethod
    def _action(
        cls,
        *,
        name: str,
        at_time: str,
        device_id: Any,
        capability_filter: str,
        command: str,
    ) -> dict[str, Any]:
        action = {
            "tool": "hub_set_rule",
            "args": {
                "name": name,
                "addTrigger": {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": at_time,
                },
                "addAction": {
                    "capability": "runCommand",
                    "deviceIds": [str(device_id)],
                    "capabilityFilter": capability_filter,
                    "command": command,
                },
            },
        }
        error = rule_machine_proposal_error(RULE_MACHINE_GATEWAY, action)
        if error is not None:
            raise ValueError(error)
        return action

    @staticmethod
    def _rule_rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            for key in ("rules", "items", "apps", "data", "result", "output"):
                nested = value.get(key)
                rows = RuleAuthoringService._rule_rows(nested)
                if rows:
                    return rows
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    async def _existing_names(self) -> set[str]:
        arguments = {"tool": "hub_list_rules", "args": {}}
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_read_rules", arguments)
        except Exception:
            return set()
        success = not result.is_error and not (
            isinstance(result.data, dict) and result.data.get("success") is False
        )
        rows = self._rule_rows(result.data)
        self._record_evidence(
            "hub_read_rules",
            arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(rows)} existing Rule Machine rules checked for duplicates",
            supports_live_claim=True,
            evidence_kind="rule_duplicate_check",
        )
        return {
            str(item.get("name") or item.get("label") or "").strip().casefold()
            for item in rows
            if item.get("name") or item.get("label")
        }

    async def propose(
        self,
        prompt: str,
        *,
        available_gateways: set[str],
        can_read_rules: bool = False,
    ) -> RuleAuthoringDecision:
        """Return a complete validated plan only for the supported grammar."""

        intent = self._intent(prompt)
        if intent is None:
            return RuleAuthoringDecision(False)
        if RULE_MACHINE_GATEWAY not in available_gateways:
            return RuleAuthoringDecision(False)

        resolver = DeviceQueryService(self.mcp, self._record_evidence)
        result = await resolver.resolve_device({"name": intent.target})
        data = result.data if isinstance(result.data, dict) else {}
        target = data.get("target") if isinstance(data.get("target"), dict) else None
        if target is None:
            alternatives = [str(item) for item in data.get("alternatives") or [] if str(item)]
            if alternatives:
                return RuleAuthoringDecision(
                    True,
                    "I found more than one plausible target. Please choose: "
                    + ", ".join(alternatives[:3])
                    + ". Nothing was queued.",
                )
            return RuleAuthoringDecision(
                True,
                f"I could not resolve **{intent.target}** to one Hubitat device. "
                "Nothing was queued.",
            )

        device_id = target.get("id") or target.get("deviceId")
        target_label = str(target.get("label") or target.get("name") or intent.target)
        if device_id in {None, ""}:
            return RuleAuthoringDecision(
                True,
                f"The resolved device **{target_label}** has no stable Hubitat ID. "
                "Nothing was queued.",
                target=target,
            )
        supported = self._commands(target)
        required = {intent.start_command.casefold()}
        if intent.end_command is not None:
            required.add(intent.end_command.casefold())
        if not required.issubset(supported):
            missing = sorted(required - supported)
            return RuleAuthoringDecision(
                True,
                f"**{target_label}** does not advertise the required command"
                f"{'s' if len(missing) != 1 else ''}: {', '.join(missing)}. "
                "Nothing was queued.",
                target=target,
            )

        capability_filter = self._capability_filter(target)

        if intent.end_time is None:
            single_name = self._rule_name(intent.start_label, target_label, "Daily")
            existing = await self._existing_names() if can_read_rules else set()
            if single_name.casefold() in existing:
                return RuleAuthoringDecision(
                    True,
                    "No duplicate rule was queued because this Rule Machine rule "
                    f"already exists: **{single_name}**.",
                    rule_names=(single_name,),
                    target=target,
                )
            actions = (
                self._action(
                    name=single_name,
                    at_time=intent.start_time,
                    device_id=device_id,
                    capability_filter=capability_filter,
                    command=intent.start_command,
                ),
            )
            return RuleAuthoringDecision(
                True,
                actions=actions,
                rule_names=(single_name,),
                target=target,
            )

        start_name = self._rule_name(intent.start_label, target_label, "Start")
        end_name = self._rule_name(intent.start_label, target_label, "End")
        existing = await self._existing_names() if can_read_rules else set()
        duplicates = [name for name in (start_name, end_name) if name.casefold() in existing]
        if duplicates:
            return RuleAuthoringDecision(
                True,
                "No duplicate rules were queued because these Rule Machine rules "
                "already exist: " + ", ".join(f"**{name}**" for name in duplicates) + ".",
                rule_names=(start_name, end_name),
                target=target,
            )

        actions = (
            self._action(
                name=start_name,
                at_time=intent.start_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.start_command,
            ),
            self._action(
                name=end_name,
                at_time=intent.end_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.end_command,
            ),
        )
        return RuleAuthoringDecision(
            True,
            actions=actions,
            rule_names=(start_name, end_name),
            target=target,
        )


__all__ = [
    "RULE_MACHINE_GATEWAY",
    "RuleAuthoringDecision",
    "RuleAuthoringService",
]
