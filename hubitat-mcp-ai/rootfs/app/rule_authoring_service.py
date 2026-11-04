"""Deterministic compiler for common Rule Machine schedules.

The model may identify an automation goal, but it must not invent Hubitat's
``hub_set_rule`` JSON.  This service recognises a deliberately small,
high-confidence schedule grammar, resolves the target through the shared
device resolver, verifies the requested commands, and emits validated atomic
Rule Machine calls for the existing confirmation pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from device_query_service import DeviceQueryService
from native_switch_schedule import create_dated_switch, dated_switch_proposal_error
from native_rule_inventory_source import _native_parent_from_summary
from native_rule_readiness_source import _server_version
from device_state_summary import room_name
from device_target_resolver import normalized_name, resolve_device_candidate
from hub_timezone import HubTimezoneResolver
from mcp_client import HubitatMCPClient

logger = logging.getLogger("HomeBrainOS.RuleAuthoringService")
from time_expressions import AT_TIME as _SHARED_AT_TIME, parse_clock as _shared_parse_clock
from tool_registry import rule_machine_proposal_error
from request_metrics import increment_active_metric
from rule_writer_contract import (
    NATIVE_DOCUMENT, UNKNOWN,
    installed_rule_writer_contract, legacy_rule_writer_incompatibility,
)


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
    _RELATIVE_DELAY = re.compile(
        r"\b(?:"
        r"(?:in|after)\s+(?P<amount>\d+)\s*(?P<unit>minutes?|mins?|hours?|hrs?)"
        r"|(?P<later_amount>\d+)\s*(?P<later_unit>minutes?|mins?|hours?|hrs?)\s+later"
        r")\s*[.!?]*$",
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
        internet_control_aliases: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._now = now
        self._hub_timezone = HubTimezoneResolver(mcp_client, record_evidence)
        self.internet_control_aliases = self._parse_internet_control_aliases(
            internet_control_aliases
        )

    @staticmethod
    def _parse_internet_control_aliases(value: Any | None) -> dict[str, str]:
        if value in {None, ""}:
            return {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return {}
        if not isinstance(value, dict):
            return {}
        aliases: dict[str, str] = {}
        for alias, label in value.items():
            alias_text = str(alias or "").strip()
            label_text = str(label or "").strip()
            if alias_text and label_text:
                aliases[normalized_name(alias_text)] = label_text
        return aliases

    def _configured_internet_target(
        self, requested: str, identities: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        requested_key = normalized_name(requested)
        configured_label = self.internet_control_aliases.get(requested_key)
        if configured_label is None:
            for label in self.internet_control_aliases.values():
                if normalized_name(label) == requested_key:
                    configured_label = label
                    break
        if not configured_label:
            return None
        wanted = normalized_name(configured_label)
        matches = []
        for item in identities:
            if not isinstance(item, dict):
                continue
            names = (
                item.get("label"),
                item.get("name"),
                item.get("displayName"),
                item.get("deviceLabel"),
            )
            if any(normalized_name(name) == wanted for name in names if name):
                matches.append(dict(item))
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _internet_identity_tokens(value: Any) -> set[str]:
        """Return order-independent identity tokens for Internet controls only.

        This intentionally does not change the global device resolver. Internet
        control labels commonly contain control/presentation prefixes and compact
        model names (for example ``Block PC-NucBox-M6Ultra``), while users naturally
        say the same identity as ``M6 Ultra PC``. Split camel/digit boundaries,
        ignore only non-identifying Internet-control words, and let extra candidate
        tokens remain harmless.
        """

        text = str(value or "").strip()
        if not text:
            return set()
        text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
        text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)
        text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
        ignored = {"block", "internet", "access", "control", "the", "a", "an"}
        return {token for token in text.split() if token not in ignored}

    @classmethod
    def _internet_local_target(
        cls, requested: str, identities: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
        """Resolve a unique token-subset match inside the Internet room.

        The match is intentionally scope-local and conservative: every identifying
        token supplied by the user must be present in one candidate name after the
        bounded normalization above. If more than one Internet control satisfies
        that condition, surface the ambiguity rather than guessing.
        """

        wanted = cls._internet_identity_tokens(requested)
        if not wanted:
            return None, ()
        matches: list[tuple[str, dict[str, Any]]] = []
        for item in identities:
            if not isinstance(item, dict):
                continue
            names = [
                str(item.get(field) or "").strip()
                for field in ("label", "name", "displayName", "deviceLabel")
            ]
            names = [name for name in names if name]
            matched_name = next(
                (
                    name
                    for name in names
                    if wanted.issubset(cls._internet_identity_tokens(name))
                ),
                None,
            )
            if matched_name is not None:
                matches.append((matched_name, dict(item)))
        if len(matches) == 1:
            return matches[0][1], ()
        if len(matches) > 1:
            alternatives: list[str] = []
            for name, _item in matches:
                if name not in alternatives:
                    alternatives.append(name)
            return None, tuple(alternatives[:3])
        return None, ()

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

    _ACTION_REQUEST = re.compile(
        r"^\s*(?:(?:please\s+)?(?:block|disable|restrict|allow|enable|"
        r"turn|switch|lock|unlock|close|shut|open|create|write|build|"
        r"schedule|add|make|set\s+up|setup)\b|"
        r"(?:can|could|would|will)\s+you\s+(?:please\s+)?"
        r"(?:block|disable|restrict|allow|enable|turn|switch|lock|"
        r"unlock|close|shut|open|create|write|build|schedule|add|"
        r"make|set\s+up|setup)\b)",
        re.I,
    )
    _DESIGN_ONLY = re.compile(
        r"\b(?:how\s+(?:would|could|do|can)|"
        r"(?:do\s+not|don't)\s+(?:actually\s+)?"
        r"(?:create|write|execute|apply|schedule|block)|"
        r"without\s+(?:creating|executing|applying|scheduling)|"
        r"just\s+(?:describe|explain|show)|"
        r"for\s+illustration\s+only)\b",
        re.I,
    )

    # Stateful usage budgets are not clock-time schedules. The supported
    # Rule Machine compiler can author fixed-time/daily actions, but has no
    # verified translation for an accumulated duration, pause/resume and
    # reset-on-restored-access state machine. This is a *capability boundary*,
    # not an instruction to silently invent several incomplete RM rules.
    #
    # Require evidence of an explicit rule-authoring request AND stateful
    # counter semantics; simple "block TV after 1 hour" and descriptive
    # read-only questions must stay on their existing paths.
    _STATEFUL_USAGE = re.compile(
        r"\b(?:cumulative|accumulat(?:ed|e|ing|ion)|running\s+total|"
        r"total\s+(?:of\s+)?\d+\s*(?:minutes?|mins?|hours?|hrs?)|"
        r"across\s+(?:separate\s+)?(?:sessions?|uses?)|"
        r"pause\s+(?:the\s+)?(?:timer|counter|counting)|"
        r"preserv(?:e|ing)\s+(?:the\s+)?(?:counter|elapsed|timer))\b",
        re.I,
    )
    _RESET_ON_RESTORATION = re.compile(
        r"\b(?:unblock(?:ed|ing)?|allow(?:ed|ing)?|restor(?:e|ed|ing))\b"
        r"[\s\S]{0,110}\b(?:reset|restart|resume|fresh|new|zero|60.minute|one.hour|1\s*(?:hour|hr))\b"
        r"|\b(?:reset|restart|resume|fresh|new)\b"
        r"[\s\S]{0,110}\b(?:unblock(?:ed|ing)?|restor(?:e|ed|ing)|"
        r"allow(?:ed|ing)?)\b",
        re.I,
    )

    @classmethod
    def is_read_only_rule_design_request(cls, prompt: str) -> bool:
        """Explicit review/proposal-only authoring: no present write authority.

        The user can discuss a desired future rule while withholding authority
        to create it. Require a rule subject, positive review objective AND a
        separate explicit no-write instruction. Fail closed on independent
        commands to modify state in the same prompt; never erase such writes.
        """
        text = " ".join(str(prompt or "").split())
        from ai_investigation_routing import active_request_interpretation
        interpreted = active_request_interpretation(prompt)
        if interpreted is not None and interpreted.objective is not None:
            # This is an objective interpretation, NOT write permission.
            return interpreted.objective == "rule_design_review"
        if not re.search(r"\b(?:rule\s*machine|automation|rule)\b", text, re.I):
            return False
        # "automation behaviour" plus "read-only; do not change anything"
        # describes an incident investigation, not a new-rule proposal.
        # Only positive future design intent may enable rule-design mode.
        from targeted_rule_scope_policy import is_existing_rule_verification_request
        existing_rule_review = is_existing_rule_verification_request(text)
        future_design = re.search(
            r"(?i)\b(?:design|draft|propose|plan|outline|build|create|"
            r"set\s*up|implement)\s+(?:(?:a|an|new|the|my|proposed)\s+){0,3}"
            r"(?:rule\s*machine\s+)?(?:rule|automation)\b"
            r"|\b(?:want|would\s+like|need|intend)\b"
            r".{0,90}\b(?:new\s+)?(?:rule|automation)\b"
            r"|\b(?:review|evaluate|check|inspect)\s+"
            r"(?:(?:the|my|a|proposed|new)\s+){0,3}"
            r"(?:rule|automation)\s+(?:design|proposal|plan)\b"
            r"|\b(?:review|evaluate|check|inspect)\s+"
            r"(?:(?:the|my|this|a)\s+)?(?:proposed|new|future)\s+"
            r"(?:rule|automation)\b"
            r"|\b(?:rule|automation)\s+(?:design|proposal|plan)\b",
            text,
        )
        # Do not interpret the prohibition itself ("do not create a new
        # automation") as a positive request to design one.
        if future_design and re.search(
            r"(?i)\b(?:do\s+not|don't|never|without)\s*$",
            text[max(0, future_design.start() - 30):future_design.start()],
        ):
            future_design = None
        if not (future_design or existing_rule_review):
            return False
        review = re.search(
            r"\b(?:read[ -]?only|proposal[ -]?only|review|inspect|"
            r"implementation\s+plan|show\s+(?:me\s+)?(?:the\s+)?"
            r"(?:plan|proposal)|design\s+only)\b", text, re.I,
        )
        no_write = re.search(
            r"\b(?:do\s+not|don't|never)\s+"
            r"(?:(?:actually|yet|now)\s+)?"
            r"(?:create|write|modify|change|disable|enable|execute|"
            r"run|queue|make|apply|install|schedule)\b"
            r"|\b(?:i\s+will|i'll)\s+"
            r"(?:explicitly\s+)?authori[sz]e\s+"
            r"(?:creation|changes|writing)\s+(?:later|separately)\b",
            text, re.I,
        )
        if not (review and no_write):
            return False
        # An actual independent imperative elsewhere in the prompt keeps
        # normal write-intent/confirmation semantics. Future desired-state
        # clauses ("if motion becomes active, cancel ...") are not commands.
        independent = re.search(
            r"(?i)(?:^|[.!?;]\s+|\b(?:also|then)\s+)"
            r"(?:please\s+)?(?:create|write|modify|change|disable|"
            r"enable|delete|remove|turn|switch|block|unblock|"
            r"restart|apply|execute|run|set)\b"
            r"[^.!?;]{0,70}\b(?:now|immediately|today)\b",
            text,
        )
        if independent:
            return False
        if re.match(
            r"(?i)^\s*(?:please\s+)?(?:create|write|modify|"
            r"change|disable|enable|turn|switch|block|unblock|"
            r"delete|remove|apply|execute)\b",
            text,
        ):
            return False
        return True

    @classmethod
    def is_existing_rule_review_first(cls, prompt: str) -> bool:
        """An explicitly conditional create must inspect an existing rule first.

        This recognises an entire user *workflow*, not arbitrary mentions of
        "rule" or a ban on creating. A new rule must not be proposed when the
        user says to inspect the installed equivalent and avoid duplication.
        Stage one is read-only; any later write needs new confirmation and
        independent validation. Unrelated immediate writes retain their
        ordinary write path.
        """
        text = " ".join(str(prompt or "").strip().split())
        # "Do not create a duplicate" is a constraint on a conditional
        # creation, NOT a prohibition on inspecting the existing rule.
        if not cls._ACTION_REQUEST.match(text):
            return False
        first_review = re.search(
            r"\b(?:first\s+(?:inspect|review|check|verify|audit|examine)|"
            r"(?:inspect|review|check|verify|audit|examine)\s+first|"
            r"before\s+(?:creating|adding|building)\b.{0,100}"
            r"(?:inspect|review|check|verify))\b",
            text, re.I,
        )
        existing = re.search(r"\b(?:existing|already\s+(?:installed|created|present))\s+"
                             r"(?:rule|automation|app)\b", text, re.I)
        avoid_duplicate = re.search(
            r"\b(?:do\s+not|don't|avoid|never)\s+"
            r"(?:creat(?:e|ing)\s+(?:a\s+)?duplicate|duplicate\b|create\s+(?:another|a\s+new)\b)"
            r"|\bif\s+(?:that|the|an?\s+existing)\s+(?:rule|automation)\b"
            r".{0,140}\b(?:do\s+not|don't|avoid)\b.{0,35}\b(?:create|duplicate)\b",
            text, re.I,
        )
        # This branch must not suppress an independent requested device/rule
        # mutation such as "then pause the old rule" or "also block internet".
        extra_change = re.search(
            r"\b(?:then|also|and\s+also)\s+"
            r"(?:please\s+)?(?:pause|disable|enable|delete|remove|"
            r"block|unblock|modify|change|turn\s+off|turn\s+on)\b",
            text, re.I,
        )
        return bool(first_review and existing and avoid_duplicate and not extra_change)

    @classmethod
    def is_stateful_authoring_request(cls, prompt: str) -> bool:
        """Route compound usage budgets to live capability-driven authoring.

        This is an intake classifier, NOT a proof the connected RM supports
        every requested operation. The actual read-only guide preflight and
        confirmation pipeline decide what can be safely proposed. Do not
        restrict this to a particular TV, room, app or variable name.
        """
        text = " ".join(str(prompt or "").strip().split())
        return bool(
            cls._ACTION_REQUEST.match(text)
            and not cls._DESIGN_ONLY.search(text)
            and re.search(r"\b(?:automation|rule|controller)\b", text, re.I)
            and cls._STATEFUL_USAGE.search(text)
            and cls._RESET_ON_RESTORATION.search(text)
        )

    def is_action_request(self, prompt: str) -> bool:
        """Explicit user scheduling authority, independent of AI task labels.

        Read-only design questions may match the authoring grammar because
        they quote valid rule syntax. They must never reach the Hubitat rule
        write confirmation path. An imperative with a valid time clause is
        authoritative even if a model classifier calls it 'propose'.
        """
        text = str(prompt or "").strip()
        return bool(
            self._ACTION_REQUEST.match(text)
            and not self._DESIGN_ONLY.search(text)
            and self.matches_request(text)
        )

    def matches_request(self, prompt: str) -> bool:
        """Return whether the bounded deterministic authoring grammar applies."""

        return self._intent(prompt) is not None

    def _intent(
        self, prompt: str, *, now: datetime | None = None
    ) -> _ScheduleIntent | None:
        text = " ".join(str(prompt).strip().split())
        authored = self._AUTHORING.search(text) is not None
        relative = self._RELATIVE_DELAY.search(text)
        # Plain control phrasing is recognised via a clock clause, a recurring
        # window, or a bounded relative delay. Relative delays are compiled
        # into a dated one-time trigger instead of leaving the model to invent
        # a Delay action inside the rule.
        plain_control = self._CONTROL_LEAD.match(text) is not None and (
            self._AT_TIME.search(text) is not None
            or self._WINDOW.search(text) is not None
            or relative is not None
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
        if relative is not None:
            if daily:
                return None
            return self._relative_intent(text, relative, now=now)
        return self._single_intent(text, daily=daily, now=now)

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

    @staticmethod
    def _relative_minutes(match: re.Match[str]) -> int | None:
        amount_text = match.group("amount") or match.group("later_amount")
        unit = match.group("unit") or match.group("later_unit") or "minutes"
        if not amount_text:
            return None
        amount = int(amount_text)
        if amount <= 0:
            return None
        return amount * (60 if unit.casefold().startswith(("hour", "hr")) else 1)

    @staticmethod
    def _relative_next_minute(current: datetime, minutes: int) -> datetime:
        """Delay by real elapsed minutes, then CEIL to the next minute.

        Work on UTC instants for aware clocks: ordinary ZoneInfo wall-clock
        addition can otherwise land in a nonexistent spring DST hour.
        A naive injected test clock retains its existing wall-clock basis.
        """
        if current.tzinfo is not None:
            target_utc = current.astimezone(timezone.utc) + timedelta(minutes=minutes)
            if target_utc.second or target_utc.microsecond:
                target_utc = target_utc.replace(second=0, microsecond=0) + timedelta(minutes=1)
            if (target_utc - current.astimezone(timezone.utc)).total_seconds() <= 60:
                # The native writer requires a strictly >60s lead time;
                # a one-minute delay requested on an exact minute boundary
                # must land on the *following* whole-minute opportunity.
                target_utc += timedelta(minutes=1)
            return target_utc.astimezone(current.tzinfo)
        target = current + timedelta(minutes=minutes)
        if target.second or target.microsecond:
            target = target.replace(second=0, microsecond=0) + timedelta(minutes=1)
        if (target - current).total_seconds() <= 60:
            target += timedelta(minutes=1)
        return target

    def _relative_intent(
        self,
        text: str,
        relative: re.Match[str],
        *,
        now: datetime | None = None,
    ) -> _ScheduleIntent | None:
        minutes = self._relative_minutes(relative)
        if minutes is None:
            return None
        goal = self._clean_goal(text, relative.start())
        goal = self._drop_redundant_trailing_state(goal)
        for pattern, command, label in self._SINGLE_PATTERNS:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if not target:
                continue
            current = now if now is not None else self._now()
            trigger = self._relative_next_minute(current, minutes)
            return _ScheduleIntent(
                target=target,
                start_time=trigger.strftime("%Y-%m-%dT%H:%M:%S"),
                start_command=command,
                start_label=label,
                recurring=False,
            )
        return None

    def _single_intent(
        self, text: str, *, daily: bool, now: datetime | None = None
    ) -> _ScheduleIntent | None:
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
                    at_time
                    if daily
                    else self._next_occurrence_iso(
                        at_time, now if now is not None else self._now()
                    )
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
        name = f"{base} ({suffix})"
        # Only this explicit ownership prefix lets the nightly cleanup
        # distinguish HomeBrain-created one-shots from user-authored rules
        # that happen to use the old descriptive suffix.
        return f"HB one-shot | {name}" if suffix.startswith("One-time ") else name

    @staticmethod
    def _one_shot_clock_error(start_time: str, now_local: datetime) -> str | None:
        """Do not create a dated trigger too soon or in a DST gap/fold."""
        if now_local.tzinfo is None:
            return "time_in_past_or_too_soon"
        try:
            wall = datetime.fromisoformat(start_time)
        except ValueError:
            return "time_in_past_or_too_soon"
        if wall.tzinfo is not None:
            return "time_in_past_or_too_soon"
        one = wall.replace(tzinfo=now_local.tzinfo, fold=0)
        two = wall.replace(tzinfo=now_local.tzinfo, fold=1)
        # Without an independently verified offset/epoch field the native
        # date editor cannot disambiguate either occurrence of a repeated
        # hour. Likewise refuse nonexistent spring-time wall clock values.
        if one.utcoffset() != two.utcoffset():
            return "native_oneshot_dst_time_ambiguous"
        if one.astimezone(timezone.utc).astimezone(now_local.tzinfo).replace(
            tzinfo=None
        ) != wall:
            return "native_oneshot_dst_time_ambiguous"
        delta = (
            one.astimezone(timezone.utc)
            - now_local.astimezone(timezone.utc)
        ).total_seconds()
        if delta <= 60:
            return "time_in_past_or_too_soon"
        return None

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

    async def _existing_names(self) -> set[str] | None:
        arguments = {"tool": "hub_list_rules", "args": {}}
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_read_rules", arguments)
        except Exception as exc:
            logger.warning("Could not read existing rule names", exc_info=True)
            self._record_evidence(
                "hub_read_rules",
                arguments,
                success=False,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                supports_live_claim=True,
                evidence_kind="rule_duplicate_check",
            )
            return None
        success = not result.is_error and not (
            isinstance(result.data, dict) and result.data.get("success") is False
        )
        rows = self._rule_rows(result.data)
        # A gateway discovery/metadata response is NOT an empty rules
        # inventory. The older parser treated any successful object with no
        # rules array as an empty set, allowing duplicate active rules after
        # the wrong read gateway answered with {gateway,mode,tools}.
        def has_rule_collection(value: Any, depth: int = 0) -> bool:
            if depth > 4 or not isinstance(value, dict):
                return False
            if isinstance(value.get("rules"), list):
                return True
            return any(
                has_rule_collection(value.get(key), depth + 1)
                for key in ("data", "result", "output")
            )
        if not has_rule_collection(result.data):
            success = False
        self._record_evidence(
            "hub_read_rules",
            arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=(
                f"{len(rows)} existing Rule Machine rules checked for duplicates"
                if success else "Rule inventory unavailable: no actual rules array"
            ),
            supports_live_claim=True,
            evidence_kind="rule_duplicate_check",
        )
        if not success:
            return None
        return {
            str(item.get("name") or item.get("label") or "").strip().casefold()
            for item in rows
            if item.get("name") or item.get("label")
        }

    @staticmethod
    def _create_name(arguments: dict[str, Any]) -> str | None:
        """Return the name only for a direct new-rule proposal."""

        if arguments.get("tool") != "hub_set_rule":
            return None
        payload = arguments.get("args")
        if not isinstance(payload, dict) or payload.get("appId") not in {None, ""}:
            return None
        source = (
            payload.get("args")
            if payload.get("operation") == "create" else payload
        )
        name = str(source.get("name") or "").strip() if isinstance(source, dict) else ""
        return name or None

    async def _rule_writer_contract(self) -> str:
        """One read-only installed-server capability probe; no write or schema guess."""
        arguments = {"section": "set_rule_reference"}
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_get_tool_guide", arguments)
            contract = installed_rule_writer_contract(result)
        except Exception:
            logger.warning("Installed Rule Machine guide unavailable", exc_info=True)
            contract = "unknown"
        # A successfully read guide is not a successful authoring request.
        # Distinguish a known incompatible contract from a failed/untrusted
        # guide and never advertise either refusal as a green success.
        if contract == NATIVE_DOCUMENT:
            increment_active_metric("rule_writer_native_unsupported")
        elif contract == UNKNOWN:
            increment_active_metric("rule_writer_contract_unverified")
        self._record_evidence(
            "hub_get_tool_guide", arguments,
            success=contract != "unknown",
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"Rule Machine writer contract: {contract}",
            supports_live_claim=True,
            evidence_kind="rule_writer_contract_check",
        )
        return contract


    @staticmethod
    def _native_date_supported(mcp: Any) -> bool:
        """Only installed MCP initialize identity attests upstream #575."""
        version = _server_version(mcp)
        if version is None:
            return False
        parts = version.split("-", 1)[0].split("+", 1)[0].split(".")
        return len(parts) == 3 and tuple(int(x) for x in parts) >= (5, 1, 6)

    async def _native_parent_id(self) -> int | None:
        """Resolve a native Rule Machine parent using two read-only sources."""
        try:
            listed = await self.mcp.call_tool("hub_read_apps_code", {
                "tool": "hub_list_apps",
                "args": {"scope": "instances"},
            })
            data = listed.data if not listed.is_error and isinstance(listed.data, dict) else {}
            rows = data.get("apps")
            if (not isinstance(rows, list) or len(rows) > 5000
                    or data.get("truncated") is True or data.get("nextCursor")
                    or (type(data.get("count")) is int
                        and data["count"] != len(rows))):
                return None
            candidates = [
                row for row in rows if isinstance(row, dict)
                and row.get("name") == "Rule Machine"
                and row.get("type") == "Rule Machine"
                and row.get("user") is False
                and row.get("parentId") in (None, "")
                and str(row.get("id") or "").isdigit()
            ]
            if len(candidates) != 1:
                return None
            parent_id = int(candidates[0]["id"])
            candidate_type = candidates[0].get("appTypeId")
            if not str(candidate_type or "").isdigit():
                return None
            detail_result = await self.mcp.call_tool("hub_read_apps_code", {
                "tool": "hub_get_app_config",
                "args": {"appId": str(parent_id), "summary": True},
            })
            detail = detail_result.data if not detail_result.is_error and isinstance(detail_result.data, dict) else {}
            verified, _gap = _native_parent_from_summary(
                detail,
                candidate_id=str(parent_id),
                candidate_type_id=str(candidate_type),
            )
            return parent_id if verified is not None else None
        except Exception:
            return None

    async def _native_guide_key(self) -> str | None:
        """Read the installed acknowledgement key, never invent one."""
        try:
            guide = await self.mcp.call_tool(
                "hub_get_tool_guide", {"section": "set_rule_reference"}
            )
            if guide.is_error:
                return None
            def flatten(value: Any) -> str:
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    return "\n".join(
                        flatten(value[k]) for k in
                        ("content", "text", "guide", "result", "data")
                        if k in value
                    )
                if isinstance(value, list):
                    return "\n".join(flatten(v) for v in value)
                return ""
            match = re.search(
                r"I-HAVE-READ-THE-GUIDE-set_rule_reference-[0-9a-fA-F]+",
                flatten(guide.data),
            )
            return match.group(0) if match else None
        except Exception:
            return None

    async def duplicate_create_error(
        self,
        arguments: dict[str, Any],
    ) -> str | None:
        return await self.duplicate_create_group_error([arguments])

    async def duplicate_create_group_error(
        self,
        arguments: list[dict[str, Any]],
    ) -> str | None:
        """Fail closed when a new Rule Machine name cannot be proved unique.

        This is intentionally reusable by both proposal-time validation and
        confirmation replay.  Checking twice closes the time-of-check/time-of-
        use window: another request may create the same rule while the user is
        reading the confirmation prompt.
        """

        names = [
            name
            for item in arguments
            if (name := self._create_name(item)) is not None
        ]
        if not names:
            return None
        # Confirmation replay is a fresh trust boundary. The server may have
        # upgraded while the queued proposal was awaiting approval. Check the
        # installed guide before ANY create write, not just at proposal time.
        contract = await self._rule_writer_contract()
        native_candidates = [
            item.get("tool") == "hub_set_rule"
            and isinstance(item.get("args"), dict)
            and item["args"].get("operation") == "create"
            for item in arguments
        ]
        if any(native_candidates):
            if not all(native_candidates) or contract != NATIVE_DOCUMENT:
                return "Native Rule Machine writer contract changed. No rule was created."
            if not self._native_date_supported(self.mcp):
                return (
                    "The installed MCP server does not attest the 5.1.6 native "
                    "dated-trigger fix. No rule was created."
                )
            verified_parent = await self._native_parent_id()
            if verified_parent is None:
                return "The native Rule Machine parent is not verified. No rule was created."
            for item in arguments:
                payload = item["args"]
                invalid = dated_switch_proposal_error(payload)
                if invalid is not None:
                    return invalid
                if payload["args"]["parent_id"] != verified_parent:
                    return (
                        "The queued native parent differs from the freshly "
                        "verified Rule Machine parent. No rule was created."
                    )
        else:
            incompatible = legacy_rule_writer_incompatibility(contract)
            if incompatible:
                return incompatible
        normalized = [name.casefold() for name in names]
        duplicates_in_group = sorted(
            {
                name
                for name in names
                if normalized.count(name.casefold()) > 1
            }
        )
        if duplicates_in_group:
            rendered = ", ".join(f"**{name}**" for name in duplicates_in_group)
            return (
                "The Rule Machine action group was cancelled because it contains "
                f"the same new rule name more than once: {rendered}. Nothing was "
                "queued or executed."
            )
        existing = await self._existing_names()
        if existing is None:
            return (
                "The Rule Machine action was cancelled because HomeBrain could "
                "not verify the current rule list. Nothing was queued or "
                "executed; retry after the hub read succeeds."
            )
        collisions = [name for name in names if name.casefold() in existing]
        if collisions:
            rendered = ", ".join(f"**{name}**" for name in collisions)
            return (
                "No duplicate rule was created because the following Rule Machine "
                f"rule{'s' if len(collisions) != 1 else ''} already exist"
                f"{'s' if len(collisions) == 1 else ''}: {rendered}. Nothing was "
                "executed."
            )
        return None

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

        # First pass is a no-I/O grammar gate. Only genuine deterministic
        # scheduling requests pay for authoritative timezone resolution.
        intent = self._intent(prompt)
        if intent is None:
            return RuleAuthoringDecision(False)
        if RULE_MACHINE_GATEWAY not in available_gateways:
            return RuleAuthoringDecision(False)

        # The installed server may now expose native document creation rather
        # than the shortcut fields our deterministic compiler emits. Consult
        # its own read-only guide before resolving a target or queuing an
        # impossible/unsafe confirmed write. Never silently translate fields.
        installed_contract = await self._rule_writer_contract()
        native_mode = installed_contract == NATIVE_DOCUMENT
        incompatible = legacy_rule_writer_incompatibility(installed_contract)
        if native_mode:
            if intent.recurring or intent.end_time is not None:
                return RuleAuthoringDecision(
                    True,
                    legacy_rule_writer_incompatibility(NATIVE_DOCUMENT)
                    or "Recurring native schedule not yet verified; no write queued.",
                )
            if not self._native_date_supported(self.mcp):
                return RuleAuthoringDecision(
                    True,
                    "native_oneshot_date_field_unverified: Installed native MCP "
                    "Rule Server version 5.1.6 or later has not been verified "
                    "through MCP initialize. Native operation=create requires "
                    "an independently verified parent_id and typed trigger "
                    "fields. Upgrade/reconnect before scheduling. "
                    "No rule write was queued or executed.",
                )
        elif incompatible:
            return RuleAuthoringDecision(True, incompatible)

        if not intent.recurring:
            runtime_now = self._now()
            if runtime_now.tzinfo is None:
                # The Home Assistant add-on container runs UTC in production.
                # Treat a naive injected/runtime clock as UTC before converting
                # it through the authoritative Hubitat location timezone.
                runtime_now = runtime_now.replace(tzinfo=timezone.utc)
            hub_now, _timezone_name, _timezone_source = (
                await self._hub_timezone.now_in_hub_timezone(lambda: runtime_now)
            )
            intent = self._intent(prompt, now=hub_now)
            if intent is None:
                return RuleAuthoringDecision(False)
            time_error = self._one_shot_clock_error(intent.start_time, hub_now)
            if time_error is not None:
                return RuleAuthoringDecision(
                    True,
                    f"{time_error}: The requested one-time wall clock is "
                    "ambiguous, in the past, or too close to the current "
                    "Hubitat-local time to schedule safely. No rule write "
                    "was queued or executed.",
                )

        resolver = DeviceQueryService(self.mcp, self._record_evidence)
        internet_access = intent.start_command.casefold() in {
            "blockinternet", "allowinternet"
        }
        resolve_arguments: dict[str, Any] = {"name": intent.target}

        if internet_access:
            # Internet access controls are ordinary Hubitat Switch devices in
            # the authoritative Internet room. Their user-facing semantics are
            # intentionally inverted from the literal switch wording:
            # switch=on means Internet allowed; switch=off means Internet
            # blocked. Do not require optional blockInternet/allowInternet
            # driver commands. First scope fuzzy identity matching to the
            # Internet room so a normal device such as "Google TV Streamer
            # (ADB)" cannot win merely because its label is a closer match.
            identity_started = time.monotonic()
            try:
                # Identity metadata remains authoritative for longer than live
                # state. Reuse a fresh complete structural snapshot first instead
                # of forcing the 12-second device-manifest cache to refresh. This
                # keeps scheduled Internet resolution fast after any recent
                # inventory/live-context read while still falling back to one
                # bounded refresh when no fresh identity snapshot exists.
                identities: list[dict[str, Any]] = []
                identity_source = "identity refresh"
                identity_peek = getattr(self.mcp, "peek_device_identities", None)
                if callable(identity_peek):
                    try:
                        identities = list(identity_peek() or [])
                    except Exception:
                        identities = []
                    if identities:
                        identity_source = "identity cache"
                if not identities:
                    identity_reader = getattr(self.mcp, "get_cached_devices", None)
                    if not callable(identity_reader):
                        identity_reader = getattr(self.mcp, "get_device_identities", None)
                    if not callable(identity_reader):
                        raise AttributeError("No device identity reader is available")
                    identities = list(await identity_reader() or [])
                    identity_source = "identity refresh"
            except Exception as exc:
                self._record_evidence(
                    "homebrain_device_inventory",
                    {"group": "Internet"},
                    success=False,
                    elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                    summary=f"Internet-group identity lookup failed: {type(exc).__name__}",
                    supports_live_claim=True,
                    evidence_kind="deterministic_internet_target_scope",
                )
                return RuleAuthoringDecision(
                    True,
                    "I could not read the authoritative **Internet** device group. "
                    "Nothing was queued.",
                )

            internet_candidates = [
                item
                for item in identities
                if isinstance(item, dict)
                and str(room_name(item) or "").casefold() == "internet"
            ]
            configured_target = self._configured_internet_target(
                intent.target,
                [item for item in identities if isinstance(item, dict)],
            )
            if configured_target is not None:
                scoped_target = configured_target
                scoped_alternatives: tuple[str, ...] = ()
                scope_source = "configured alias"
            else:
                local_target, local_alternatives = self._internet_local_target(
                    intent.target, internet_candidates
                )
                if local_target is not None:
                    scoped_target = local_target
                    scoped_alternatives = ()
                    scope_source = "Internet room local-token match"
                elif local_alternatives:
                    scoped_target = None
                    scoped_alternatives = local_alternatives
                    scope_source = "Internet room local-token ambiguity"
                else:
                    scoped = resolve_device_candidate(intent.target, internet_candidates)
                    scoped_target = scoped.target
                    scoped_alternatives = scoped.alternatives
                    scope_source = "Internet room fuzzy fallback"
            self._record_evidence(
                "homebrain_device_inventory",
                {"group": "Internet"},
                success=scoped_target is not None,
                elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                summary=(
                    f"{len(internet_candidates)} Internet-group candidates; "
                    f"configured_aliases={len(self.internet_control_aliases)}; "
                    f"identity_source={identity_source}; "
                    f"source={scope_source}; "
                    f"target={'resolved' if scoped_target is not None else 'unresolved'}"
                ),
                supports_live_claim=True,
                evidence_kind="deterministic_internet_target_scope",
            )
            if scoped_target is None:
                if scoped_alternatives:
                    return RuleAuthoringDecision(
                        True,
                        "I could not uniquely match that request to an Internet-control "
                        "device. Possible matches: "
                        + ", ".join(scoped_alternatives[:3])
                        + ". Nothing was queued.",
                    )
                return RuleAuthoringDecision(
                    True,
                    f"I could not match **{intent.target}** to a device in the "
                    "authoritative **Internet** group or configured Internet aliases. "
                    "Nothing was queued.",
                )

            selected_label = str(
                scoped_target.get("label")
                or scoped_target.get("name")
                or intent.target
            ).strip()
            actual_start_command = (
                "off"
                if intent.start_command.casefold() == "blockinternet"
                else "on"
            )
            actual_end_command = intent.end_command
            if intent.end_command is not None:
                if intent.end_command.casefold() == "blockinternet":
                    actual_end_command = "off"
                elif intent.end_command.casefold() == "allowinternet":
                    actual_end_command = "on"

            # Re-read the selected control surface by its authoritative label
            # and verify the real Switch command we will schedule. This keeps
            # command verification on the existing off/on interface even when optional driver-specific Internet commands are also advertised.
            resolve_arguments = {
                "name": selected_label,
                "required_command": actual_start_command,
            }
            result = await resolver.resolve_device(resolve_arguments)
            intent = _ScheduleIntent(
                target=intent.target,
                start_time=intent.start_time,
                start_command=actual_start_command,
                start_label=intent.start_label,
                end_time=intent.end_time,
                end_command=actual_end_command,
                end_label=intent.end_label,
                recurring=intent.recurring,
            )
        else:
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
            required_command = str(resolve_arguments.get("required_command") or "").strip()
            if required_command:
                return RuleAuthoringDecision(
                    True,
                    f"I could not resolve a Hubitat device matching **{intent.target}** "
                    f"that advertises the required command: {required_command.casefold()}. "
                    "Nothing was queued.",
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
            if existing is None:
                return RuleAuthoringDecision(
                    True,
                    "The rule was not queued because HomeBrain could not verify "
                    "the current Rule Machine list. Retry after the hub read "
                    "succeeds.",
                    rule_names=(single_name,),
                    target=target,
                )
            if single_name.casefold() in existing:
                return RuleAuthoringDecision(
                    True,
                    "No duplicate rule was queued because this Rule Machine rule "
                    f"already exists: **{single_name}**.",
                    rule_names=(single_name,),
                    target=target,
                )
            if native_mode:
                parent_id = await self._native_parent_id()
                guide_key = await self._native_guide_key()
                if parent_id is None:
                    return RuleAuthoringDecision(
                        True,
                        "The native Rule Machine parent is not source-verified. "
                        "No rule was queued.",
                        rule_names=(single_name,), target=target,
                    )
                # The upstream guide acknowledges writes only when that
                # setting is enabled. Do not invent a key when not advertised:
                # upstream will refuse a required missing key before writing.
                try:
                    wall = datetime.fromisoformat(intent.start_time)
                    if wall.tzinfo is not None:
                        raise ValueError("expected hub-local wall clock")
                    local_at = wall.replace(tzinfo=hub_now.tzinfo)
                    create_action = create_dated_switch(
                        name=single_name, parent_id=parent_id,
                        device_id=str(device_id), command=intent.start_command,
                        hub_local_at=local_at, best_practice_key=guide_key,
                    )
                except (TypeError, ValueError):
                    return RuleAuthoringDecision(
                        True,
                        "Native dated Switch candidate could not be verified. "
                        "No rule was queued.", target=target,
                    )
            else:
                create_action = self._action(
                    name=single_name,
                    at_time=intent.start_time,
                    device_id=device_id,
                    capability_filter=capability_filter,
                    command=intent.start_command,
                )
            # One-time rules are deliberately left with only their dated
            # trigger and device action. The nightly HomeBrain cleanup removes
            # expired generated rules after the safety grace period; self-pause
            # proved unreliable on the live hub and is no longer required.
            actions = (create_action,)
            return RuleAuthoringDecision(
                True,
                actions=actions,
                rule_names=(single_name,),
                target=target,
            )

        start_name = self._rule_name(intent.start_label, target_label, "Start")
        end_name = self._rule_name(intent.start_label, target_label, "End")
        existing = await self._existing_names() if can_read_rules else set()
        if existing is None:
            return RuleAuthoringDecision(
                True,
                "The rules were not queued because HomeBrain could not verify "
                "the current Rule Machine list. Retry after the hub read "
                "succeeds.",
                rule_names=(start_name, end_name),
                target=target,
            )
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
