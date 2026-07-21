from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, first_value, normalise_text, safe_debug, walk


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_INTENT_RE = re.compile(
    r"^\s*(?:please\s+)?(?P<action>pause|resume|enable|disable|run|stop)\s+(?P<target>.+?)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_PAUSE_TOOLS = ("hub_set_rule_paused", "hub_pause_rule", "hub_resume_rule")
_RUN_TOOLS = ("hub_call_rule", "hub_run_rule")


def _normalise(value: Any) -> str:
    text = normalise_text(value).lower()
    text = re.sub(r"\(\s*paused\s*\)", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _deep_value(value: Any, *names: str) -> Any:
    wanted = {name.lower() for name in names}
    for item in walk(value):
        if not isinstance(item, dict):
            continue
        for key, nested in item.items():
            if str(key).lower() in wanted and nested not in (None, ""):
                return nested
    return None


def _target_variants(value: str) -> tuple[str, ...]:
    raw = re.sub(r"\s+", " ", value.strip(" .!?"))
    candidates = [raw]
    for prefix in ("the ", "rule ", "automation ", "the rule ", "the automation "):
        if raw.lower().startswith(prefix):
            candidates.append(raw[len(prefix) :].strip())
    for candidate in list(candidates):
        for suffix in (" rule", " automation"):
            if candidate.lower().endswith(suffix):
                candidates.append(candidate[: -len(suffix)].strip())
    ordered: list[str] = []
    for candidate in candidates:
        normalised = _normalise(candidate)
        if normalised and normalised not in ordered:
            ordered.append(normalised)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class NamedRuleIntent:
    action: str
    requested_name: str
    variants: tuple[str, ...]
    explicit_rule: bool


def parse_named_rule_intent(query: str) -> NamedRuleIntent | None:
    match = _INTENT_RE.match(str(query or ""))
    if not match:
        return None
    requested_name = match.group("target").strip(" .!?")
    variants = _target_variants(requested_name)
    if not variants:
        return None
    return NamedRuleIntent(
        action=match.group("action").lower(),
        requested_name=requested_name,
        variants=variants,
        explicit_rule=bool(
            re.search(r"(?:^|\s)(?:rule|automation)(?:\s|$)", requested_name, re.IGNORECASE)
            or re.fullmatch(r"(?:rule\s+)?(?:id\s+)?#?\d+", requested_name, re.IGNORECASE)
        ),
    )


class NamedRuleController:
    """Resolve explicit named-rule commands before any device or AI route."""

    def __init__(self, application: Any) -> None:
        self.application = application
        self.mcp = application.mcp

    async def handle(self, intent: NamedRuleIntent) -> dict[str, Any] | None:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_rules", {})
        if listed.is_error:
            return self._error(
                "I could not read the Rule Machine inventory, so no rule command was sent.",
                listed,
                started,
            )

        rules = self._rule_rows(listed.data)
        matches = self._exact_matches(rules, intent)
        if len(matches) != 1:
            candidates = matches or self._possible_matches(rules, intent)
            # Verbs such as stop/enable can also describe devices. If the user did
            # not say rule/automation and the rule inventory has no plausible target,
            # preserve the existing device/AI route instead of stealing the request.
            if not candidates and not intent.explicit_rule:
                return None
            return self._clarification(intent, candidates, listed, started)

        rule = matches[0]
        tool_names = await self._available_tool_names()
        tool_name, arguments, wording = self._operation(intent.action, rule["id"], tool_names)
        if not tool_name:
            return self._error(
                wording,
                listed,
                started,
                rule=rule,
            )

        result = await self.mcp.call_tool(tool_name, arguments)
        failed = result.is_error or _deep_value(result.data, "success") is False
        if failed:
            detail = result.text or str(_deep_value(result.data, "error") or "Hubitat rejected the command")
            return self._error(
                f"No verified rule change can be reported for **{rule['name']}**: {detail}",
                result,
                started,
                rule=rule,
            )

        return self._success(intent, rule, tool_name, arguments, wording, result, started)

    async def _available_tool_names(self) -> set[str]:
        tools = await self.mcp.list_tools()
        names = {str(tool.name) for tool in tools}
        gateway_map = getattr(self.mcp, "gateway_map", None)
        if callable(gateway_map):
            names.update((await gateway_map()).keys())
        return names

    @staticmethod
    def _operation(
        action: str,
        rule_id: Any,
        available: set[str],
    ) -> tuple[str | None, dict[str, Any], str]:
        if action in {"pause", "disable", "resume", "enable"}:
            paused = action in {"pause", "disable"}
            if "hub_set_rule_paused" in available:
                verb = "pause" if paused else "resume"
                return "hub_set_rule_paused", {"ruleId": rule_id, "paused": paused}, verb
            legacy = "hub_pause_rule" if paused else "hub_resume_rule"
            if legacy in available:
                verb = "pause" if paused else "resume"
                return legacy, {"ruleId": rule_id}, verb
            return None, {}, "The connected MCP server does not advertise pause/resume rule control. No command was sent."

        if action in {"run", "stop"}:
            if "hub_call_rule" in available:
                return "hub_call_rule", {"ruleId": rule_id, "action": "rule" if action == "run" else "stop"}, action
            if action == "run" and "hub_run_rule" in available:
                return "hub_run_rule", {"ruleId": rule_id}, "run"
            return None, {}, f"The connected MCP server does not advertise {action} rule control. No command was sent."

        return None, {}, "Unsupported rule operation. No command was sent."

    @staticmethod
    def _rule_rows(value: Any) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for item in walk(value):
            if not isinstance(item, dict):
                continue
            rule_id = first_value(item, "id", "ruleId", "appId")
            name = first_value(item, "label", "name", "ruleName", "appName")
            if rule_id in (None, "") or not name:
                continue
            key = str(rule_id)
            rows[key] = {"id": rule_id, "name": normalise_text(name), "normalised": _normalise(name)}
        return sorted(rows.values(), key=lambda row: (row["name"].lower(), str(row["id"])))

    @staticmethod
    def _requested_id(intent: NamedRuleIntent) -> str | None:
        match = re.fullmatch(r"(?:rule\s+)?(?:id\s+)?#?(\d+)", _normalise(intent.requested_name))
        return match.group(1) if match else None

    @classmethod
    def _exact_matches(cls, rules: list[dict[str, Any]], intent: NamedRuleIntent) -> list[dict[str, Any]]:
        requested_id = cls._requested_id(intent)
        if requested_id is not None:
            return [rule for rule in rules if str(rule["id"]) == requested_id]
        variants = set(intent.variants)
        return [rule for rule in rules if rule["normalised"] in variants]

    @staticmethod
    def _possible_matches(rules: list[dict[str, Any]], intent: NamedRuleIntent) -> list[dict[str, Any]]:
        candidates = [
            rule
            for rule in rules
            if any(variant in rule["normalised"] or rule["normalised"] in variant for variant in intent.variants)
        ]
        return candidates[:5]

    def _clarification(
        self,
        intent: NamedRuleIntent,
        candidates: list[dict[str, Any]],
        listed: Any,
        started: float,
    ) -> dict[str, Any]:
        if candidates:
            message = "I did not find one exact rule match, so no command was sent. Possible rules:\n" + "\n".join(
                f"- {rule['name']} (Rule ID {rule['id']})" for rule in candidates
            )
        else:
            message = f"I could not find a Rule Machine rule named **{intent.requested_name}**. No command was sent."
        return {
            "success": False,
            "route": "mcp-rule-clarification",
            "intent": "automation-rule-clarification",
            "message": message,
            "display": display_payload(
                "rules",
                "Confirm rule",
                subtitle="No command has been sent",
                items=[
                    {
                        "icon": "⚙️",
                        "title": rule["name"],
                        "value": str(rule["id"]),
                        "subtitle": "Reply with the exact name or Rule ID",
                    }
                    for rule in candidates
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "candidates": candidates, "mcp": listed.data}),
        }

    def _success(
        self,
        intent: NamedRuleIntent,
        rule: dict[str, Any],
        tool_name: str,
        arguments: dict[str, Any],
        wording: str,
        result: Any,
        started: float,
    ) -> dict[str, Any]:
        if wording == "pause":
            message = f"Pause command accepted for **{rule['name']}**. It should no longer fire from its triggers."
            note = "Hubitat MCP accepted the command but does not expose a paused-state read-back in the rule inventory."
            title = "Rule pause requested"
            intent_name = "automation-rule-pause-accepted"
        elif wording == "resume":
            message = f"Resume command accepted for **{rule['name']}**. It can fire from its triggers again."
            note = "Hubitat MCP accepted the command but does not expose a paused-state read-back in the rule inventory."
            title = "Rule resume requested"
            intent_name = "automation-rule-resume-accepted"
        elif wording == "run":
            message = f"Run command accepted for **{rule['name']}**."
            note = "This performs the rule's normal evaluation and may execute its configured actions."
            title = "Rule run requested"
            intent_name = "automation-rule-run-accepted"
        else:
            message = f"Stop command accepted for **{rule['name']}**."
            note = "This requests cancellation of currently running actions and delays; it does not pause future triggers."
            title = "Rule stop requested"
            intent_name = "automation-rule-stop-accepted"
        return {
            "success": True,
            "route": "mcp-rule-control",
            "intent": intent_name,
            "message": message,
            "answered_by": "Hubitat MCP deterministic rule controller",
            "display": display_payload(
                "rule-control",
                title,
                subtitle=note,
                metrics=[
                    {"label": "Action", "value": wording.title(), "icon": "🎯"},
                    {"label": "Rule ID", "value": str(rule["id"]), "icon": "⚙️"},
                ],
                items=[{"icon": "⚙️", "title": rule["name"], "value": wording.title(), "subtitle": note}],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "requested_action": intent.action,
                    "resolved_rule": rule,
                    "tool": tool_name,
                    "arguments": arguments,
                    "mcp": result.data,
                    "post_state_verified": False if wording in {"pause", "resume"} else None,
                }
            ),
        }

    def _error(
        self,
        message: str,
        result: Any,
        started: float,
        *,
        rule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-rule-control-error",
            "intent": "automation-rule-control-error",
            "message": message,
            "display": display_payload(
                "rule-control",
                "Rule command not completed",
                subtitle="No successful rule change was verified",
                items=[{"icon": "⚠️", "title": rule["name"], "value": str(rule["id"])}] if rule else [],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(getattr(result, "data", result)),
        }


def install_named_rule_controller(application: Any) -> NamedRuleController:
    original_ask: AskHandler = application.ask
    controller = NamedRuleController(application)

    async def ask_with_named_rule_control(request: Any) -> dict[str, Any]:
        intent = parse_named_rule_intent(str(getattr(request, "query", "") or ""))
        if intent is None:
            return await original_ask(request)
        answer = await controller.handle(intent)
        if answer is None:
            return await original_ask(request)
        answer.setdefault("version", application.VERSION)
        return answer

    application.ask = ask_with_named_rule_control
    application.named_rule_controller = controller
    return controller


__all__ = [
    "NamedRuleController",
    "NamedRuleIntent",
    "install_named_rule_controller",
    "parse_named_rule_intent",
]
