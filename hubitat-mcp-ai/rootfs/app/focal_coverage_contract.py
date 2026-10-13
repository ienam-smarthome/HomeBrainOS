"""Focal-event source classes for the public investigation coverage contract.

A successful unbounded native event feed can include newer *unrelated* OFF
transitions. Its presence must not satisfy the requested historical focal
event requirement. Conversely, a Historical Journal OFF at collector receipt
time can support an observed OFF without proving an original native state
timestamp. This helper does not modify the event collector or device state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def reconcile_focal_requirement_sources(
    receipts: list[dict[str, Any]],
    found: set[str],
    checked: set[str],
    notes: list[str],
) -> tuple[dict[str, str], dict[str, Any] | None]:
    """Correctly attribute a specifically requested lockout event by source.

    Only act on a host-evaluated, explicitly time-scoped focal investigation.
    Older generic/manual-history requests preserve their existing assessor
    behavior. Source absence remains unverified rather than a negative claim.
    """
    detail = next((
        row.get("details")
        for row in reversed(receipts)
        if isinstance(row, dict)
        and row.get("tool") == "homebrain_motion_lockout_investigation"
        and row.get("success") is True
        and isinstance(row.get("details"), dict)
        and isinstance((row.get("details") or {}).get("focalSelection"), dict)
        and (row["details"]["focalSelection"]).get("explicitTargetUtc")
    ), None)
    if not isinstance(detail, dict):
        return {}, None

    selection = detail["focalSelection"]
    target = _at(selection.get("explicitTargetUtc"))
    if target is None:
        return {}, None
    native_off = _at(selection.get("selectedOff"))
    native_observed = (
        native_off is not None
        and abs((native_off-target).total_seconds()) <= 3
    )
    source_classes: dict[str, str] = {}
    fusion = detail.get("crossSourceFocalProvenance") or {}
    journal_off = False
    journal_off_time = None
    journal_off_basis = None
    target_light = str(detail.get("lightDeviceId") or "")
    for item in detail.get("journal") or []:
        if (
            not isinstance(item, dict)
            or item.get("kind") != "light"
            or str(item.get("deviceId") or "") != target_light
        ):
            continue
        for row in item.get("observations") or []:
            if not isinstance(row, dict):
                continue
            stamp = _at(row.get("observedAt"))
            if (
                stamp is None or str(row.get("value") or "").casefold() != "off"
                or not 0 <= (stamp-target).total_seconds() <= 5
            ):
                continue
            journal_off = True
            journal_off_time = stamp.isoformat(timespec="milliseconds")
            journal_off_basis = str(row.get("timestampBasis") or "unknown")
            break
        if journal_off:
            break

    # Supersede unscoped newer OFF rows which previously caused false
    # "observed from native switch-event history" in the public API.
    found.discard("target_off")
    if native_observed:
        found.add("target_off")
        source_classes["target_off"] = "targeted native light switch-state history"
    elif journal_off:
        found.add("target_off")
        checked.add("target_off")
        source_classes["target_off"] = (
            "Historical Journal OFF observation (collector receipt; "
            "native state-event time unverified)"
        )
        notes.append(
            "Requested OFF appears in collector-received journal observations; "
            "the matching native switch-state event is absent from returned history"
        )
    else:
        checked.add("target_off")
        source_classes["target_off"] = (
            "targeted native light history and Historical Journal checked; "
            "requested OFF not observed in returned sources"
        )

    native_button_command = (
        isinstance(fusion, dict)
        and fusion.get("nativeButtonCommandVerified") is True
        and fusion.get("requestedEventUtc") == target.isoformat()
    )
    selection_manual = (
        selection.get("manualOffVerified") is True
        and bool(selection.get("physicalButtonCommandChain"))
        and native_observed
    )
    found.discard("controller")
    if native_button_command or selection_manual:
        found.add("controller")
        checked.add("controller")
        source_classes["controller"] = (
            "independent native physical button and native app OFF command"
        )
    else:
        checked.add("controller")
        source_classes["controller"] = (
            "targeted controller history; initiating native command unverified"
        )

    motion_rows = [
        row for row in detail.get("motionCorrelations") or []
        if isinstance(row, dict)
    ]
    motion_eligible = any(
        row.get("eligibleActivationSourceVerified") is True
        for row in motion_rows
    )
    found.discard("motion")
    if motion_eligible:
        found.add("motion")
    else:
        checked.add("motion")
    if motion_rows:
        source_classes["motion"] = (
            "Historical Journal motion observations; "
            "activation role verified" if motion_eligible else
            "Historical Journal motion observations; "
            "activation eligibility unverified"
        )
        if not motion_eligible:
            notes.append(
                "Motion was observed after the requested OFF, but historical "
                "eligibility as an activation trigger remains unverified"
            )

    found.discard("execution")
    if detail.get("lockoutExecutionVerified") is True:
        found.add("execution")
    else:
        checked.add("execution")

    evidence = {
        "requestedEventUtc": target.isoformat(),
        "nativeLightOffObserved": native_observed,
        "collectorReceivedLightOffObserved": journal_off,
        "collectorLightOffAtUtc": journal_off_time,
        "nativeButtonCommandLinked": bool(
            native_button_command or selection_manual
        ),
        "postOffMotionObserved": bool(motion_rows),
        "motionActivationEligibilityVerified": motion_eligible,
        "historicalLockoutExecutionVerified": (
            detail.get("lockoutExecutionVerified") is True
        ),
        "currentSettingsDoNotProvePastExecution": True,
        "unrelatedNativeHistoryDoesNotMeetFocalProof": True,
        "journalCaptureComplete": False,
    }
    return source_classes, evidence


__all__ = ["reconcile_focal_requirement_sources"]
