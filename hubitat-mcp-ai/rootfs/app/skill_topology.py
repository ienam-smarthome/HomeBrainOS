"""Plan read-only topology discovery from actual scoped evidence, not room guesses."""
from __future__ import annotations

from typing import Any

from causal_evidence_graph import build_causal_evidence_graph
from causal_command_provenance import preceding_command_candidates


def build_topology_plan(
    evidence: list[dict[str, Any]], question: str,
) -> dict[str, Any] | None:
    graph = build_causal_evidence_graph(evidence, question)
    if graph.get("scope") != "single-observed-event":
        return None
    focus = graph.get("focus") or {}
    subject = str(focus.get("subject") or "")
    on = str(focus.get("on") or "")
    clues = preceding_command_candidates(
        evidence, subject=subject, transition="on",
        requested_boundary=on,
    ) if subject and on else []
    direct = graph.get("directCommand") or {}
    producer = (direct.get("producer") or {}) if direct else (
        (clues[0].get("producer") or {}) if clues else {}
    )
    app_id = str(producer.get("id") or "")
    checked_config = set()
    checked_scoped_logs = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        args = item.get("arguments") or {}
        if isinstance(args.get("args"), dict):
            args = args["args"]
        if not isinstance(args, dict):
            continue
        leaf = str(item.get("sub_tool") or args.get("tool") or "")
        inspected_app_id = str(args.get("appId") or args.get("appID") or "")
        if leaf == "hub_get_app_config" and inspected_app_id:
            checked_config.add(inspected_app_id)
        if leaf == "hub_get_logs" and inspected_app_id:
            checked_scoped_logs.add(inspected_app_id)
    reads = []
    if app_id and app_id not in checked_config:
        reads.append({
            "source": "controlling_app_configuration", "appId": app_id,
            "tool_hint": "hub_get_app_config",
            "question": "Which device subscriptions, nested pages and MQTT/controller inputs can issue this command?",
            "priority": "high",
        })
    if app_id and app_id not in checked_scoped_logs:
        reads.append({
            "source": "controlling_app_logs", "appId": app_id,
            "tool_hint": "hub_get_logs",
            "question": "Is command handler execution recorded in the bounded event-time window?",
            "priority": "medium",
        })
    if clues:
        reads.append({
            "source": "upstream_controller", "appId": app_id,
            "tool_hint": "hub_search_tools / hub_get_tool_guide",
            "question": "If app config shows an upstream MQTT or touch topic, can it be corroborated without exposing secrets?",
            "priority": "high",
        })
    return {
        "schema": "homebrain-skill-topology/v1",
        "target": subject,
        "commandProducer": {"appId": app_id, "label": producer.get("label")},
        "currentSourceCoverage": {
            "appConfiguration": "checked" if app_id in checked_config else "not-checked",
            "appScopedLogs": "checked" if app_id in checked_scoped_logs else "not-checked",
            "historicalConfigurationVerified": False,
        },
        "recommendedReads": reads[:3],
        "constraints": [
            "Discover live leaf schemas before making a call",
            "Do not treat current configuration as proof of past execution",
            "Never print or forward MQTT credentials",
        ],
    }


def render_topology_plan(
    evidence: list[dict[str, Any]], question: str,
) -> str | None:
    plan = build_topology_plan(evidence, question)
    if not plan or not plan["recommendedReads"]:
        return None
    lines = ["HOST SKILL TOPOLOGY INVESTIGATION PLAN (read-only):"]
    producer = plan["commandProducer"]
    if producer.get("appId"):
        lines.append(
            f"Recorded command producer: {producer.get('label') or 'Hubitat app'} "
            f"(app {producer['appId']}); a device state bridge is not its upstream actor."
        )
    for step in plan["recommendedReads"]:
        lines.append(
            f"- {step['source']} [{step['priority']}]: {step['tool_hint']}; "
            f"{step['question']} AppId={step.get('appId') or 'unknown'}."
        )
    lines.append(
        "Follow only decisive reads permitted by the declared live MCP catalog. "
        "If logs are expired, stop and report a historical coverage gap. "
        "Never disclose app secrets or infer past execution from current settings."
    )
    return "\n".join(lines)


__all__ = ["build_topology_plan", "render_topology_plan"]
