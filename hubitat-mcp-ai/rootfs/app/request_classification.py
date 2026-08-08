"""Pure text-classification helpers extracted from UnifiedMCPAgent.

These functions look only at a prompt string (plus, for `matches`, a caller-
supplied term set) and return a plain value. None of them read or mutate
agent state, so they're safe to unit test and reuse in isolation from the
orchestrator's tool-calling loop. See docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import re
from typing import Any

_STRONG_CONTROL_VERBS = {
    "create", "delete", "disable", "enable", "install", "pause", "reboot", "remove",
    "restart", "resume", "set", "shutdown", "start", "stop", "toggle",
    "unlock", "update", "write",
}


def matches(prompt: str, terms: set[str]) -> bool:
    """True if any term (optionally pluralized with s/es) appears as a word in prompt."""

    value = prompt.lower()
    return any(
        re.search(rf"\b{re.escape(term.lower())}(?:s|es)?\b", value) is not None
        for term in terms
    )


def requests_mutation(prompt: str) -> bool:
    """True if the prompt reads as a command to change device/hub state."""

    value = " ".join(prompt.lower().split())
    tokens = re.findall(r"[a-z0-9]+", value)
    if tokens and tokens[0] in _STRONG_CONTROL_VERBS | {"close", "lock", "open"}:
        return True
    if (
        re.search(r"\b(?:turn|switch|power)\b.+\b(?:on|off)\b", value)
        or re.search(r"\b(?:turn|switch|power)\s+(?:on|off)\b", value)
    ):
        return True
    if re.search(
        r"\bplease\s+(?:close|create|delete|disable|enable|install|lock|open|pause|"
        r"reboot|remove|restart|resume|set|shutdown|start|stop|toggle|"
        r"unlock|update|write)\b",
        value,
    ):
        return True
    return False


_FIRMWARE_INSTALL = re.compile(
    r"^\s*(?:please\s+)?(?:install|apply|do|run|start)\s+(?:the\s+)?"
    r"(?:available\s+)?(?:hub(?:itat)?\s+)?firmware(?:\s+update)?\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?update\s+(?:the\s+)?hub(?:itat)?\s+firmware\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?upgrade\s+(?:the\s+)?(?:hub(?:itat)?\s+)?firmware\s*[?.!]*\s*$",
    re.I,
)


def parse_firmware_install_intent(prompt: str) -> bool:
    """True for an explicit directive to install/update/upgrade hub firmware.

    Deliberately a narrow ``fullmatch`` over known imperative phrasings
    (mirrors the WebUI's own "Update hub firmware" button text and its
    yes/proceed normalization, plus the natural variants a user might type
    directly), not a loose keyword search -- a read-only question like
    "check firmware" or "is there a firmware update" must never match this.

    Live-tested regression: the system prompt used to instruct the model to
    "only call hub_update_firmware after the snapshot reports
    update_available=true", trusting it to chain a second tool call across
    tool-selection rounds. It didn't reliably do that -- even the explicit
    request "Install the available Hubitat firmware update" only ever
    called the read-only snapshot and narrated a summary, so the
    confirmation gate (which only fires once the model actually attempts
    the sensitive tool call) never engaged. The WebUI's own "Update hub
    firmware" button just resubmits that same text, so the loop repeated
    indefinitely. This intent match lets the host propose the sensitive
    action deterministically instead -- it does not bypass confirmation;
    the actual `hub_update_firmware` call still only runs once the user
    replies "confirm".
    """

    return _FIRMWARE_INSTALL.fullmatch(str(prompt).strip()) is not None


_FIRMWARE_STATUS = re.compile(
    r"^\s*(?:please\s+)?(?:check\s+)?(?:the\s+)?(?:firmware\s+|hub\s+)?"
    r"update\s+(?:status|progress)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?(?:check\s+)?(?:the\s+)?firmware\s+update\s+"
    r"(?:status|progress)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?how(?:'s|\s+is)\s+the\s+(?:firmware\s+)?update\s+"
    r"(?:going|coming\s+along|progressing)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?is\s+the\s+(?:firmware\s+)?update\s+"
    r"(?:done|finished|complete|over)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?(?:is|has)\s+the\s+firmware\s+(?:update\s+)?"
    r"(?:finished|done|completed|installed)\s*[?.!]*\s*$",
    re.I,
)


def parse_firmware_status_intent(prompt: str) -> bool:
    """True for a question asking how a firmware update is progressing.

    This is the read-only counterpart to `parse_firmware_install_intent`,
    kept in this module rather than `contextual_read_fast_path.py` because
    it is firmware-domain-specific rather than a device-attribute read, and
    belongs next to the write-intent parser it mirrors. Deliberately a
    narrow `fullmatch` for the same reason as its write counterpart: a
    generic firmware question like "check firmware" or "what firmware is
    installed" (answered fine by the ordinary snapshot flow, see
    `homebrain_hub_info_snapshot`) must not match here, only phrasing that
    specifically asks about update status/progress/completion.

    Added after live testing surfaced a real limitation: Hubitat's Hub Info
    driver does not expose a live download percentage through its
    `hubUpdateStatus` attribute (confirmed live -- it read "Update
    Available" throughout an active download, never a percentage or a
    "Downloading"/"Installing" state), unlike the hub's own native
    Settings > Check for Updates page. The best a status check here can
    honestly report is whether `installed_firmware` has caught up with
    `available_firmware` yet -- "still in progress" vs "complete" -- not a
    percentage, and the outcome message says so rather than implying more
    precision than the data supports.
    """

    return _FIRMWARE_STATUS.fullmatch(str(prompt).strip()) is not None


def routine_control_arguments(prompt: str) -> dict[str, Any] | None:
    """Parse generic on/off/toggle control grammar without device-name encoding."""

    value = " ".join(str(prompt).strip().split())
    patterns = (
        r"^(?:please\s+)?(?:turn|switch|power)\s+"
        r"(?P<command>on|off)\s+(?P<target>.+?)\s*[.!?]*$",
        r"^(?:please\s+)?(?:turn|switch|power)\s+"
        r"(?P<target>.+?)\s+(?P<command>on|off)\s*[.!?]*$",
        r"^(?:please\s+)?(?P<command>toggle)\s+"
        r"(?P<target>.+?)\s*[.!?]*$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if not match:
            continue
        target = str(match.group("target") or "").strip()
        if target:
            return {
                "device_names": [target],
                "device_kind": "auto",
                "command": str(match.group("command")).casefold(),
            }
    return None
