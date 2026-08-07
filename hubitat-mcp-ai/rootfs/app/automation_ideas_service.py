"""Model-assisted creative automation suggestions.

`AutomationStatusService` is deliberately deterministic (see its own
docstring: "without relying on LLM formatting") -- gap analysis against
real device capabilities and real automation names, nothing invented.
That is the right default for factual status/audit questions, but a
request for genuinely new, themed automation ideas ("set up an away/
security mode", "consolidate the kids' homework routine") requires
synthesizing across the whole device inventory, which a capability-gap
checklist cannot do no matter how many capabilities it covers -- that
needs a model.

This module asks the configured model directly, in one plain (non-tool-
calling) round, grounded only in already-retrieved real device and
automation data supplied by the caller. It never claims anything about
current device state as fact -- only ever proposes ideas, explicitly
labelled as suggestions -- so it deliberately does not go through
`UnifiedMCPAgent`'s tool-calling loop or its strict evidence-required
grounding policy (`grounding_policy.py`): that policy exists to stop
unverified *factual* claims, not clearly-labelled speculative suggestions
grounded in data the caller already fetched.

Never raises: any failure (missing API key, timeout, malformed response)
returns `None` so the caller can fall back to the deterministic
gap-analysis message unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agent_prompt_policy import render_device_manifest


logger = logging.getLogger("HomeBrainOS.AutomationIdeas")

ChatCallable = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    Awaitable[dict[str, Any]],
]

_SYSTEM_PROMPT = (
    "You are HomeBrainOS, a concise smart-home assistant. The user wants "
    "genuinely new home automation ideas, not a status report. You are "
    "given their real, live device inventory and the names of automations "
    "that already exist. Suggest 3 to 5 concrete, themed automation ideas "
    "that are not already covered by an existing automation name. Each "
    "idea must reference real devices from the inventory by name. Clearly "
    "present these as suggestions, never as facts about the current state "
    "of any device -- do not claim a device is currently on, off, open, "
    "or in any particular state; you have no live reading of that here. "
    "Be concise: a short heading and one or two sentences per idea is "
    "enough."
)


async def suggest_new_automations(
    chat: ChatCallable,
    automation_items: list[dict[str, Any]],
    devices: list[dict[str, Any]],
) -> str | None:
    """Ask the model for creative ideas grounded in real inventory data.

    Returns `None` on any failure or when there is no device data to
    ground a suggestion in, so the caller can fall back to the
    deterministic gap-analysis message unchanged.
    """

    if not devices:
        return None
    existing_names = ", ".join(
        sorted({
            str(item.get("display_name") or item.get("name") or "").strip()
            for item in automation_items
            if item.get("display_name") or item.get("name")
        })
    )
    manifest = render_device_manifest(devices)
    user_prompt = (
        "LIVE DEVICE MANIFEST\n" + manifest + "\n\n"
        "EXISTING AUTOMATION NAMES (do not duplicate these)\n"
        + (existing_names or "None") + "\n\n"
        "Suggest new automation ideas for this home."
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = await chat(messages, [])
    except Exception:
        logger.warning(
            "Creative automation suggestion call failed", exc_info=True
        )
        return None
    content = str((response or {}).get("content") or "").strip()
    return content or None


__all__ = ["suggest_new_automations"]
