"""Targeted, read-only current motion lockout settings lookup.

Do not let model tool-name selection decide whether a known, permission-gated
read gateway can be used for a specific app configuration question. This
module does not read histories, execute commands, or assert historical effects.
"""
from __future__ import annotations

import re
from typing import Any

from focal_event_provenance import current_config_facts


_APP_ID = re.compile(r"\bapp\s*(?:#|id\s*)?(\d{3,6})\b", re.I)
_EXPECTED = re.compile(
    r"\b(?:intended|expected|desired|want|requested)\b.{0,60}?"
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s*(?:-|\s)?minutes?\b", re.I,
)
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def current_lockout_config_app_id(prompt: str) -> str | None:
    """Narrow single-app current-settings intent, never a historical inquiry."""
    text = str(prompt or "")
    match = _APP_ID.search(text)
    folded = text.casefold()
    if not match or "lockout" not in folded and "lock-out" not in folded:
        return None
    if not re.search(r"\b(?:configur\w*|persisted|settings?|duration|trigger mode)\b", folded):
        return None
    if re.search(
        r"\b(?:investigat\w*|reconstruct|"
        r"at\s+\d{1,2}:\d{2}|on\s+\d{1,2}\s+\w+\s+\d{4}|"
        r"execution logs?|followed by motion|engag\w*)\b", folded,
    ):
        return None
    return match.group(1)


def _settings(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("settings")
    if not isinstance(raw, dict):
        app = config.get("app")
        raw = app.get("settings") if isinstance(app, dict) else None
    return raw if isinstance(raw, dict) else {}


def _extract_button(config: dict[str, Any]) -> str | None:
    """Read known lockout fields only; never guess a button from page prose."""
    for key in (
        "motionOffLockoutButton",
        "motionOffLockoutButtonId",
        "motionOffLockoutToggleButton",
    ):
        candidate = _settings(config).get(key)
        if isinstance(candidate, dict):
            candidate = candidate.get("value")
        if isinstance(candidate, (str, int)):
            value = str(candidate).strip()
            if value and len(value) <= 80:
                return value
    return None


async def read_current_lockout_config(
    host: Any, prompt: str, *, catalog: Any,
) -> str | None:
    app_id = current_lockout_config_app_id(prompt)
    if app_id is None:
        return None
    tool = catalog.available_tool("hub_read_apps_code")
    if tool is None:
        return (
            f"App {app_id}: current lockout settings could not be read because "
            "the permission-gated hub_read_apps_code gateway is unavailable. "
            "No configuration value has been verified in this request."
        )
    execution = await host.executor.execute(
        "hub_read_apps_code",
        {"tool": "hub_get_app_config",
         "args": {"appId": app_id, "includeSettings": True}},
        tool=tool, supports_live_claim=True,
        evidence_kind="current_persisted_app_configuration",
    )
    config = (
        execution.result.data
        if execution.success and execution.result is not None
        and isinstance(execution.result.data, dict)
        else None
    )
    facts = current_config_facts(config)
    if not facts["settingsRead"]:
        return (
            f"App {app_id}: the read gateway did not return persisted settings. "
            "The motion-off lockout duration, trigger mode and controller "
            "remain unverified from this request; no Hubitat settings changed."
        )
    duration = facts["configuredDurationMinutes"]
    mode = facts["triggerMode"]
    button = _extract_button(config)
    answer = [
        f"App {app_id} — current persisted motion-off lockout settings "
        "(read-only):",
        ("- Duration: **" + str(duration) + " minutes**."
         if duration is not None else
         "- Duration: not exposed in the returned persisted settings."),
        ("- Trigger mode: **" + mode + "**."
         if mode else
         "- Trigger mode: not exposed in the returned persisted settings."),
        ("- Controller setting: **" + button + "** (stored value; physical "
         "device identity not independently confirmed)."
         if button else
         "- Controller: not independently established from the returned "
         "persisted settings."),
    ]
    wanted = _EXPECTED.search(str(prompt))
    if wanted and duration is not None:
        token = wanted.group(1).casefold()
        expected = int(token) if token.isdecimal() else _NUMBER_WORDS[token]
        answer.append(
            f"- Your stated intention is **{expected} minutes**; "
            + ("this matches the stored duration."
               if expected == duration else
               f"the current stored value is **{duration} minutes**, "
               "so they do not match.")
        )
    answer.append(
        "These are settings at the time of this read, not proof of the "
        "settings or effective motion suppression at an earlier event. "
        "No configuration or device changes were made."
    )
    return "\n".join(answer)


__all__ = ["current_lockout_config_app_id", "read_current_lockout_config"]
