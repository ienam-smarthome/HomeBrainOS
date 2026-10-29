"""Bind independently verified target READs to the user's actual subject.

Focus is source/identity-derived, never a keyword route or a guessed ID.
A device-scoped read and a matching typed source receipt are BOTH necessary
for log, runtime-stat or event-history anchors. Unscoped hub audits, app
commands, free-text mentions and unmatched labels cannot create focus.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def _normal(value: Any) -> str:
    return " ".join(re.findall(r"[^\\W_]+", str(value or "").casefold(),
                               flags=re.UNICODE))


def _question_basis(question: str, target: str, names: list[Any]) -> str | None:
    if re.search(r"(?<![0-9])" + re.escape(target) + r"(?![0-9])", question):
        return "explicit_verified_device_id"
    normalized_question = " " + _normal(question) + " "
    for value in names:
        if not isinstance(value, str):
            continue
        aliases = [value]
        if " - [" in value:
            aliases.append(value.split(" - [", 1)[0])
        for alias in aliases:
            normalized_alias = _normal(alias)
            if (len(normalized_alias) >= 9
                    and len(normalized_alias.split()) >= 2
                    and " " + normalized_alias + " " in normalized_question):
                return "explicit_verified_device_name"
    return None


def verified_device_focus(
    question: str, operation: str, args: Mapping[str, Any],
    source: Mapping[str, Any], verified_device_ids: set[str],
) -> dict[str, str] | None:
    """Recognise explicitly referenced subjects in approved typed READs.

    The requested ID must already be independently permitted by the host
    and **echoed** by the actual projected source. A requested filter is not
    evidence by itself. No unspecified focus is inferred from broad reads.
    """
    if not isinstance(question, str):
        return None
    if not isinstance(args, Mapping) or not isinstance(source, Mapping):
        return None
    requested = args.get("deviceId")
    if type(requested) not in (int, str) or not str(requested).isdecimal():
        return None
    target = str(requested)
    if target not in verified_device_ids:
        return None

    names: list[Any] = []
    origin = ""
    if operation == "hub_get_device" and str(source.get("id")) == target:
        names = [source.get("label"), source.get("name")]
        origin = "device"
    elif operation == "hub_get_logs":
        mode = args.get("mode", "past")
        if mode == "past":
            summary = source.get("log_summary")
            groups = (summary.get("warning_error_groups", [])
                      if isinstance(summary, Mapping) else [])
            for group in groups[:35] if isinstance(groups, list) else []:
                if (isinstance(group, Mapping)
                        and str(group.get("source_id")) == target
                        and group.get("source_type") in ("dev", "device")):
                    names.append(group.get("source_name"))
            if names:
                origin = "target_log"
        elif mode == "devices":
            stats = source.get("runtime_stats")
            rows = stats.get("rows", []) if isinstance(stats, Mapping) else []
            if isinstance(stats, Mapping) and stats.get("mode") == "devices":
                for row in rows[:60] if isinstance(rows, list) else []:
                    if isinstance(row, Mapping) and str(row.get("id")) == target:
                        names.append(row.get("name"))
                if names:
                    origin = "device_runtime"
    elif operation == "hub_list_device_events":
        events = source.get("events")
        for event in events[:130] if isinstance(events, list) else []:
            if not isinstance(event, Mapping):
                continue
            producer = event.get("producedBy")
            if (isinstance(producer, Mapping)
                    and str(producer.get("deviceId")) == target
                    and producer.get("appId") is None):
                names.append(producer.get("name"))
        if names:
            origin = "device_event"
    if not origin:
        return None

    basis = _question_basis(question, target, names)
    return {"device_id": target, "identity_basis": basis,
            "source_kind": origin} if basis and origin != "device" else (
        {"device_id": target, "identity_basis": basis} if basis else None)


__all__ = ["verified_device_focus"]
