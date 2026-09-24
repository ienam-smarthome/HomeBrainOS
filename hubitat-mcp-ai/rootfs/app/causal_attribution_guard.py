"""Deterministic guard against configuration-only causal attribution."""

from __future__ import annotations

import re
from typing import Any

from causal_timeline import build_causal_timeline_rows


_APP_TERM = re.compile(r"\b(?:app|automation|rule|controller)\b", re.I)
_CAUSAL_CLAIM = re.compile(
    r"\b(?:most\s+likely\s+cause|likely\s+(?:cause|trigger)|"
    r"caus(?:e|ed|es)|trigger(?:ed|s)?|responsible\s+for|"
    r"turned\s+(?:it|the\s+device)\s+on)\b",
    re.I,
)
_DIRECT_PROVENANCE_TERM = re.compile(
    r"\b(?:physical\s+button|button\s+(?:press|push)|controller\s+event|"
    r"execution\s+log|native\s+log|command\s+source)\b",
    re.I,
)
_UNRESOLVED_CAVEAT = re.compile(
    r"\b(?:no\s+direct\s+(?:log\s+)?evidence|not\s+established|"
    r"could\s+not\s+confirm|couldn't\s+confirm|unexplained|"
    r"no\s+corresponding\s+(?:controller\s+events?|hub\s+logs?|logs?))\b",
    re.I,
)


def _has_app_configuration(evidence: list[dict[str, Any]]) -> bool:
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        sub_tool = str(receipt.get("sub_tool") or "").casefold()
        if sub_tool in {"hub_get_app_config", "hub_list_apps"}:
            return True
    return False


def _has_aligned_start_controller(evidence: list[dict[str, Any]]) -> bool:
    return any(
        row.get("triggerEvidence")
        for row in build_causal_timeline_rows(evidence)
        if row.get("material")
    )


def guard_configuration_only_causal_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Soften causal app claims that outrun current-turn provenance.

    Installed-app/config reads prove association and capability, not that the app
    initiated one observed transition. If a stronger aligned controller event is
    present, it must outrank configuration. If no direct provenance is present,
    a draft that both names an app as the likely cause and admits provenance is
    unestablished is internally inconsistent and must be softened.
    """

    text = str(message or "")
    if not _has_app_configuration(evidence):
        return text, False
    if not (_APP_TERM.search(text) and _CAUSAL_CLAIM.search(text)):
        return text, False

    has_controller = _has_aligned_start_controller(evidence)
    self_disclaims_proof = _UNRESOLVED_CAVEAT.search(text) is not None

    if not has_controller and not self_disclaims_proof:
        return text, False

    pieces = re.split(r"(?P<space>(?<=[.!?])\s+|\n+)", text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not (_APP_TERM.search(sentence) and _CAUSAL_CLAIM.search(sentence)):
            continue
        if _DIRECT_PROVENANCE_TERM.search(sentence):
            continue
        if has_controller:
            pieces[index] = (
                "The strongest current-turn start-boundary evidence is the aligned "
                "controller event; the checked app/rule configuration can explain "
                "downstream handling, but configuration alone does not establish "
                "that it initiated the turn-on."
            )
        else:
            pieces[index] = (
                "The checked app/rule configuration shows that the automation can "
                "manage this device, but current-turn execution/provenance evidence "
                "does not establish that it initiated this specific turn-on."
            )
        changed = True

    return "".join(pieces), changed


def _producer_identity(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        return "", "", ""
    producer_type = str(value.get("type") or "").strip().casefold()
    if not producer_type:
        if value.get("appId") not in {None, ""}:
            producer_type = "app"
        elif value.get("deviceId") not in {None, ""}:
            producer_type = "device"
    producer_id = str(
        value.get("id")
        or value.get("appId")
        or value.get("deviceId")
        or ""
    ).strip()
    label = str(value.get("label") or value.get("name") or "").strip()
    return producer_type, producer_id, label


def _history_events(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("tool") != "homebrain_device_history"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("boundaryEvents", "commandEvents", "observedEvents"):
            events = details.get(key)
            if not isinstance(events, list):
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                identity = (
                    str(event.get("date") or ""),
                    str(event.get("name") or ""),
                    str(event.get("value") or ""),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(event)
    return rows


def _triggered_only_app_contexts(
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Return apps observed only as downstream listeners on physical events."""

    events = _history_events(evidence)
    direct_ids: set[str] = set()
    direct_labels: set[str] = set()
    for event in events:
        producer_type, producer_id, producer_label = _producer_identity(
            event.get("producedBy")
        )
        if producer_type != "app":
            continue
        if producer_id:
            direct_ids.add(producer_id)
        if producer_label:
            direct_labels.add(producer_label.casefold())

    contexts: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        if str(event.get("type") or "").strip().casefold() != "physical":
            continue
        producer_type, _producer_id, producer_label = _producer_identity(
            event.get("producedBy")
        )
        if producer_type == "app" or not producer_label:
            continue
        triggered = event.get("triggered")
        if not isinstance(triggered, list):
            continue
        for item in triggered:
            if not isinstance(item, dict):
                continue
            app_id = str(item.get("id") or item.get("appId") or "").strip()
            app_label = str(item.get("label") or item.get("name") or "").strip()
            if not app_label:
                continue
            if (
                (app_id and app_id in direct_ids)
                or app_label.casefold() in direct_labels
            ):
                continue
            key = (
                app_id,
                app_label.casefold(),
                producer_label.casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            contexts.append({
                "appId": app_id,
                "appLabel": app_label,
                "producerLabel": producer_label,
                "eventDate": str(event.get("date") or "").strip(),
            })
    return contexts


def guard_triggered_listener_causal_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Prevent triggered-listener metadata being promoted to initiating cause.

    Hubitat state-event triggered entries describe listeners invoked by the
    event. When that same event is physical and structured producedBy points
    to a device/bridge, a triggered app is downstream evidence unless a
    separate command or boundary row independently records that app as producer.
    """

    text = str(message or "")
    contexts = _triggered_only_app_contexts(evidence)
    if not contexts or not _CAUSAL_CLAIM.search(text):
        return text, False

    by_label = {
        row["appLabel"].casefold(): row
        for row in contexts
        if row.get("appLabel")
    }
    generic_context = contexts[0]

    pieces = re.split(r"(?P<space>(?<=[.!?])\s+|\n+)", text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _CAUSAL_CLAIM.search(sentence):
            continue

        sentence_folded = sentence.casefold()
        matched = next(
            (
                row
                for label, row in by_label.items()
                if label and label in sentence_folded
            ),
            None,
        )
        if matched is None:
            # Catch generic claims such as "directly triggered by an automation"
            # when current evidence contains only downstream app listeners and a
            # physical device/bridge producer.
            if not _APP_TERM.search(sentence):
                continue
            matched = generic_context

        app_label = matched["appLabel"]
        producer_label = matched["producerLabel"]
        pieces[index] = (
            f"For this physical state event, {app_label} is recorded only as a "
            f"downstream listener in triggered[]; the event itself was produced "
            f"by {producer_label}. This evidence does not establish that "
            f"{app_label} initiated the transition."
        )
        changed = True

    return "".join(pieces), changed


__all__ = [
    "guard_configuration_only_causal_claim",
    "guard_triggered_listener_causal_claim",
]
