"""Reusable, evidence-driven planning and completion assessment.

A successful MCP call means a source was queried. It does not mean an
investigation established an actual historical event, causal controller,
command reachability, scheduler owner or measured performance saving.

The same small contract is consumed *before* tool selection and *after*
the tools run, without another model round or new hub polling. Keep domain
recognition separate from claim/evidence logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    description: str
    source: str
    necessary: bool = True


@dataclass(frozen=True)
class InvestigationPlan:
    domain: str
    objective: str
    requirements: tuple[EvidenceRequirement, ...]
    stop_rule: str
    forbidden_inferences: tuple[str, ...]
    max_unfocused_reads: int = 0


_PLANS = {
    "manual_motion_lockout": InvestigationPlan(
        domain="manual_motion_lockout",
        objective="Determine if an actual manual OFF event engaged a motion lockout.",
        requirements=(
            EvidenceRequirement("target_off", "A historic OFF event on the affected light",
                                "targeted device switch-event history"),
            EvidenceRequirement("controller", "Manual button/switch event near that OFF",
                                "targeted controller button-event history"),
            EvidenceRequirement("motion", "Motion after the OFF, within the lockout window",
                                "targeted activation-sensor event history"),
            EvidenceRequirement("execution", "Rule decision or lockout log near the OFF",
                                "owning app's time-scoped execution logs"),
        ),
        stop_rule="Without an observed OFF and evidence of a lockout decision, label "
                  "historical engagement unverified; current configuration cannot replace them.",
        forbidden_inferences=(
            "Current lockout=inactive does not establish past engagement.",
            "Current sensor health or motion cannot prove an earlier decision.",
            "A motion event without the OFF boundary cannot prove a manual lockout.",
        ),
    ),
    "device_telemetry": InvestigationPlan(
        domain="device_telemetry",
        objective="Separate operational telemetry freshness, MQTT session state and command reachability.",
        requirements=(
            EvidenceRequirement("status", "Device identity and reported current health",
                                "targeted live device attributes"),
            EvidenceRequirement("freshness", "Actual last device-originated telemetry versus locally calculated age",
                                "targeted device history/lastSeen"),
            EvidenceRequirement("watchdog", "Scoped connection/watchdog evidence",
                                "targeted device logs"),
            EvidenceRequirement("command_path", "Acknowledged delivery or response to a command",
                                "verified non-mutating command transport evidence",
                                necessary=False),
        ),
        stop_rule="Stale telemetry may be established without command testing, "
                  "but ability to receive commands remains unverified.",
        forbidden_inferences=(
            "A connected MQTT flag does not prove recent telemetry.",
            "Watchdog attempts do not prove the device cannot receive commands.",
            "Do not diagnose MQTT LWT failure without explicit broker evidence.",
            "Host-generated dataAgeSeconds increments are not device telemetry.",
        ),
    ),
    "scheduler_ownership": InvestigationPlan(
        domain="scheduler_ownership",
        objective="Separate scheduled entries, verified owners, observed executions and measured load.",
        requirements=(
            EvidenceRequirement("jobs", "Structured list of scheduled entries and handlers",
                                "hub_get_jobs"),
            EvidenceRequirement("owners", "Actual scheduler-provided app/device owner IDs",
                                "owner fields on each scheduler row"),
            EvidenceRequirement("execution", "Executed-call counts or measured busy time",
                                "targeted performance statistics",
                                necessary=False),
        ),
        stop_rule="Without scheduler owner metadata, report handler counts and unknown "
                  "ownership; do not assign candidate ID prefixes as verified owners.",
        forbidden_inferences=(
            "A scheduler-key prefix matching an app/device ID is not owner provenance.",
            "Matching nextRun values do not prove simultaneous execution.",
            "Scheduled entry count is not observed invocation frequency or CPU usage.",
            "Unresolved candidate IDs do not prove obsolete/orphan jobs.",
        ),
    ),
}


def plan_investigation(request: str, *, route_hint: str = "") -> InvestigationPlan | None:
    """Recognise an investigative *goal*, not an automation/rule to patch.

    Broad goal classification is deliberately modest. Ordinary controls and
    status lookups still follow existing routes without an extra contract.
    """
    text = " ".join(str(request or "").casefold().split())
    if not text:
        return None
    analytic = any(stem in text for stem in (
        "investigat", "diagnos", "analys", "analyz", "why ", "determine",
        "establish", "verify", "explain", "optimis", "optimiz", "identify",
    ))
    if not analytic:
        return None
    if ("lockout" in text or "lock-out" in text) and (
        "motion" in text or "occupancy" in text
    ) and any(term in text for term in ("manual", "button", "switch", "turn off")):
        return _PLANS["manual_motion_lockout"]
    if any(term in text for term in ("scheduled job", "scheduled task", "scheduler job",
                                   "scheduled handler", "scheduled work")) and any(
        term in text for term in ("owner", "handler", "efficien", "unnecessary",
                                  "performance", "workload", "optimis", "optimiz")
    ):
        return _PLANS["scheduler_ownership"]
    if any(term in text for term in ("offline", "stale", "not reporting", "last seen",
                                   "no telemetry", "unavailable")) and any(
        term in text for term in ("device", "mqtt", "mesh", "connection", "telemetry",
                                  "reporting", "communication")
    ):
        return _PLANS["device_telemetry"]
    return None


def _leaf(row: dict[str, Any]) -> str:
    """Identify the actual source in both gateway and local-tool receipts."""
    if row.get("sub_tool"):
        return str(row["sub_tool"])
    args = row.get("arguments") or {}
    if isinstance(args, dict) and args.get("tool"):
        return str(args["tool"])
    return str(row.get("tool") or "")


def _args(row: dict[str, Any]) -> dict[str, Any]:
    """Unwrap gateway envelopes without inventing omitted filter parameters."""
    current = row.get("arguments") or {}
    for _ in range(3):
        if not isinstance(current, dict):
            return {}
        inner = current.get("args")
        if not isinstance(inner, dict):
            break
        current = inner
    return current if isinstance(current, dict) else {}


def _events(row: dict[str, Any]) -> list[dict[str, Any]]:
    details = row.get("details") or {}
    if not isinstance(details, dict):
        return []
    for key in ("observedEvents", "events", "logs"):
        records = details.get(key)
        if isinstance(records, list):
            return [x for x in records if isinstance(x, dict)]
    return []


def _instant(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _within_seconds(a: datetime, b: datetime, *, earliest: float,
                    latest: float) -> bool:
    delta = (a - b).total_seconds()
    return earliest <= delta <= latest


def assess_investigation(plan: InvestigationPlan, receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Score evidence by *what it actually observed*, not tool success.

    This assessment is domain-agnostic about the vendor's device/rule names;
    time and entity scope remain requirements of the upstream collector. A
    read with no relevant rows is recorded as checked-empty, never verified.
    """
    source = [r for r in receipts if isinstance(r, dict) and r.get("success") is True]
    found: set[str] = set()
    checked: set[str] = set()
    notes: list[str] = []
    # Cross-source event linking must require actual time alignment. Otherwise
    # a button from yesterday and current motion could produce a false claim
    # that a manual OFF lockout was investigated.
    off_times: list[datetime] = []
    button_times: list[datetime] = []
    motion_times: list[datetime] = []
    lockout_times: list[datetime] = []
    for row in source:
        leaf, args, events = _leaf(row), _args(row), _events(row)
        if plan.domain == "manual_motion_lockout":
            if row.get("tool") == "homebrain_motion_lockout_investigation":
                detail = row.get("details") or {}
                if isinstance(detail, dict):
                    sources = detail.get("sources") or []
                    if any(isinstance(x, dict)
                           and x.get("source") == "bounded-light-device-history"
                           for x in sources):
                        checked.add("target_off")
                    off = _instant(detail.get("focalOff"))
                    if off is not None:
                        found.add("target_off")
                    journal = detail.get("journal") or []
                    if isinstance(journal, list):
                        for entry in journal:
                            if not isinstance(entry, dict):
                                continue
                            kind = entry.get("kind")
                            if kind == "button":
                                checked.add("controller")
                            if kind == "sensor":
                                checked.add("motion")
                            if kind == "sensor" and off is not None:
                                for ev in entry.get("observations") or []:
                                    stamp = _instant(ev.get("observedAt"))
                                    if (stamp is not None
                                            and str(ev.get("value") or "").casefold()
                                            == "active"
                                            and _within_seconds(
                                                stamp, off, earliest=0,
                                                latest=180)):
                                        found.add("motion")
                    if detail.get("nearbyButtonEvents"):
                        found.add("controller")
                    if any(isinstance(x, dict)
                           and x.get("source") == "bounded-app-execution-logs"
                           and x.get("readSucceeded")
                           for x in sources):
                        checked.add("execution")
                    if detail.get("lockoutExecutionVerified") is True:
                        found.add("execution")
                continue
            if leaf == "hub_get_app_config":
                notes.append("Current configuration is context only, not historic execution")
            if leaf in ("hub_list_device_events", "homebrain_device_history"):
                checked.update(("target_off", "controller", "motion"))
                for event in events:
                    attr = str(event.get("name") or event.get("attribute") or "").casefold()
                    value = str(event.get("value") or "").casefold()
                    stamp = _instant(event.get("date") or event.get("timestamp"))
                    if stamp is None:
                        continue
                    if attr == "switch" and value == "off":
                        off_times.append(stamp)
                    if attr in ("button", "pushed", "held", "released"):
                        button_times.append(stamp)
                    if attr in ("motion", "presence", "occupancy"):
                        motion_times.append(stamp)
            if leaf == "hub_get_logs" and args.get("appId") not in (None, ""):
                checked.add("execution")
                for event in events:
                    log = str(event.get("message") or "").casefold()
                    time = _instant(event.get("date") or event.get("timestamp"))
                    if time and ("lockout" in log or "lock out" in log):
                        lockout_times.append(time)
        elif plan.domain == "device_telemetry":
            if leaf in ("hub_get_device", "hub_list_devices", "homebrain_resolve_device"):
                checked.add("status")
                found.add("status")
            if leaf in ("hub_list_device_events", "homebrain_device_history"):
                checked.add("freshness")
                if any(str(x.get("name") or x.get("attribute") or "").casefold()
                       in ("lastseen", "last_seen", "devicehealth", "dataageseconds")
                       for x in events):
                    found.add("freshness")
            if leaf == "hub_get_logs" and args.get("deviceId") not in (None, ""):
                checked.add("watchdog")
                target = str(args["deviceId"])
                if any(
                    str(event.get("deviceId") or "") == target
                    or ("dev|" + target + "|") in str(event.get("message") or "")
                    for event in events
                ):
                    found.add("watchdog")
        elif plan.domain == "scheduler_ownership":
            if leaf == "hub_get_jobs":
                checked.add("jobs")
                found.add("jobs")
                details = row.get("details") or {}
                if isinstance(details, dict):
                    jobs = details.get("scheduledJobs") or details.get("jobs") or []
                    if isinstance(jobs, list) and any(isinstance(x, dict)
                            and any(x.get(k) not in ("", None)
                                    for k in ("appId", "deviceId", "ownerId"))
                            for x in jobs):
                        found.add("owners")
                checked.add("owners")
            if leaf == "hub_get_performance_stats":
                checked.add("execution")
                found.add("execution")
    if plan.domain == "manual_motion_lockout":
        if off_times:
            found.add("target_off")
        if off_times and any(
            _within_seconds(button, off, earliest=-5, latest=5)
            for off in off_times for button in button_times
        ):
            found.add("controller")
        if off_times and any(
            _within_seconds(motion, off, earliest=0, latest=180)
            for off in off_times for motion in motion_times
        ):
            found.add("motion")
        if off_times and any(
            _within_seconds(logged, off, earliest=0, latest=180)
            for off in off_times for logged in lockout_times
        ):
            found.add("execution")
        if off_times and not lockout_times:
            notes.append(
                "OFF may be observed, but past lockout engagement requires "
                "a time-linked execution/decision record"
            )
    requirements = []
    for item in plan.requirements:
        state = ("observed" if item.key in found else
                 "checked-unverified" if item.key in checked else "not-checked")
        requirements.append({
            "key": item.key, "state": state, "necessary": item.necessary,
            "source": item.source, "description": item.description,
        })
    necessary = [x for x in requirements if x["necessary"]]
    complete = all(x["state"] == "observed" for x in necessary)
    status = ("evidence-acquired" if complete else
              "partial-evidence" if any(x["state"] == "observed" for x in necessary)
              else "not-established")
    return {
        "domain": plan.domain, "status": status,
        "evidenceComplete": complete,
        "requirements": requirements,
        "nextMissingSources": [x["source"] for x in necessary if x["state"] != "observed"],
        "stopRule": plan.stop_rule,
        "warnings": list(dict.fromkeys(notes))[:3],
        "noCausalAttributionFromToolSuccess": True,
    }


def render_investigation_plan(plan: InvestigationPlan) -> str:
    payload = {
        "domain": plan.domain, "objective": plan.objective,
        "orderedEvidenceRequirements": [
            {"key": r.key, "source": r.source, "mustObserve": r.description,
             "necessary": r.necessary}
            for r in plan.requirements
        ],
        "stopRule": plan.stop_rule,
        "invalidInferences": plan.forbidden_inferences,
        "retrievalBudget": {"unfocusedHistoryOrLogReads": plan.max_unfocused_reads},
    }
    return "HOST STRUCTURED INVESTIGATION PLAN (read-only):\n" + json.dumps(payload, ensure_ascii=False)


def render_investigation_assessment(
    plan: InvestigationPlan, evidence: list[dict[str, Any]]
) -> str:
    result = assess_investigation(plan, evidence)
    return (
        "HOST EVIDENCE SUFFICIENCY ASSESSMENT (current turn only):\n"
        + json.dumps(result, ensure_ascii=False)
        + "\nDo not describe an unverified evidence requirement as established. "
          "Answer the actual objective rather than replacing it with current "
          "configuration or unrelated system status. Distinguish a checked "
          "source with zero records from a source never checked. If evidence "
          "is incomplete, explain the specific missing evidence and preserve "
          "the unresolved conclusion."
    )


__all__ = [
    "EvidenceRequirement", "InvestigationPlan", "plan_investigation",
    "assess_investigation", "render_investigation_plan",
    "render_investigation_assessment",
]
