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
from datetime import datetime, timedelta
from typing import Any, Callable

from device_query_service import DeviceQueryService
from mcp_client import HubitatMCPClient
from time_expressions import AT_TIME as _SHARED_AT_TIME, parse_clock as _shared_parse_clock
from tool_registry import rule_machine_proposal_error


RULE_MACHINE_GATEWAY = "hub_manage_rule_machine"

# Placeholder substituted by ConfirmedActionCoordinator with the appId the
# hub assigns to a just-created rule, once that create action has been
# executed and verified. Lets a one-time rule's follow-up self-pause action
# be built and validated at proposal time -- before the real id exists --
# without teaching the coordinator anything about rule-authoring semantics
# beyond "replace this token with the previous rule write's appId."
NEW_RULE_ID_TOKEN = "__NEW_RULE_ID__"


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
    recurring: bool = True


class RuleAuthoringService:
    """Compile supported daily and one-time device schedules without model-authored JSON."""

    _AUTHORING = re.compile(
        r"\b(?:add|build|create|make|schedule|set up|setup|write)\b"
        r"[\s\S]{0,40}\b(?:automation|rule|schedule)\b",
        re.I,
    )
    # Plain routine-control phrasing ("turn on X at 7am", "turn on X every day
    # at 7am") is a legitimate rule-authoring request on its own -- it should
    # not require the user to additionally say the word "rule". This mirrors
    # the verb set request_classification.requests_mutation() already treats
    # as control language, so a phrase recognised as a control command
    # elsewhere in the codebase is recognised consistently here too.
    _CONTROL_LEAD = re.compile(
        r"^(?:please\s+)?(?:turn|switch|lock|unlock|close|shut|open|block|"
        r"disable|allow|enable)\b",
        re.I,
    )
    _WINDOW = re.compile(
        r"\bfrom\s+(?P<start>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
        r"\s+(?:to|until|through|-)\s+"
        r"(?P<end>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
        re.I,
    )
    # "every single day" is at least as natural as "every day" and must not
    # be left to fall through to the daily-vs-one-time branch undetected --
    # see _clean_goal, which strips whichever of these actually matched.
    _DAILY = re.compile(
        r"\b(?:daily|every\s+single\s+day|every\s*day|everyday)\b", re.I
    )
    _PREFIX = re.compile(
        r"^.*?\b(?:automation|rule|schedule)\b\s+(?:that\s+|to\s+)?",
        re.I,
    )
    # request_classification.routine_control_arguments() -- the deterministic
    # matcher for *immediate* (non-scheduled) control commands -- already
    # accepts a leading "please" in its own patterns. This grammar's device-
    # name extraction patterns (_SINGLE_PATTERNS / _window_intent's patterns)
    # never accounted for it, so "please turn on X at 7am" silently fell
    # through to the generic model loop instead of being recognised, even
    # though _CONTROL_LEAD above was already written to allow "please" at
    # the gate. Stripped in _clean_goal so both the single-trigger and
    # window grammars benefit uniformly.
    _LEADING_PLEASE = re.compile(r"^please\s+", re.I)
    _AT_TIME = _SHARED_AT_TIME

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
        *,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._now = now

    @staticmethod
    def _clock(value: str) -> str | None:
        return _shared_parse_clock(value)

    @staticmethod
    def _next_occurrence_iso(clock_value: str, now: datetime) -> str:
        """Resolve a bare 'HH:MM' clock time to the next real occurrence.

        Hubitat's "Certain Time (and optional date)" trigger fires once and
        does not recur when ``atTime`` carries a specific calendar date
        (unlike the bare 'HH:MM' form used for daily rules, which recurs
        every day). If the time has already passed today, the next
        occurrence is tomorrow rather than today; this is a real clock read
        from the host, not a model guess, so it is deterministic and
        testable via the injected ``now`` callable.
        """

        hour, minute = (int(part) for part in clock_value.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.strftime("%Y-%m-%dT%H:%M:%S")

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
        goal = " ".join(goal.split()).strip(" ,.-")
        goal = cls._LEADING_PLEASE.sub("", goal)
        return goal.strip(" ,.-")

    def _intent(self, prompt: str) -> _ScheduleIntent | None:
        text = " ".join(str(prompt).strip().split())
        authored = self._AUTHORING.search(text) is not None
        # Plain control phrasing is recognised via either an "at <time>"
        # clause ("turn on X at 7am") or a "from X to Y" window clause
        # ("block internet for X from 10pm to 6am") -- the window form has
        # no "at" clause at all, so gating on _AT_TIME alone silently
        # rejected every window-style command before it ever reached the
        # window-intent branch below.
        plain_control = self._CONTROL_LEAD.match(text) is not None and (
            self._AT_TIME.search(text) is not None
            or self._WINDOW.search(text) is not None
        )
        if not authored and not plain_control:
            return None
        daily = self._DAILY.search(text) is not None
        window = self._WINDOW.search(text)
        if window is not None:
            # The auto-revert window grammar ("...from 10pm to 6am") only
            # makes sense as a recurring daily pair -- a one-shot version
            # would need its own end-date handling this grammar does not
            # attempt. Require the daily marker here, same as before.
            if not daily:
                return None
            return self._window_intent(text, window)
        return self._single_intent(text, daily=daily)

    @classmethod
    def _window_intent(cls, text: str, window: re.Match[str]) -> _ScheduleIntent | None:
        start = cls._clock(window.group("start"))
        end = cls._clock(window.group("end"))
        if start is None or end is None or start == end:
            return None

        goal = cls._clean_goal(text, window.start())
        patterns = (
            (re.compile(r"^(?:block|disable|restrict)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I),
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
            r"^(?:block|disable|restrict)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "blockInternet", "Block"),
        (re.compile(
            r"^(?:allow|enable)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "allowInternet", "Unblock"),
        # "unblock"/"restore" are only safe to treat as internet-access verbs
        # when "internet"/"access" is stated explicitly -- see the matching
        # note in request_classification.py's _ALLOW_INTERNET_EXPLICIT; both
        # words are heavily overloaded elsewhere ("restore the backup").
        (re.compile(
            r"^(?:unblock|restore)\s+(?:internet\s+(?:access\s+)?(?:for\s+)?|access\s+for\s+)"
            r"(?P<target>.+)$", re.I,
        ), "allowInternet", "Unblock"),
    )

    # Catches "turn on X on", "turn off X off", "switch on X on", "switch
    # off X off" -- a redundant trailing state word that duplicates the
    # leading verb. Live testing found "turn on livingroom light 1 on at
    # 12.05" resolved a device literally named "livingroom light 1 on":
    # `_SINGLE_PATTERNS`' first (greedy) alternative for "turn on" swallows
    # everything after it, including an accidental repeated "on" right
    # before the time clause -- a natural typo when the phrasing habit
    # "turn on X" gets combined with "X on at TIME". Only collapses when
    # the trailing word exactly matches the leading verb's state, so a
    # device genuinely named to end in "...on"/"...off" is not touched
    # unless someone also says the state word twice.
    _REDUNDANT_TRAILING_STATE = re.compile(
        r"^(?P<lead>turn\s+on|turn\s+off|switch\s+on|switch\s+off)\s+"
        r"(?P<target>.+?)\s+(?P<trail>on|off)$",
        re.I,
    )

    @classmethod
    def _drop_redundant_trailing_state(cls, goal: str) -> str:
        match = cls._REDUNDANT_TRAILING_STATE.fullmatch(goal)
        if match is None:
            return goal
        lead_state = match.group("lead").split()[-1].casefold()
        if lead_state != match.group("trail").casefold():
            return goal
        return f"{match.group('lead')} {match.group('target')}"

    def _single_intent(self, text: str, *, daily: bool) -> _ScheduleIntent | None:
        """Recognise a single trigger with no auto-revert window.

        Deliberately narrow: exactly one advertised command is required and
        verified, exactly one atomic rule is emitted. "Turn on X every day
        at 7am" (recurring) and "turn on X at 7am" (one-time) are the
        intended shapes; neither is confused with the window grammar's
        auto-reverting "turn X off from A to B" pattern, since this path
        only runs when `_window_intent` found no window clause at all.

        ``daily`` selects the trigger shape: a bare 'HH:MM' recurs every
        day on Hubitat; a full calendar-date ISO datetime fires exactly
        once. The clock time itself is parsed identically either way --
        only what gets sent as ``atTime`` differs.
        """

        at_match = self._AT_TIME.search(text)
        if at_match is None:
            return None
        at_time = self._clock(at_match.group("time"))
        if at_time is None:
            return None

        goal = self._clean_goal(text, at_match.start())
        goal = self._drop_redundant_trailing_state(goal)
        for pattern, command, label in self._SINGLE_PATTERNS:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if target:
                trigger_time = (
                    at_time if daily else self._next_occurrence_iso(at_time, self._now())
                )
                return _ScheduleIntent(
                    target=target,
                    start_time=trigger_time,
                    start_command=command,
                    start_label=label,
                    recurring=daily,
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

    # Standard Hubitat capabilities and the commands they're documented to
    # expose. Used to prefer whichever capability actually backs the
    # command(s) this rule schedules, rather than picking by fixed
    # priority regardless of what's being scheduled -- a device
    # advertising both "Switch" and "GarageDoorControl" (e.g. a garage
    # door opener that also exposes a virtual switch) previously always
    # got "Switch" as its capabilityFilter because Switch sits first in
    # the priority list, even for a scheduled "close"/"open" rule that
    # "Switch" cannot perform -- Hubitat's runCommand action requires the
    # capabilityFilter to be a capability that actually exposes the
    # command, so this silently produced a rule that could never fire the
    # intended action.
    _CAPABILITY_COMMANDS: dict[str, frozenset[str]] = {
        "Switch": frozenset({"on", "off"}),
        "Lock": frozenset({"lock", "unlock"}),
        "DoorControl": frozenset({"open", "close"}),
        "GarageDoorControl": frozenset({"open", "close"}),
        "Valve": frozenset({"open", "close"}),
    }

    @classmethod
    def _capability_filter(cls, device: dict[str, Any], commands: set[str]) -> str:
        values = device.get("capabilities") or []
        if isinstance(values, dict):
            values = list(values)
        names = []
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("capability")
            if item:
                names.append(str(item))
        # Prefer, in the device's own reported capability order, whichever
        # capability's standard commands cover every command this rule
        # schedules (start and, for a window, end).
        wanted = {str(command).casefold() for command in commands}
        for name in names:
            canonical = next(
                (
                    cap for cap in cls._CAPABILITY_COMMANDS
                    if cap.casefold() == name.casefold()
                ),
                None,
            )
            if canonical and wanted and wanted.issubset(cls._CAPABILITY_COMMANDS[canonical]):
                return canonical
        # No capability's known standard commands cover what's being
        # scheduled -- this is expected for driver-specific commands like
        # blockInternet/allowInternet, which aren't part of any standard
        # capability's documented command set. Fall back to the original
        # fixed-priority selection among the device's own capabilities.
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
    def _self_pause_action() -> dict[str, Any]:
        """Build the follow-up edit that pauses a just-created one-time rule.

        Hubitat's "Certain Time (and optional date)" trigger is documented
        to fire once and not recur when ``atTime`` carries a full calendar
        date, but a live scheduler job inspected during development still
        carried a `"recurring": true` label internally despite the dated
        trigger -- an unconfirmed ambiguity in Hubitat's own scheduler
        bookkeeping, not this app's behaviour. Rather than rely on that
        label being cosmetic, a one-time rule's action list ends with a
        native `pauseRule` action that pauses the rule itself, so even if
        the underlying job did try to fire again, the rule can never
        re-execute its actions.

        `pauseRule` requires an existing rule id for both the edit target
        (``appId``) and the action's own ``ruleIds`` -- neither of which
        exists yet at proposal time, since the rule this pauses hasn't been
        created. Both are filled with ``NEW_RULE_ID_TOKEN``, a placeholder
        `ConfirmedActionCoordinator` substitutes with the real appId
        returned by the immediately preceding create action, after
        verifying that write succeeded. `rule_machine_proposal_error` only
        checks that ``appId`` is non-empty, not that it looks numeric, so
        this validates cleanly with the token still in place.
        """

        action = {
            "tool": "hub_set_rule",
            "args": {
                "appId": NEW_RULE_ID_TOKEN,
                "addAction": {
                    "capability": "pauseRule",
                    "action": "pause",
                    "ruleIds": [NEW_RULE_ID_TOKEN],
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
        can_read_rules: bool = True,
    ) -> RuleAuthoringDecision:
        """Return a complete validated plan only for the supported grammar.

        `can_read_rules` is accepted for backward compatibility but no
        longer gates the duplicate-rule check below (default changed to
        True). It used to be tied to whether `hub_read_rules` happened to
        survive this turn's per-request tool-catalog truncation
        (`tool_limit`, default 48) -- an incidental, discovery-dependent
        signal, not a guarantee that the gateway doesn't exist. That let a
        server exposing more than `tool_limit` gateways silently skip
        duplicate-rule protection on every single schedule request whose
        catalog build happened not to include `hub_read_rules`, creating
        additional duplicate Rule Machine rules for repeated identical
        requests instead of reporting "already exists". `_existing_names()`
        calls `hub_read_rules` directly via the MCP client, not through the
        model's declared-tool schema, so it never needed this turn's
        catalog to include the tool in the first place -- and it already
        fails closed to an empty set (skipping the check, not raising) if
        the call genuinely errors.
        """

        intent = self._intent(prompt)
        if intent is None:
            return RuleAuthoringDecision(False)
        if RULE_MACHINE_GATEWAY not in available_gateways:
            return RuleAuthoringDecision(False)

        resolver = DeviceQueryService(self.mcp, self._record_evidence)
        resolve_arguments: dict[str, Any] = {"name": intent.target}
        # Scope resolution to devices that actually support blockInternet/
        # allowInternet before matching by name. Live regression: a house
        # can have both a plain power-switch and a separate network-
        # integration device sharing a name like "tv" -- ordinary name
        # resolution always prefers an exact label match, so a scheduled
        # "block the tv at 10pm" request used to resolve the switch and
        # then get flatly rejected with "does not advertise the required
        # command" instead of finding the capable device sitting right
        # there in the same candidate list. Deliberately scoped to just
        # these two commands -- on/off scheduled rules are unaffected.
        if intent.start_command.casefold() in {"blockinternet", "allowinternet"}:
            resolve_arguments["required_command"] = intent.start_command
        result = await resolver.resolve_device(resolve_arguments)
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

        capability_filter = self._capability_filter(target, required)

        if intent.end_time is None:
            if intent.recurring:
                suffix = "Daily"
            else:
                # intent.start_time is a full ISO datetime for a one-time
                # trigger (see _next_occurrence_iso); surface the resolved
                # calendar date AND time in the rule name so it is visible
                # in Rule Machine's own listing, not just in this chat
                # response. The date alone is not enough to disambiguate --
                # two distinct one-time requests for the same device and
                # command on the same day (e.g. "at 7am" and later "at
                # noon") produced identical date-only names and the second
                # request was wrongly treated as a duplicate of the first
                # and silently skipped, even though they are genuinely
                # different rules.
                date_part, _, time_part = intent.start_time.partition("T")
                suffix = f"One-time {date_part} {time_part[:5]}"
            single_name = self._rule_name(intent.start_label, target_label, suffix)
            existing = await self._existing_names() if can_read_rules else set()
            if single_name.casefold() in existing:
                return RuleAuthoringDecision(
                    True,
                    "No duplicate rule was queued because this Rule Machine rule "
                    f"already exists: **{single_name}**.",
                    rule_names=(single_name,),
                    target=target,
                )
            create_action = self._action(
                name=single_name,
                at_time=intent.start_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.start_command,
            )
            actions = (
                (create_action, self._self_pause_action())
                if not intent.recurring
                else (create_action,)
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
