"""Deterministic native-log correlation around causal subject boundaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from causal_timeline import build_causal_timeline_rows
from natural_datetime import normalize_iso_offset


_LOG_PREFIX = re.compile(r"^(?P<kind>dev|app|rule)\|(?P<id>[^|]+)\|(?P<label>[^|]+)\|(?P<message>.*)$", re.I)
_BUTTON_NUMBER = re.compile(r"\bbutton\s+(?P<button>\d+)\b", re.I)
_PHYSICAL_CONTROL = re.compile(
    r"\b(?:button|pushed|held|released|double\s*tapped|doubletapped)\b",
    re.I,
)
_COMMAND_ACTIONS = (
    (re.compile(r"\b(?:turn\s+on\s+command|command\s+called:\s*on\(\))\b", re.I), "on"),
    (re.compile(r"\b(?:turn\s+off\s+command|command\s+called:\s*off\(\))\b", re.I), "off"),
)
_APP_REACTION = re.compile(
    r"\b(?:manual\s+run|manual\s+activation|dev\s+lock|will\s+turn\s+off|"
    r"detected|external|takeover|timed\s+run)\b",
    re.I,
)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _parse_log_time(value: Any, *, reference: datetime) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=reference.tzinfo)
    return parsed


def causal_boundary_log_windows(
    evidence: list[dict[str, Any]],
    *,
    padding_seconds: int = 10,
    max_intervals: int = 2,
) -> list[dict[str, str]]:
    """Return UTC native-log windows for both start and end boundaries."""

    pad = timedelta(seconds=max(1, min(60, int(padding_seconds))))
    windows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    material = [
        row
        for row in build_causal_timeline_rows(evidence)
        if row.get("material")
    ]
    material.sort(
        key=lambda row: _parse_time(row.get("start")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    for row in material[: max(1, min(2, int(max_intervals)))]:
        for role, key in (("start", "start"), ("end", "end")):
            raw = str(row.get(key) or "").strip()
            boundary = _parse_time(raw)
            if boundary is None:
                continue
            dedupe = (str(row.get("id") or ""), role)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            since = (boundary - pad).astimezone(timezone.utc)
            until = (boundary + pad).astimezone(timezone.utc)
            windows.append({
                "timelineId": str(row.get("id") or ""),
                "boundaryRole": role,
                "subjectBoundary": boundary.isoformat(),
                "since": since.isoformat().replace("+00:00", "Z"),
                "until": until.isoformat().replace("+00:00", "Z"),
            })
    return windows


def _log_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if not (
            str(receipt.get("sub_tool") or "") == "hub_get_logs"
            or str(receipt.get("tool") or "") == "hub_get_logs"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        logs = details.get("logs")
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            date = str(item.get("date") or item.get("timestamp") or "").strip()
            message = str(item.get("message") or "").strip()
            if not date or not message:
                continue
            key = (date, message)
            if key in seen:
                continue
            seen.add(key)
            match = _LOG_PREFIX.match(message)
            row = dict(item)
            if match:
                row["sourceKind"] = match.group("kind").casefold()
                row["sourceId"] = match.group("id").strip()
                row["sourceLabel"] = match.group("label").strip()
                row["payload"] = match.group("message").strip()
            else:
                row["sourceKind"] = ""
                row["sourceId"] = ""
                row["sourceLabel"] = str(item.get("source") or "").strip()
                row["payload"] = message
            rows.append(row)
    return rows


def _command_action(row: dict[str, Any], *, subject: str) -> str | None:
    if str(row.get("sourceKind") or "") != "dev":
        return None
    label = str(row.get("sourceLabel") or "").strip()
    payload = str(row.get("payload") or row.get("message") or "")
    comparable_subject = re.sub(r"[^a-z0-9]", "", subject.casefold())
    comparable_label = re.sub(r"[^a-z0-9]", "", label.casefold())
    if comparable_subject and comparable_label != comparable_subject:
        if comparable_subject not in re.sub(r"[^a-z0-9]", "", payload.casefold()):
            return None
    for pattern, action in _COMMAND_ACTIONS:
        if pattern.search(payload):
            return action
    return None


def _physical_controller(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = str(row.get("payload") or row.get("message") or "")
    if "[physical]" not in payload.casefold() or not _PHYSICAL_CONTROL.search(payload):
        return None
    button_match = _BUTTON_NUMBER.search(payload)
    button = button_match.group("button") if button_match else ""
    source_id = str(row.get("sourceId") or "").strip()
    source_label = str(row.get("sourceLabel") or "").strip()
    return {
        "sourceId": source_id,
        "sourceLabel": source_label,
        "button": button,
        "fingerprint": f"{source_id}:{button}" if source_id else f"{source_label.casefold()}:{button}",
        "message": payload,
    }


def correlate_native_log_boundaries(
    evidence: list[dict[str, Any]],
    *,
    command_window_seconds: float = 2.0,
    controller_window_seconds: float = 2.0,
    reaction_window_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Join physical controller -> subject command -> state boundary timing."""

    logs = _log_rows(evidence)
    if not logs:
        return []

    correlations: list[dict[str, Any]] = []
    for timeline in build_causal_timeline_rows(evidence):
        if not timeline.get("material"):
            continue
        subject = str(timeline.get("subject") or "").strip()
        for role, expected_action in (("start", "on"), ("end", "off")):
            boundary = _parse_time(timeline.get(role))
            if boundary is None:
                continue

            commands: list[tuple[float, datetime, dict[str, Any]]] = []
            for row in logs:
                event_time = _parse_log_time(row.get("date"), reference=boundary)
                if event_time is None:
                    continue
                action = _command_action(row, subject=subject)
                if action != expected_action:
                    continue
                signed = (event_time - boundary).total_seconds()
                if abs(signed) <= command_window_seconds:
                    commands.append((abs(signed), event_time, row))
            if not commands:
                continue
            commands.sort(key=lambda item: item[0])
            _distance, command_time, command_row = commands[0]

            controllers: list[tuple[float, datetime, dict[str, Any], dict[str, Any]]] = []
            for row in logs:
                event_time = _parse_log_time(row.get("date"), reference=boundary)
                if event_time is None:
                    continue
                controller = _physical_controller(row)
                if controller is None:
                    continue
                signed = (event_time - command_time).total_seconds()
                # Prefer physical events immediately before the command. Allow a
                # tiny positive skew for logger ordering jitter, but never a broad
                # after-the-fact association.
                if -controller_window_seconds <= signed <= 0.250:
                    controllers.append((abs(signed), event_time, row, controller))
            controllers.sort(key=lambda item: item[0])

            app_reactions: list[tuple[float, datetime, dict[str, Any]]] = []
            for row in logs:
                if str(row.get("sourceKind") or "") != "app":
                    continue
                event_time = _parse_log_time(row.get("date"), reference=boundary)
                if event_time is None:
                    continue
                signed = (event_time - command_time).total_seconds()
                payload = str(row.get("payload") or row.get("message") or "")
                if 0 <= signed <= reaction_window_seconds and _APP_REACTION.search(payload):
                    app_reactions.append((signed, event_time, row))
            app_reactions.sort(key=lambda item: item[0])

            correlation: dict[str, Any] = {
                "timelineId": str(timeline.get("id") or ""),
                "boundaryRole": role,
                "subject": subject,
                "stateBoundary": boundary.isoformat(),
                "expectedAction": expected_action,
                "command": {
                    "date": command_time.isoformat(),
                    "sourceId": str(command_row.get("sourceId") or ""),
                    "sourceLabel": str(command_row.get("sourceLabel") or ""),
                    "message": str(command_row.get("payload") or command_row.get("message") or ""),
                    "commandToStateMs": round((boundary - command_time).total_seconds() * 1000, 1),
                },
                "controller": None,
                "appReactions": [],
            }

            if controllers:
                _delta, controller_time, controller_row, controller = controllers[0]
                correlation["controller"] = {
                    **controller,
                    "date": controller_time.isoformat(),
                    "controllerToCommandMs": round(
                        (command_time - controller_time).total_seconds() * 1000,
                        1,
                    ),
                    "controllerToStateMs": round(
                        (boundary - controller_time).total_seconds() * 1000,
                        1,
                    ),
                }

            correlation["appReactions"] = [
                {
                    "date": event_time.isoformat(),
                    "sourceId": str(row.get("sourceId") or ""),
                    "sourceLabel": str(row.get("sourceLabel") or ""),
                    "message": str(row.get("payload") or row.get("message") or ""),
                    "afterCommandMs": round(delta * 1000, 1),
                }
                for delta, event_time, row in app_reactions[:4]
            ]
            correlations.append(correlation)

    by_role = {str(row.get("boundaryRole")): row for row in correlations}
    start_controller = (by_role.get("start") or {}).get("controller")
    end_controller = (by_role.get("end") or {}).get("controller")
    repeated = bool(
        isinstance(start_controller, dict)
        and isinstance(end_controller, dict)
        and start_controller.get("fingerprint")
        and start_controller.get("fingerprint") == end_controller.get("fingerprint")
    )
    if repeated:
        for row in correlations:
            row["repeatedControllerPattern"] = True
            row["provenanceStrength"] = "strong-repeated-temporal-provenance"
    else:
        for row in correlations:
            row["repeatedControllerPattern"] = False
            row["provenanceStrength"] = (
                "strong-single-boundary-temporal-provenance"
                if row.get("controller")
                else "subject-command-only"
            )
    return correlations


def native_log_provenance_sufficient(correlations: list[dict[str, Any]]) -> bool:
    """Require repeated same-controller start/end evidence before early finalization."""

    if not correlations:
        return False
    by_role = {str(row.get("boundaryRole")): row for row in correlations}
    start = by_role.get("start")
    end = by_role.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return False
    return bool(
        start.get("controller")
        and end.get("controller")
        and start.get("repeatedControllerPattern") is True
        and end.get("repeatedControllerPattern") is True
        and start.get("command")
        and end.get("command")
    )


def render_native_log_correlation(
    correlations: list[dict[str, Any]],
) -> str | None:
    if not correlations:
        return None

    lines = [
        "HOST NATIVE-LOG BOUNDARY CORRELATION",
        (
            "These rows are deterministic timestamp correlations from CURRENT-TURN "
            "native logs. A physical controller event immediately preceding the "
            "subject command is materially stronger provenance than app configuration. "
            "Repeated matching controller/input evidence at both start and end "
            "strengthens the device-control association, but timing alone still does "
            "not prove the configured button-to-device mapping or identify a person."
        ),
    ]
    for row in correlations:
        role = str(row.get("boundaryRole") or "?")
        command = row.get("command") if isinstance(row.get("command"), dict) else {}
        controller = row.get("controller") if isinstance(row.get("controller"), dict) else None
        lines.append(
            f"- {row.get('timelineId') or '?'} {role}: subject {row.get('expectedAction')} "
            f"command at {command.get('date')} -> state boundary {row.get('stateBoundary')} "
            f"(command-to-state {command.get('commandToStateMs')} ms)."
        )
        if controller:
            lines.append(
                f"  physical-controller: {controller.get('sourceLabel')} "
                f"button {controller.get('button') or '?'} at {controller.get('date')} "
                f"-> command {controller.get('controllerToCommandMs')} ms later; "
                f"fingerprint={controller.get('fingerprint')}."
            )
        for reaction in row.get("appReactions") or []:
            lines.append(
                f"  downstream-app: {reaction.get('sourceLabel')} "
                f"{reaction.get('afterCommandMs')} ms after command: "
                f"{reaction.get('message')}"
            )

    if native_log_provenance_sufficient(correlations):
        lines.append(
            "DETERMINISTIC RESULT: the same physical controller/input immediately "
            "preceded both the subject ON command and the later OFF command. Present "
            "that controller/input as the strongest initiating-control candidate. "
            "If an app reaction is logged only after the ON command, describe the app "
            "as downstream handling rather than the initiator. Preserve the caveat "
            "that timestamp repetition does not independently prove the configured "
            "mapping."
        )
    return "\n".join(lines)


__all__ = [
    "causal_boundary_log_windows",
    "correlate_native_log_boundaries",
    "native_log_provenance_sufficient",
    "render_native_log_correlation",
]
