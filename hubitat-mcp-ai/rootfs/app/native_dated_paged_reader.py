"""Strict bounded read-only fallback for large native Rule Machine documents.

The upstream native hub_set_rule(operation=read) supports paging ONE section,
which avoids whole-document responses exceeding MCP's response-size cap.
This is a diagnostic read fallback, not a form or write path. No raw
settings, trigger contents, exception text or source errors are published.
"""
from __future__ import annotations

import re
import time
from typing import Any

from mcp_client import MCPTool, tool_succeeded
from tool_registry import ToolEffect, classify_tool_effect

_PAGED_SECTIONS = ("triggers", "settings")
_PAGE_SIZE = 50
_MAX_PAGES = {"triggers": 3, "settings": 8}
_MAX_TOTAL = {"triggers": 100, "settings": 400}
_SOURCE_TAG = "hub_set_rule:paged-read"
_SAFE_REVISION = re.compile(r"^[a-fA-F0-9]{16,128}$")
_CURSOR = re.compile(r"^(?:0|[1-9][0-9]{0,5})$")


def read_failure_category(reply: Any, rule_id: str) -> str:
    """Non-sensitive outcome code, never publish raw MCP response contents."""
    if reply is None:
        return "tool_exception"
    data = getattr(reply, "data", None)
    if getattr(reply, "is_error", False) or not tool_succeeded(reply):
        raw = ""
        if isinstance(data, dict):
            raw = str(data.get("error") or "")
            nested = data.get("result") or data.get("data") or data.get("output")
            if not raw and isinstance(nested, dict):
                raw = str(nested.get("error") or "")
        # Some MCP servers put errors in text, but don't expose the text.
        raw = (raw or str(getattr(reply, "text", "") or ""))[:512].casefold()
        if any(word in raw for word in (
            "response size", "size limit", "too large",
            "exceeds", "maximum response", "output too long",
        )):
            return "response_size_limit"
        if "native settings are unavailable" in raw:
            return "native_settings_unavailable"
        return "source_rejected"
    if not isinstance(data, dict):
        return "unexpected_source_shape"
    rid = data.get("rule_id")
    if type(rid) not in (str, int) or str(rid) != rule_id:
        return "rule_id_mismatch"
    if data.get("truncated") is True or data.get("nextCursor") is not None:
        return "incomplete_document"
    if not isinstance(data.get("triggers"), dict):
        return "missing_triggers"
    if not isinstance(data.get("settings"), list):
        return "missing_settings"
    if len(data["settings"]) > 256:
        return "oversized_settings"
    if len(data["triggers"]) > 100:
        return "oversized_triggers"
    return "unverified_document_shape"


def _page_shape(
    data: Any, *, rule_id: str, section: str, offset: int,
    expected_total: int | None, expected_revision: str | None,
) -> tuple[list[Any] | dict[str, Any] | None, str | None, int | None, str | None, str | None]:
    """Return (rows, next_cursor, total, revision, failure_code)."""
    if not isinstance(data, dict):
        return None, None, None, None, "unexpected_source_shape"
    if type(data.get("rule_id")) not in (int, str) or str(data["rule_id"]) != rule_id:
        return None, None, None, None, "rule_id_mismatch"
    page = data.get("page")
    if not isinstance(page, dict):
        return None, None, None, None, "missing_page_metadata"
    total, start, revision = page.get("total"), page.get("offset"), page.get("revision")
    if (type(total) is not int or type(start) is not int
            or start != offset or total < 0 or total > _MAX_TOTAL[section]):
        return None, None, None, None, "unbounded_or_changed_page"
    if not isinstance(revision, str) or not _SAFE_REVISION.fullmatch(revision):
        return None, None, None, None, "invalid_page_revision"
    if expected_total is not None and expected_total != total:
        return None, None, None, None, "changed_page_total"
    if expected_revision is not None and revision != expected_revision:
        return None, None, None, None, "changed_page_revision"
    rows = data.get(section)
    if section == "settings":
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("name"), str)
            for row in rows
        ):
            return None, None, None, None, "invalid_settings_rows"
        if len({row["name"] for row in rows}) != len(rows):
            return None, None, None, None, "duplicate_settings_rows"
    elif not isinstance(rows, dict) or any(
        not isinstance(k, str) for k in rows
    ):
        return None, None, None, None, "invalid_trigger_rows"
    count = len(rows)
    next_cursor = data.get("nextCursor")
    if next_cursor is not None:
        if (not isinstance(next_cursor, str) or not _CURSOR.fullmatch(next_cursor)
                or int(next_cursor) != offset + count
                or int(next_cursor) <= offset
                or int(next_cursor) >= total):
            return None, None, None, None, "invalid_page_cursor"
    elif offset + count != total:
        return None, None, None, None, "incomplete_page"
    if offset + count > total:
        return None, None, None, None, "page_exceeds_total"
    return rows, next_cursor, total, revision, None


async def read_paged_native_dated_document(
    mcp: Any, recorder: Any, *,
    gateway: str, rule_id: str,
) -> tuple[dict[str, Any] | None, str, dict[str, int]]:
    """Strictly source-attested two-section read with bounded continuation.

    Every tool envelope is independently classified as READ. The response
    is rejected if pages shift identity, revision, total, ordering or cursor.
    Only the final exact-ID and all-section complete document is returned
    for the caller's allowlisted date-field projector.
    """
    combined: dict[str, Any] = {"rule_id": int(rule_id)}
    pages_by_section: dict[str, int] = {}
    for section in _PAGED_SECTIONS:
        offset = 0
        cursor = ""
        revision: str | None = None
        total: int | None = None
        collected: list[dict[str, Any]] | dict[str, Any] = (
            [] if section == "settings" else {}
        )
        complete = False
        for _ in range(_MAX_PAGES[section]):
            args = {"tool": "hub_set_rule", "args": {
                "operation": "read", "rule_id": int(rule_id),
                "args": {
                    "sections": [section],
                    "cursor": cursor,
                    "limit": _PAGE_SIZE,
                },
            }}
            if classify_tool_effect(MCPTool(gateway, gateway, {}), args) is not ToolEffect.READ:
                return None, "read_envelope_not_authorized", pages_by_section
            start = time.monotonic()
            failure: str | None = None
            rows: list[Any] | dict[str, Any] | None = None
            nxt: str | None = None
            incoming_total: int | None = None
            incoming_revision: str | None = None
            try:
                reply = await mcp.call_tool(gateway, args)
                if tool_succeeded(reply):
                    rows, nxt, incoming_total, incoming_revision, failure = _page_shape(
                        getattr(reply, "data", None), rule_id=rule_id,
                        section=section, offset=offset,
                        expected_total=total, expected_revision=revision,
                    )
                else:
                    failure = read_failure_category(reply, rule_id)
            except Exception:
                failure = "tool_exception"
            ok = failure is None and rows is not None
            recorder.record(
                gateway, args, success=ok,
                elapsed_ms=round((time.monotonic() - start) * 1000),
                summary=(
                    f"Bounded native {section} page read verified"
                    if ok else f"Bounded native {section} page incomplete"
                ),
                evidence_kind="typed_native_dated_trigger_page",
                supports_live_claim=False, mutates=False, effect="read",
                details={
                    "ruleId": rule_id, "section": section,
                    "offset": offset,
                    "rowsReturned": len(rows) if ok else 0,
                    "failureCode": failure if failure else None,
                },
            )
            if not ok:
                return None, failure or "unverified_page", pages_by_section
            total = incoming_total
            revision = incoming_revision
            if section == "settings":
                assert isinstance(collected, list) and isinstance(rows, list)
                seen = {r["name"] for r in collected}
                if any(r["name"] in seen for r in rows):
                    return None, "duplicate_settings_rows", pages_by_section
                collected.extend(rows)
            else:
                assert isinstance(collected, dict) and isinstance(rows, dict)
                if set(collected).intersection(rows):
                    return None, "duplicate_trigger_rows", pages_by_section
                collected.update(rows)
            pages_by_section[section] = pages_by_section.get(section, 0) + 1
            if nxt is None:
                complete = True
                break
            offset = int(nxt)
            cursor = nxt
        if not complete:
            return None, "page_limit_exceeded", pages_by_section
        combined[section] = collected
    combined["_source"] = _SOURCE_TAG
    return combined, "complete", pages_by_section


__all__ = ["read_failure_category", "read_paged_native_dated_document"]
