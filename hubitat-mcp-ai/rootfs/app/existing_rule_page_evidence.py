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
_MAX_PHYSICAL_LINES = 32
_MAX_SOURCE_PARAGRAPH = 8192
# Editor page paragraphs sometimes prefix the action with an ordinal, bullet
# or "Action N:"; remove only that constrained presentation prefix. Never
# search arbitrary text for an action verb (help text is not execution data).
_DISPLAY_PREFIX = re.compile(
    r"^(?:(?:(?:Action|Step)\s*(?:#?\d+)?\s*:\s*)|"
    r"(?:(?:[•*–-]|\d{1,3}[.):\-])\s+)){1,2}", re.I,
)
_SYNTAX_HINTS = {
    "cancel_delayed": re.compile(r"\bCancel\s+Delayed\s+Actions\b", re.I),
    "conditional_if": re.compile(r"\bIF\s*\(", re.I),
    "end_if": re.compile(r"\bEND[- ]IF\b", re.I),
    "delay": re.compile(r"\bDelay\s+\d", re.I),
    "switch_off": re.compile(r"\bOff\s*:", re.I),
    "switch_on": re.compile(r"\bOn\s*:", re.I),
}
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
    # Match only a leading action verb *after* a constrained presentation
    # prefix. Mentions embedded in help descriptions are counted as hints
    # below but must never be promoted into recognised action rows.
    line = _DISPLAY_PREFIX.sub("", line, count=1)
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


def _classify_fragment(value: str) -> tuple[list[dict[str, Any]], int, bool]:
    """Recognise *separate physical lines* without flattening help prose.

    A multiline paragraph may contain editor rows or explanatory text. Promote
    action tokens only when >=2 separate, anchored physical lines match the
    allowlist. Reject a single "Action: On:..." followed by an unrelated line:
    it may be a description or a multi-line injection, not a row list.

    Return (recognized rows, inspected physical lines, limited/truncated).
    The output contains no raw source text or device labels.
    """
    if not isinstance(value, str) or "\x00" in value:
        return [], 0, False
    if len(value) > _MAX_SOURCE_PARAGRAPH:
        return [], 0, True
    lines = value.splitlines()
    if len(lines) < 2:
        return ([_classify_row(value)] if _classify_row(value) else []), 1, False
    limited = len(lines) > _MAX_PHYSICAL_LINES
    found: list[dict[str, Any]] = []
    for line in lines[:_MAX_PHYSICAL_LINES]:
        parsed = _classify_row(line)
        if parsed is not None:
            found.append(parsed)
    # Preserve anti-injection behaviour for one recognised line buried in
    # multiline prose or accidental newlines in a value.
    return (found if len(found) >= 2 else []), min(len(lines), _MAX_PHYSICAL_LINES), limited


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
        "paragraphSyntaxHints": {key: 0 for key in _SYNTAX_HINTS},
        "paragraphShapeCounts": {
            "numbered_or_bulleted": 0,
            "html_markup": 0,
            "over_limit": 0,
            "multiline": 0,
            "non_string": 0,
            "physical_lines_inspected": 0,
            "multiline_action_candidates": 0,
            "multiline_action_rows": 0,
        },
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
                result["paragraphShapeCounts"]["non_string"] += 1
                continue
            if len(fragment) > _MAX_FRAGMENT_LENGTH:
                result["paragraphShapeCounts"]["over_limit"] += 1
            if any(ch in fragment for ch in ("\n", "\r", "\x00")):
                result["paragraphShapeCounts"]["multiline"] += 1
            if _MARKUP.search(fragment):
                result["paragraphShapeCounts"]["html_markup"] += 1
            fragment_plain = html.unescape(_MARKUP.sub(" ", fragment))
            if _DISPLAY_PREFIX.match(fragment_plain.strip()):
                result["paragraphShapeCounts"]["numbered_or_bulleted"] += 1
            # Diagnostic hints are only counts of reserved syntax tokens:
            # no source text, labels, secrets, device IDs or URLs are retained.
            for hint_name, pattern in _SYNTAX_HINTS.items():
                if pattern.search(fragment_plain):
                    result["paragraphSyntaxHints"][hint_name] += 1
            classified_rows, inspected_lines, line_limited = _classify_fragment(fragment)
            result["paragraphShapeCounts"]["physical_lines_inspected"] += inspected_lines
            if line_limited:
                result["pageRowsTruncated"] = True
            if len(fragment.splitlines()) > 1:
                result["paragraphShapeCounts"]["multiline_action_candidates"] += (
                    len(classified_rows)
                )
            for classified in classified_rows:
                if len(rows) >= _MAX_ROWS:
                    result["pageRowsTruncated"] = True
                    break
                rows.append(classified)
                if len(fragment.splitlines()) > 1:
                    result["paragraphShapeCounts"]["multiline_action_rows"] += 1
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
