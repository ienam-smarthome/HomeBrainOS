"""Target one named installed Rule Machine document; never enumerate as answer.

Exact-name lookup is a read-only identity step. A specific native document
read then reuses the existing typed-source verifier and privacy filter.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from mcp_client import tool_succeeded
from native_rule_document_source import read_explicit_native_rule_document

_QUOTED_NAMED = re.compile(
    r"\brule(?:\s+machine)?\s+(?:named|called|titled)\s+"
    r"(?P<quote>['\"“‘])(?P<name>[^'\"”’\r\n]{1,160})['\"”’]",
    re.I,
)
_OBJECTIVE = re.compile(
    r"\b(?:read|retrieve|inspect|review|examine|show|check|find|"
    r"describe|analyse|analyze|explain|report)\b",
    re.I,
)
_RULE_DOCUMENT = re.compile(
    r"\b(?:native|document|details?|configuration|settings|"
    r"triggers?|actions?|conditions?|ordered|rule\s+id|"
    r"schedule|scheduled\s+job|rule\s+health)\b",
    re.I,
)


def parse_named_rule_read(prompt: str) -> str | None:
    """Accept an exact quoted named rule, never infer identity from a keyword."""
    text = str(prompt or "")
    match = _QUOTED_NAMED.search(text)
    if (not match or not _OBJECTIVE.search(text)
            or not _RULE_DOCUMENT.search(text)):
        return None
    name = " ".join(match.group("name").split()).strip()
    return name if 1 <= len(name) <= 160 else None


@dataclass(slots=True)
class NamedRuleReadOutcome:
    message: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    request_class: str = "live-read"
    route: str = "named-rule-read"
    choices: list[str] = field(default_factory=list)
    complete: bool = False


class _Evidence:
    def __init__(self, target: list[dict[str, Any]]) -> None:
        self.target = target

    def record(self, gateway: str, arguments: dict[str, Any], **kw: Any) -> None:
        self.target.append({"tool": gateway, "arguments": arguments, **kw})


async def read_named_rule_document(mcp: Any, name: str) -> NamedRuleReadOutcome:
    """Exact unique match, then one approved native operation='read' call."""
    evidence: list[dict[str, Any]] = []
    listed_args = {"tool": "hub_list_rules", "args": {}}
    started = time.monotonic()
    try:
        listing = await mcp.call_tool("hub_read_rules", listed_args)
        ok = tool_succeeded(listing)
        data = listing.data if ok and isinstance(listing.data, dict) else {}
    except Exception:
        ok, data = False, {}
    rows = data.get("rules")
    complete = (
        ok and isinstance(rows, list)
        and all(isinstance(row, dict) for row in rows)
        and not data.get("nextCursor")
        and data.get("truncated") is not True
        and type(data.get("count")) is int
        and data["count"] == len(rows)
    )
    evidence.append({
        "tool": "hub_read_rules", "sub_tool": "hub_list_rules",
        "arguments": listed_args, "success": bool(complete),
        "mutates": False, "effect": "read",
        "supports_live_claim": bool(complete),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "summary": (
            "Complete current native rule name inventory checked for an exact unique match"
            if complete else "Rule inventory incomplete; exact-name identity not verified"
        ),
    })
    if not complete:
        return NamedRuleReadOutcome(
            f"I couldn't verify the complete Rule Machine list, so I can't "
            f"safely identify the rule named **{name}**. No rule was changed.",
            evidence,
        )
    matches = [row for row in rows
               if str(row.get("name") or row.get("label") or "").strip().casefold()
               == name.casefold()]
    if len(matches) != 1:
        return NamedRuleReadOutcome(
            f"**{name}** matched {len(matches)} entries in the complete "
            "Rule Machine listing. I won't guess an ID or substitute a "
            "general automation summary. No rule was changed.",
            evidence,
        )
    selected = matches[0]
    app_id = str(selected.get("id") or selected.get("appId") or "")
    if not re.fullmatch(r"[1-9]\d{1,8}", app_id):
        return NamedRuleReadOutcome(
            f"**{name}** was found, but its rule ID is not verifiable. "
            "No native document was read and nothing was changed.",
            evidence,
        )
    try:
        catalog = await mcp.list_tools()
        available = {entry.name for entry in catalog}
    except Exception:
        available = set()
    if not available:
        return NamedRuleReadOutcome(
            f"Found **{name}** (rule ID **{app_id}**), but native rule "
            "read capability discovery failed. Its triggers and actions "
            "remain unverified. No changes were made.",
            evidence,
        )
    # Use the existing strictly read-only envelope and typed result verifier.
    # A source error is reported, never silently replaced with inventory.
    request = (
        f'hub_set_rule operation=read rule_id={app_id} '
        'sections=["triggers","actions","settings","conditions","expressions","variables"]'
    )
    result = await read_explicit_native_rule_document(
        mcp, _Evidence(evidence), prompt=request, available_names=available,
        summary_mode=True,
    )
    if result is None:
        return NamedRuleReadOutcome(
            f"Found **{name}** (rule ID **{app_id}**), but native "
            "document read was not admitted. Nothing was changed.",
            evidence,
        )
    verified = bool(
        evidence and evidence[-1].get("success") is True
        and evidence[-1].get("details", {}).get("projectionVerified") is True
    )
    return NamedRuleReadOutcome(
        f"**{name}** — Rule Machine ID **{app_id}**.\n\n{result}\n\n"
        "This is saved rule configuration, not proof the rule has fired. "
        "A one-time name alone does not establish a one-time trigger.",
        evidence, complete=verified,
    )
