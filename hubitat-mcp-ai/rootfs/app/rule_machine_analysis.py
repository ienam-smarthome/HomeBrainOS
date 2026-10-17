"""Deterministic read-only Rule Machine investigation with bounded verified IDs."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from investigation_intelligence import plan_investigation
from investigation_policy import is_history_investigation
from causal_rule_decision_context import configuration_text, referenced_sensor_identities
from device_state_summary import device_attributes
from mcp_client import tool_succeeded
from room_status_snapshot import _device_health, _parent_reliability
from groovy_source_investigation import requested_groovy_app_id

_APP_ID = re.compile(r"\b(?:rule\s+machine\s+)?(?:app|rule)\s*(?:id\s*)?#?\s*(\d{2,7})\b", re.I)
_PARENT_ID = re.compile(r"\bparent\s+(?:device\s+)?(?:id\s*)?#?\s*(\d{2,7})\b", re.I)
_INTENT = re.compile(r"\b(?:analy[sz]e|inspect|audit|review|investigate|verify|check)\b", re.I)
_WRITES = re.compile(
    r"\b(?:change|modify|update|enable|disable|delete|remove|create|edit|pause|resume|turn\s+on|turn\s+off)\b", re.I
)
_PAST_RULE_ACTION = re.compile(
    r"(?i)\b(?:issued|sent|executed|ran|fired|triggered|invoked|"
    r"acknowledged|commanded|performed|actually\s+run|execution\s+logs?|"
    r"command\s+(?:event|history|logs?|acknowledg\w*|provenance)|"
    r"(?:off|on)\s+commands?)\b|\b(?:on|off)\s*\(\s*\)"
)
_HISTORY_VERIFICATION = re.compile(
    r"(?i)\b(?:verify|check|confirm|investigate|determine|establish|"
    r"correlate|reconstruct|prove|whether|did|when|what|who|how|"
    r"execution\s+(?:history|logs?))\b"
)


def historical_rule_execution_request(prompt: str) -> bool:
    """Historic app execution/command provenance must not use config snapshot.

    Recognise this intent independently from the general analytical planner:
    'verify whether app 3950 issued OFF at 01:30' is evidence work, even when
    it contains none of the planner's telemetry or generic causation phrases.
    A current trigger/settings review remains eligible for the fast path.
    """
    value = str(prompt or "")
    return bool(
        _APP_ID.search(value)
        and _PAST_RULE_ACTION.search(value)
        and _HISTORY_VERIFICATION.search(value)
    )


def parse_rule_analysis_request(prompt: str) -> tuple[str, str | None] | None:
    """Intercept only non-mutating requests about a named Rule Machine app."""
    value = str(prompt or "")
    # Installed Groovy-source analysis cannot be answered by this configuration-
    # and-sensor-health-only Rule Machine report.
    if requested_groovy_app_id(value) is not None:
        return None
    if historical_rule_execution_request(value):
        return None
    if not _INTENT.search(value) or _WRITES.search(value):
        return None
    # This fast path reads current configuration and referenced-device health.
    # It cannot satisfy questions about a past event, motion-lockout decision,
    # command provenance or real execution. Let the shared investigation
    # planner route those questions to bounded historical evidence collection.
    if plan_investigation(value) is not None or is_history_investigation(value):
        return None
    match = _APP_ID.search(value)
    if match is None:
        return None
    parent = _PARENT_ID.search(value)
    return match.group(1), (parent.group(1) if parent else None)


def _id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("deviceId") or "").strip()


def _name(item: dict[str, Any] | None, fallback: str) -> str:
    return str((item or {}).get("label") or (item or {}).get("name") or fallback)


def _states(item: dict[str, Any]) -> dict[str, str]:
    return {
        re.sub(r"[^a-z0-9]", "", str(key).casefold()): str(value)
        for key, value in device_attributes(item).items()
        if value is not None
    }



@dataclass(frozen=True, slots=True)
class RuleAnalysisReport:
    message: str
    partial: bool


def _precise_referenced_sensors(
    config_text: str, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Prevent a parent label from falsely matching inside its child's label.

    A configured "FP2 Livingroom sensor (homekit)" must not automatically
    select a separate device labelled "FP2 Livingroom". Match longest full
    labels first and consume their spans before considering shorter labels.
    A genuinely separate occurrence of the parent label remains selectable.
    """

    remaining = str(config_text or "")
    matched = []
    seen = set()
    for candidate in sorted(
        candidates, key=lambda item: len(_name(item, "")), reverse=True
    ):
        label = _name(candidate, "")
        device_id = _id(candidate)
        if not label or not device_id or device_id in seen:
            continue
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(label) + r"(?![A-Za-z0-9])",
            re.I,
        )
        if pattern.search(remaining):
            matched.append(candidate)
            seen.add(device_id)
            remaining = pattern.sub(" ", remaining)
    return matched


def _normalize_detail_device(data: dict[str, Any], expected_id: str) -> dict[str, Any] | None:
    """Project actual hub_get_device(mode=details) sections to canonical states.

    The default MCP summary deliberately has no parentDeviceId. The detailed
    relationships section provides the native parent ID under
    sections.relationships.device.parentDeviceId. The attributes section uses
    fullJson currentStates, not the summary's flat list-of-name/value rows.
    """

    if _id(data) != expected_id or data.get("mode") != "details":
        return None
    sections = data.get("sections")
    if not isinstance(sections, dict):
        return None
    relationships = sections.get("relationships")
    attributes = sections.get("attributes")
    reads = data.get("sectionRead") if isinstance(data.get("sectionRead"), dict) else {}
    relation_status = (reads.get("relationships") or {}).get("status") if isinstance(reads.get("relationships"), dict) else None
    attr_status = (reads.get("attributes") or {}).get("status") if isinstance(reads.get("attributes"), dict) else None
    relation_device = (relationships or {}).get("device") if isinstance(relationships, dict) else None
    native = attributes.get("currentStates") if isinstance(attributes, dict) else None
    states: dict[str, Any] = {}
    if isinstance(native, dict):
        for key, row in native.items():
            if isinstance(row, dict):
                value = row.get("value", row.get("currentValue"))
                if value is None and isinstance(row.get("valueStr"), str):
                    value = row["valueStr"]
            else:
                value = row
            if value is not None:
                states[str(key)] = value
    elif isinstance(native, list):
        states = device_attributes({"attributes": native})
    parent_id = str((relation_device or {}).get("parentDeviceId") or "").strip() if isinstance(relation_device, dict) else ""
    return {
        "id": expected_id,
        "label": data.get("label") or data.get("name") or f"Device {expected_id}",
        "attributes": states,
        "parentDeviceId": parent_id if parent_id.isdecimal() else None,
        "_relationship_unverified": (
            not isinstance(relation_device, dict)
            or (relation_status in {"unavailable", "partial", "failed"} and not parent_id.isdecimal())
        ),
        "_attributes_unverified": not isinstance(native, (dict, list)) or attr_status in {"unavailable", "partial", "failed"},
    }


def build_rule_analysis(
    app_id: str,
    config: dict[str, Any] | None,
    references: list[dict[str, Any]],
    reads: dict[str, dict[str, Any] | None],
    *,
    explicit_parent_id: str | None = None,
    inventory_unavailable: bool = False,
    coverage_limited: bool = False,
) -> RuleAnalysisReport:
    valid = bool(
        isinstance(config, dict)
        and isinstance(config.get("app"), dict)
        and str(config["app"].get("id") or "") == app_id
    )
    excerpts, _ = configuration_text(config) if valid else ([], "")
    name = _name(config["app"], f"App {app_id}") if valid else f"App {app_id}"
    incomplete = not valid or not excerpts or inventory_unavailable or coverage_limited
    lines = [f"### Rule Machine investigation — {name} (app {app_id})"]

    if excerpts:
        lines.append("**Verified current configuration (not execution history):**")
        for entry in excerpts:
            kind = (
                "Trigger" if re.search(r"\bmode\s+(?:changes?|becomes?|switched)", entry, re.I)
                else "Condition/action" if re.search(r"\b(?:if|then|required expression)\b", entry, re.I)
                else "Rule detail"
            )
            lines.append(f"- **{kind}:** {entry}")
        required = any(re.search(r"\brequired\s+expression\s*:", e, re.I) for e in excerpts)
        lines.append(
            "**Required expression:** "
            + ("Listed above; whether it evaluated true at a historical event is unknown."
               if required else
               "Not verified from this configuration view; an editor checkbox is not proof it is enabled.")
        )
    elif valid:
        lines.append(
            "**Configuration incomplete:** The app identity was verified, but its "
            "trigger/condition configuration was not available in usable form."
        )
    else:
        lines.append(
            "**Configuration unavailable:** The direct app configuration read "
            "did not verify this app's triggers, IF conditions or actions."
        )

    parent_reported: set[str] = set()
    if references or explicit_parent_id:
        lines.append("**Referenced sensor states and connectivity (now, not at execution time):**")
    else:
        lines.append(
            "**Sensor dependencies unverified:** No configured sensor identities "
            "were resolved; this does not prove the rule has no dependencies."
        )

    for identity in references:
        id_ = _id(identity)
        label = _name(identity, f"Device {id_}")
        child = reads.get(id_)
        if not isinstance(child, dict):
            lines.append(f"- **{label} (ID {id_}): Health unverified.** Detailed device read unavailable.")
            incomplete = True
            continue
        attrs = _states(child)
        own_health, own_details = _device_health(attrs)
        parent_id = str(child.get("parentDeviceId") or identity.get("parentDeviceId") or "")
        parent = reads.get(parent_id) if parent_id.isdecimal() else None
        if child.get("_relationship_unverified"):
            incomplete = True
        if child.get("_attributes_unverified"):
            incomplete = True
        parent_health, reasons = (
            _parent_reliability(parent) if parent_id.isdecimal() else ("unknown", [])
        )
        unhealthy = own_health is not None or (
            parent_id.isdecimal() and parent_health != "verified"
        ) or bool(child.get("_relationship_unverified"))
        status = own_health or (
            "Parent offline" if parent_health == "offline" else "Parent health unverified"
        ) if parent_id.isdecimal() else (own_health or "Connection status unverified")
        if not own_health and (not parent_id.isdecimal() or parent_health == "unverified"):
            incomplete = True
        retained = ", ".join(
            f"{key}={attrs[key]}" for key in ("motion", "presence", "illuminance")
            if key in attrs
        )
        note = (
            f" Last reported, freshness unverified: {retained}."
            if retained else ""
        )
        lines.append(
            f"- **{label} (ID {id_}): {status}.**"
            + (f" Parent ID {parent_id}." if parent_id.isdecimal() else "")
            + (f" {'; '.join(own_details)}." if own_details else "")
            + note
        )
        if parent_id.isdecimal() and parent_id not in parent_reported:
            parent_reported.add(parent_id)
            parent_label = _name(parent, f"Device {parent_id}")
            state = (
                "Offline" if parent_health == "offline" else
                "Connection reported healthy" if parent_health == "verified" else
                "Connection unverified"
            )
            if parent_health == "unverified":
                incomplete = True
            lines.append(
                f"  - **Linked parent {parent_label} (ID {parent_id}): {state}.**"
                + (f" {'; '.join(reasons)}." if reasons else "")
            )

    if explicit_parent_id and explicit_parent_id not in parent_reported:
        parent = reads.get(explicit_parent_id)
        state, reasons = _parent_reliability(parent)
        display = (
            "Offline" if state == "offline" else
            "Connection reported healthy" if state == "verified" else
            "Connection unverified"
        )
        if state == "unverified":
            incomplete = True
        lines.append(
            f"- **Requested parent {_name(parent, f'Device {explicit_parent_id}')} "
            f"(ID {explicit_parent_id}): {display}.**"
            + (f" {'; '.join(reasons)}." if reasons else "")
            + " An explicit parentDeviceId on a configured child is required to "
              "verify a dependency on this rule."
        )
    if inventory_unavailable:
        lines.append("**Coverage limit:** Cached sensor identities unavailable; named dependencies may be missing.")
    if coverage_limited:
        lines.append("**Coverage limit:** Bounded device reads do not cover every candidate dependency.")
    lines.append(
        "**Could retained sensor values cause an action?** Possibly. A Hubitat "
        "Rule Machine IF condition can evaluate the last stored attribute value "
        "when a separate trigger fires. This alone does not show that a specific "
        "historical run evaluated the IF condition using stale readings."
    )
    lines.append(
        "**Historical cause remains unverified:** Current offline status and "
        "old last-activity timestamps do not establish what was evaluated during "
        "a past rule execution. Adding motion as a trigger alone cannot guarantee "
        "a fresh illuminance value."
    )
    lines.insert(1, (
        "**Investigation status: PARTIAL — some source evidence is unavailable.**"
        if incomplete else
        "**Investigation status: current configuration and device-health reads complete; "
        "past execution still unverified.**"
    ))
    return RuleAnalysisReport("\n\n".join(lines), incomplete)


def render_rule_analysis(*args: Any, **kwargs: Any) -> str:
    """Backwards-compatible text-only format used by presentation callers."""

    return build_rule_analysis(*args, **kwargs).message


class RuleMachineAnalysisService:
    """Bounded Hubitat MCP reads; no AI model calls or device writes."""

    def __init__(self, mcp: Any, evidence: Any) -> None:
        self.mcp, self.evidence = mcp, evidence

    async def _read(
        self, gateway: str, tool: str, args: dict[str, Any],
        *, live: bool = False,
    ) -> dict[str, Any] | None:
        request = {"tool": tool, "args": args}
        start = time.monotonic()
        try:
            result = await self.mcp.call_tool(gateway, request)
            ok = tool_succeeded(result)
            data = result.data if isinstance(result.data, dict) else {}
            if data.get("status") in ("pending", "in_progress"):
                ok = False
        except Exception:
            ok, data = False, {}
        self.evidence.record(
            gateway, request, success=ok,
            elapsed_ms=round((time.monotonic() - start) * 1000),
            summary=f"{tool}: {'read available' if ok else 'read unavailable'}",
            evidence_kind="targeted_device_lookup" if live else "tool_result",
            supports_live_claim=bool(live and ok),
            mutates=False, effect="read",
        )
        return data if ok else None

    async def analyse(self, app_id: str, explicit_parent: str | None) -> RuleAnalysisReport:
        config = await self._read(
            "hub_read_apps_code", "hub_get_app_config",
            {"appId": app_id, "includeSettings": False},
        )
        valid = bool(
            isinstance(config, dict)
            and isinstance(config.get("app"), dict)
            and str(config["app"].get("id") or "") == app_id
        )
        _, config_text = configuration_text(config) if valid else ([], "")
        identities: list[dict[str, Any]] = []
        if valid:
            peek = getattr(self.mcp, "peek_device_identities", None)
            if callable(peek):
                try:
                    identities = [x for x in (peek() or []) if isinstance(x, dict)]
                except Exception:
                    identities = []
            if not identities:
                get = getattr(self.mcp, "get_cached_devices", None)
                if callable(get):
                    try:
                        identities = [x for x in (await get() or []) if isinstance(x, dict)]
                    except Exception:
                        identities = []

        references = (
            _precise_referenced_sensors(
                config_text,
                referenced_sensor_identities(config_text, identities, ""),
            )
            if valid else []
        )
        reads: dict[str, dict[str, Any] | None] = {}
        for ref in references[:4]:
            device_id = _id(ref)
            if not device_id.isdecimal() or device_id in reads:
                continue
            result = await self._read(
                "hub_read_devices", "hub_get_device",
                {
                    "deviceId": device_id,
                    "mode": "details",
                    "sections": ["attributes", "relationships"],
                }, live=True,
            )
            reads[device_id] = (
                _normalize_detail_device(result, device_id)
                if isinstance(result, dict) else None
            )

        parents = set()
        for ref in references:
            record = reads.get(_id(ref))
            parent_id = str(
                (record or {}).get("parentDeviceId") or ref.get("parentDeviceId") or ""
            )
            if parent_id.isdecimal():
                parents.add(parent_id)
        if explicit_parent:
            parents.add(explicit_parent)
        for parent_id in sorted(parents, key=int)[:4]:
            if parent_id not in reads:
                result = await self._read(
                    "hub_read_devices", "hub_get_device",
                    {"deviceId": parent_id}, live=True,
                )
                reads[parent_id] = (
                    result if isinstance(result, dict) and _id(result) == parent_id else None
                )
        return build_rule_analysis(
            app_id, config if valid else None, references, reads,
            explicit_parent_id=explicit_parent,
            inventory_unavailable=bool(valid and config_text and not identities),
            coverage_limited=len(parents) > 4 or len(references) > 4,
        )
