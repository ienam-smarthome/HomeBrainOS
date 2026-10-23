"""Read-only, bounded evidence from current native Rule Machine editor pages.

A page is a *rendered editor view*, not the compiled native actionList.
Only declassify recognized action syntax (no labels, raw HTML, arbitrary text,
variables, device names, credentials or URLs). Never mark ordered actions or
conditions as validated from an HTML/page read.
"""
from __future__ import annotations

import html
import re
from typing import Any

_ALLOWED_PAGES = frozenset({"selectActions", "selectTriggers"})
_ID = re.compile(r"^[1-9]\d{1,7}$")
_MARKUP = re.compile(r"<[^>]{0,512}>")
_WS = re.compile(r"\s+")
_MAX_SECTIONS = 32
_MAX_PARAGRAPHS = 128
_MAX_FRAGMENT_LENGTH = 400
_MAX_ROWS = 40
_DELAY = re.compile(
    r"^Delay\s+(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})"
    r"\s*(?P<cancelable>\(\s*cancelable\s*\))?",
    re.I,
)
_ACTION = (
    ("cancel-delayed-actions", re.compile(r"^(?:Action:\s*)?Cancel Delayed Actions(?:\b|$)", re.I)),
    ("if", re.compile(r"^(?:Action:\s*)?IF\s*\(", re.I)),
    ("end-if", re.compile(r"^(?:Action:\s*)?END[- ]IF\b", re.I)),
    ("else-if", re.compile(r"^(?:Action:\s*)?ELSE[- ]IF\b", re.I)),
    ("else", re.compile(r"^(?:Action:\s*)?ELSE\b", re.I)),
    ("off", re.compile(r"^(?:Action:\s*)?Off:\s*\S", re.I)),
    ("on", re.compile(r"^(?:Action:\s*)?On:\s*\S", re.I)),
)


def _classify_row(value: str) -> dict[str, Any] | None:
    if (not isinstance(value, str) or len(value) > _MAX_FRAGMENT_LENGTH
            or any(ch in value for ch in ("\n", "\r", "\x00"))):
        return None
    line = _WS.sub(" ", html.unescape(_MARKUP.sub(" ", value))).strip()
    if not line or any(ord(ch) < 32 for ch in line):
        return None
    # Avoid treating page instructions discussing actions as actual action rows.
    if line.casefold().startswith(("action:", "step:")):
        line = re.sub(r"^(?:action|step):\s*", "", line, flags=re.I)
    match = _DELAY.match(line)
    if match:
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes"))
        seconds = int(match.group("seconds"))
        if hours > 23 or minutes > 59 or seconds > 59:
            return None
        return {
            "kind": "delay",
            "seconds": hours * 3600 + minutes * 60 + seconds,
            # Omitted means the page did not specify cancelability.
            **({"cancelable": True} if match.group("cancelable") else {}),
        }
    for kind, pat in _ACTION:
        if pat.match(line):
            return {"kind": kind}
    return None


def project_existing_rule_page(
    data: Any, expected_app_id: str, expected_page: str,
) -> dict[str, Any]:
    """Normalize recognized page rows; never treat page text as typed native actions."""
    empty: dict[str, Any] = {
        "appId": str(expected_app_id),
        "pageName": str(expected_page),
        "pageReadVerified": False,
        "pageRowsTruncated": False,
        "recognizedActionRows": [],
        "orderedActionsValidated": False,
        "conditionsValidated": False,
        "triggerLogicValidated": False,
    }
    if expected_page not in _ALLOWED_PAGES or not _ID.fullmatch(str(expected_app_id)):
        return empty
    if not isinstance(data, dict) or data.get("success") is False:
        return empty
    app = data.get("app")
    if not isinstance(app, dict) or str(app.get("id") or "") != str(expected_app_id):
        return empty
    page = data.get("page")
    if not isinstance(page, dict):
        return empty
    page_name = page.get("name") or page.get("pageName")
    if page_name is not None and str(page_name) != expected_page:
        return empty
    sections = page.get("sections")
    if not isinstance(sections, list):
        return empty
    result = dict(empty, pageReadVerified=True)
    if len(sections) > _MAX_SECTIONS:
        result["pageRowsTruncated"] = True
    rows = []
    paragraph_total = 0
    for section in sections[:_MAX_SECTIONS]:
        if not isinstance(section, dict):
            continue
        fragments = section.get("paragraphs")
        if not isinstance(fragments, list):
            continue
        if len(fragments) > _MAX_PARAGRAPHS:
            result["pageRowsTruncated"] = True
        for fragment in fragments[:_MAX_PARAGRAPHS]:
            paragraph_total += 1
            if len(rows) >= _MAX_ROWS:
                result["pageRowsTruncated"] = True
                break
            if not isinstance(fragment, str):
                continue
            classified = _classify_row(fragment)
            if classified is not None:
                rows.append(classified)
    # The list is "encounter order in the displayed page", explicitly NOT a
    # certified native action order. Even a complete-looking page may be only
    # a preview, an excerpt or dynamic editor screen.
    result["recognizedActionRows"] = rows
    result["paragraphsInspected"] = paragraph_total
    return result


def existing_rule_page_metadata(
    gateway: str, arguments: dict[str, Any], data: Any,
) -> dict[str, Any] | None:
    """Permit the regular execution recorder to attach strict page metadata."""
    if gateway != "hub_read_apps_code" or arguments.get("tool") != "hub_get_app_config":
        return None
    args = arguments.get("args")
    if not isinstance(args, dict):
        return None
    page = args.get("pageName")
    app_id = str(args.get("appId") or "")
    if page not in _ALLOWED_PAGES or not _ID.fullmatch(app_id):
        return None
    return project_existing_rule_page(data, app_id, page)


__all__ = ["project_existing_rule_page", "existing_rule_page_metadata"]
