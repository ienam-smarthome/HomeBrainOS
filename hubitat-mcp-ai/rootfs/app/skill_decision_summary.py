"""Source-ranked diagnostic conclusions with separate observations and hypotheses.

Used as a safe conclusion layer when a model synthesis cannot be validated and
as a concise working interpretation of device telemetry. No live calls, writes,
model inference or guessed source claims.
"""
from __future__ import annotations

from typing import Any

from skill_investigation import build_skill_investigation


def _args(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("arguments") or {}
    if isinstance(args, dict) and isinstance(args.get("args"), dict):
        args = args["args"]
    return args if isinstance(args, dict) else {}


def causal_skill_conclusion(
    evidence: list[dict[str, Any]], question: str,
) -> dict[str, Any] | None:
    projection = build_skill_investigation(evidence, question)
    if not projection:
        return None
    commands = [
        fact for fact in projection.get("facts", [])
        if fact.get("kind") == "preceding_hubitat_command"
    ]
    if not commands:
        return None
    command = commands[0]
    producer_id = str(command.get("producerId") or "")
    app_config = []
    app_logs = []
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        leaf = str(row.get("sub_tool") or
                   (row.get("arguments") or {}).get("tool") or "")
        if str(_args(row).get("appId") or "") != producer_id:
            continue
        if leaf == "hub_get_app_config":
            app_config.append(row)
        elif leaf == "hub_get_logs":
            app_logs.append(row)
    log_rows = [
        (row.get("details") or {}).get("logCount")
        for row in app_logs
        if isinstance((row.get("details") or {}).get("logCount"), int)
    ]
    intervening = [
        event for fact in projection.get("facts", [])
        if fact.get("kind") == "intervening_state_changes"
        for event in fact.get("events", [])
    ]
    return {
        "schema": "homebrain-evidence-conclusion/v1",
        "status": "leading-recorded-candidate-unverified",
        "subject": projection.get("subject"),
        "focusTime": projection.get("focusTime"),
        "command": {
            "producer": command.get("producer"),
            "timestamp": command.get("time"),
            "command": command.get("command"),
            "delaySeconds": command.get("delaySeconds"),
            "deliveryVerified": False,
            "causationVerified": False,
        },
        "intervening": intervening[:6],
        "alternatives": [
            "independent reporting-integration action requires source-side evidence",
            "stale-state resynchronisation needs transport/state history",
        ],
        "sourceChecks": {
            "producerAppConfigChecked": bool(app_config),
            "producerAppLogsChecked": bool(app_logs),
            "producerAppLogEntries": sum(log_rows) if log_rows else (
                0 if app_logs and all(
                    isinstance((r.get("details") or {}).get("logCount"), int)
                    for r in app_logs
                ) else None
            ),
        },
        "nextCheck": (
            "Check the command producer's upstream controller or message receipt at the "
            "command timestamp and reporting integration transport around any intervening "
            "state reports. A current app setting does not prove past execution."
        ),
    }


def render_causal_skill_conclusion(
    evidence: list[dict[str, Any]], question: str,
) -> str | None:
    conclusion = causal_skill_conclusion(evidence, question)
    if not conclusion:
        return None
    command = conclusion["command"]
    lines = [
        "**Best-supported explanation:** "
        f"{command.get('producer') or 'A Hubitat source'} is the strongest "
        f"*recorded command candidate*: it issued "
        f"{command.get('command') or 'a matching command'} "
        f"{command['delaySeconds']:.3f} seconds before the reported state "
        "transition. The command invocation is verified, but its delivery "
        "and role in causing the state change are not.",
    ]
    between = conclusion["intervening"]
    if between:
        sequence = ", ".join(
            f"{str(row.get('state') or 'state').upper()} at {row.get('date')}"
            for row in between[:4]
        )
        lines.append(
            "**Important counterevidence:** An intervening state report "
            f"({sequence}) prevents a simple immediate command-to-state "
            "attribution; it does not prove a separate controller acted."
        )
    lines.append(
        "**Competing explanations:** The recorded Hubitat command, an "
        "independent reporting-integration action, and stale-state resynchronisation "
        "remain distinct hypotheses; the latter two have no verified "
        "initiator in this evidence."
    )
    checks = conclusion["sourceChecks"]
    if checks["producerAppConfigChecked"]:
        lines.append(
            "**App configuration:** Producer configuration was queried, "
            "but present-day settings cannot prove the historical initiating input."
        )
    if checks["producerAppLogsChecked"]:
        n = checks["producerAppLogEntries"]
        lines.append(
            "**App execution logs:** The producer's scoped logs were queried "
            + (f"and returned {n} log entries. " if n is not None else
               "but no verified event count was retained. ")
            + "The absence of a retained log cannot exclude past execution."
        )
    lines.append("**Best next checks (read-only):** " + conclusion["nextCheck"])
    return "\n\n".join(lines)


def telemetry_skill_conclusion(summary: dict[str, Any]) -> str | None:
    """Draw a calibrated status-level diagnosis without inventing root cause."""
    reported = summary.get("reportedDeviceState") or {}
    attrs = reported.get("reportedAttributes") or {}
    if not isinstance(attrs, dict) or (
        str(attrs.get("healthStatus") or "").casefold() != "offline"
    ):
        return None
    states = summary.get("stateEventCount")
    window = summary.get("queryWindowHours")
    no_state = isinstance(states, int) and states == 0
    text = (
        "**Working diagnosis:** Hubitat currently *reports* this device "
        "offline. "
    )
    if no_state:
        text += (
            f"No state/attribute updates were returned in the "
            f"{window}-hour history query. " if window else
            "No state/attribute updates were returned in the bounded history. "
        )
    text += (
        "This is consistent with stale or interrupted device telemetry, "
        "but the physical device, radio/network path and root cause have "
        "not been independently verified."
    )
    if str(attrs.get("mqttStatus") or "").casefold() == "connected":
        text += (
            " MQTT and device-health fields can describe different layers: "
            "a driver/broker connection can remain reported as connected "
            "without fresh telemetry from the endpoint. This is a possible "
            "explanation, not verified driver implementation or proof of "
            "the physical cause. The stored 'connected' value alone cannot "
            "establish current device reachability."
        )
    return text


__all__ = [
    "causal_skill_conclusion", "render_causal_skill_conclusion",
    "telemetry_skill_conclusion",
]
