"""A compact, source-derived map of returned installed-app configuration pages.

This is metadata about what the model actually read, not a planner or a causal
classifier. Do not infer a historical configuration, a timer firing, the state
of unqueried devices or an execution log from an app's rendered UI.
"""
from __future__ import annotations

import json
import re
from typing import Any


_SENSITIVE_FIELD = re.compile(
    r"password|passwd|token|secret|api[_-]?key|credential|authorization|pin\b",
    re.IGNORECASE,
)
_SCALAR_TYPES = {"bool", "boolean", "number", "decimal", "enum", "time"}


def _inner(result: dict) -> dict | None:
    if not isinstance(result, dict) or result.get("isError"):
        return None
    for block in result.get("content", []) if isinstance(result.get("content"), list) else []:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        try:
            payload = json.loads(block.get("text", ""))
        except (ValueError, TypeError):
            continue
        if (isinstance(payload, dict) and payload.get("success") is not False
                and isinstance(payload.get("app"), dict)
                and isinstance(payload.get("page"), dict)):
            return payload
    if (isinstance(result.get("app"), dict)
            and isinstance(result.get("page"), dict)
            and result.get("success") is not False):
        return result
    return None


def _short(value: Any, limit: int = 128) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    text = str(value)
    return text if 0 < len(text) <= limit else None


def config_source_map(result: dict) -> dict | None:
    """Summarise ONLY the current returned config page; never infer a cause.

    Every named field below was read from the original MCP result. Limits are
    explicit and all omitted data remains available in the original result.
    """
    payload = _inner(result)
    if payload is None:
        return None
    page = payload["page"]
    hrefs = page.get("hrefs") if isinstance(page.get("hrefs"), list) else []
    pages = []
    for href in hrefs:
        if not isinstance(href, dict):
            continue
        name = _short(href.get("page"), 96)
        if name is None:
            continue
        pages.append({"page": name, "title": _short(href.get("title"), 120)})
    linked_pages = pages[:24]

    sections = page.get("sections") if isinstance(page.get("sections"), list) else []
    controls = []
    selected = []
    total_inputs = 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        inputs = section.get("inputs")
        if not isinstance(inputs, list):
            continue
        for row in inputs:
            if not isinstance(row, dict):
                continue
            total_inputs += 1
            name = _short(row.get("name"), 96)
            title = _short(row.get("title"), 140)
            kind = _short(row.get("type"), 70)
            if not name or not kind or _SENSITIVE_FIELD.search(name) or (
                    title and _SENSITIVE_FIELD.search(title)):
                continue
            chosen = row.get("selected")
            if isinstance(chosen, list) and chosen:
                refs = []
                for item in chosen:
                    if not isinstance(item, dict):
                        continue
                    value = _short(item.get("value"), 96)
                    if value is None:
                        continue
                    refs.append({"value": value, "label": _short(item.get("label"), 120)})
                if refs:
                    selected.append({
                        "name": name, "title": title, "type": kind,
                        "selected": refs[:24], "returned_selected_count": len(refs),
                        "selected_items_omitted": max(0, len(refs) - 24),
                    })
            elif kind.startswith("capability.") or kind == "mode":
                # Selected labels are not always supplied by upstream. Keep
                # raw references if the input explicitly returned them.
                raw_values = row.get("value")
                if isinstance(raw_values, list):
                    refs = [v for v in (_short(x, 96) for x in raw_values) if v is not None]
                    if refs:
                        selected.append({
                            "name": name, "title": title, "type": kind,
                            "selected_values": refs[:24],
                            "returned_selected_count": len(refs),
                            "selected_items_omitted": max(0, len(refs) - 24),
                        })
            if kind in _SCALAR_TYPES and row.get("value") is not None:
                raw_value = row.get("value")
                if isinstance(raw_value, (bool, str, int, float)) and (
                        not isinstance(raw_value, str) or len(raw_value) <= 128):
                    controls.append({
                        "name": name, "title": title, "type": kind,
                        "value": raw_value,
                    })
    # Preserve source field names and literal values. Do not label options as
    # schedules, causes, conditions, "active" or "verified" in this client map.
    return {
        "source_scope": "one returned current installed-app configuration page",
        "page_name": _short(page.get("name"), 120),
        "linked_pages": linked_pages,
        "linked_pages_omitted": max(0, len(pages) - len(linked_pages)),
        "inputs_on_returned_page": total_inputs,
        "selected_input_groups": selected[:24],
        "selected_input_groups_omitted": max(0, len(selected) - 24),
        "returned_scalar_control_values": controls[:64],
        "scalar_control_values_omitted": max(0, len(controls) - 64),
        "raw_settings_included_in_source": isinstance(payload.get("settings"), dict),
        "historical_configuration_proven_by_this_page": False,
        "event_specific_callback_or_timer_proven_by_this_page": False,
        "note": (
            "This map restates fields from one returned configuration page. "
            "It neither establishes historical settings nor proves which "
            "internal path ran. Linked pages can contain additional controls; "
            "selected input groups are not proof of their historical state. "
            "For a causal question, compare the observed initiating event with "
            "materially plausible configured paths and the relevant input "
            "histories or execution records when available. The model decides "
            "whether further read-only sources are useful."
        ),
    }
