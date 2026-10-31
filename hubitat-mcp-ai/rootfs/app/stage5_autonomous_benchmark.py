"""Stage 5 read-only, synthetic, independent cloud investigation pilot.

The actual cloud model chooses 0-2 sources from a fictional catalog before
writing a natural answer and independently selected cited finding types.
No suggested answer candidates, real MCP calls, user evidence, agent routing
or publisher changes. The host owns source/claim reference scoring; generated
prose is intentionally NOT semantically certified.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import re
import time
from typing import Any

import httpx

from cloud_benchmark import BenchmarkError, benchmark_status
from chat_transport import EmptyOllamaAssistantMessage


def _source(source_id: str, name: str, event_id: str, kind: str, **fields: Any) -> dict:
    return {"id": source_id, "name": name, "records": [
        {"id": event_id, "kind": kind, "synthetic": True, **fields}
    ]}


# Gold source choices and required fact kinds are deliberately kept outside
# all model-facing payloads. All IDs and device names are fictional.
_CASES = {
    "lighting": {
        "title": "Why did the fictional lounge light come on?",
        "question": "Explain the observed light transition, what likely relates to it, and what cannot be verified.",
        "initial": {"id": "I1", "kind": "state_report", "at": "12:04:03Z",
                    "device": "Fictional Lounge Light", "state": "on",
                    "physical_confirmation": False},
        "catalog": [
            _source("S3", "Unrelated kitchen socket meter",
                    "E3", "power_meter", at="12:03:59Z", watts=25),
            _source("S2", "Motion sensor state events in the same interval",
                    "E2", "sensor_report", at="12:03:55Z",
                    sensor="Fictional Lounge Motion", state="active",
                    delivered_to_controller="unknown"),
            _source("S4", "Lighting configuration last saved",
                    "E4", "configuration", at="11:10:00Z",
                    timeout_seconds=30, does_not_prove_runtime_decision=True),
            _source("S1", "Controller's device command history",
                    "E1", "command_record", at="12:04:01Z",
                    command="setLevel", level=60, issuer="Fictional Lighting App",
                    upstream_trigger="not independently recorded",
                    physical_confirmation=False),
        ],
        "gold_sources": ("S1", "S2"),
        "required_kinds": ("state_report", "command_record", "issuer_record"),
    },
    "heating": {
        "title": "Heating demand despite a warm room",
        "question": "Explain the fictional heating report while the room seems above its target. What does the available evidence establish?",
        "initial": {"id": "I1", "kind": "state_report", "at": "17:05:00Z",
                    "device": "Fictional Thermostat", "state": "heating",
                    "physical_confirmation": False},
        "catalog": [
            _source("S2", "Room temperature and target observations",
                    "E2", "sensor_report", at="17:05:00Z",
                    device="Fictional Hallway Sensor", temperature_c=22.8,
                    target_c=22.0, source_clock="reported"),
            _source("S3", "Unrelated garden thermometer",
                    "E3", "sensor_report", at="17:04:00Z",
                    device="Fictional Garden Sensor", temperature_c=8),
            _source("S1", "Heating scheduler's latest decision records",
                    "E1", "app_decision", at="17:04:56Z",
                    decision="protection period active",
                    note="device heat report alone does not prove valve or boiler operation"),
            _source("S4", "Heating scheduling configuration",
                    "E4", "configuration", at="15:00:00Z",
                    scheduled_target_c=22.0, no_execution_receipt=True),
        ],
        "gold_sources": ("S1", "S2"),
        "required_kinds": ("state_report", "sensor_report", "app_decision"),
    },
    "ventilation": {
        "title": "Fan boost unexpectedly active",
        "question": "Explain the fictional fan boost report and assess whether humidity or a schedule is established as its cause.",
        "initial": {"id": "I1", "kind": "state_report", "at": "11:02:10Z",
                    "device": "Fictional Bathroom Boost", "state": "on",
                    "physical_confirmation": False},
        "catalog": [
            _source("S4", "Unrelated hallway button activity",
                    "E4", "button_report", at="11:02:02Z", state="pushed"),
            _source("S1", "Ventilation schedule decisions",
                    "E1", "app_decision", at="11:02:03Z",
                    decision="scheduled ventilation boost triggered",
                    source="Fictional Fan Scheduler", does_not_confirm_motor=True),
            _source("S3", "Humidity readings around the transition",
                    "E3", "sensor_report", at="11:02:04Z",
                    device="Fictional Bathroom Humidity", humidity_percent=51,
                    causation_established=False),
            _source("S2", "Fan rule configuration last edited",
                    "E2", "configuration", at="09:00:00Z",
                    humidity_boost_threshold_percent=65,
                    not_a_runtime_trigger_receipt=True),
        ],
        "gold_sources": ("S1", "S3"),
        "required_kinds": ("state_report", "app_decision", "sensor_report"),
    },
    "connectivity": {
        "title": "Why did a fictional mesh plug go offline?",
        "question": "Investigate the plug's last contact and scheduled OFF, distinguishing evidence from an unverified root cause.",
        "initial": {"id": "I1", "kind": "state_report", "at": "01:30:01Z",
                    "device": "Fictional Mesh Plug", "state": "offline",
                    "state_basis": "watchdog", "physical_confirmation": False},
        "catalog": [
            _source("S3", "Outdoor ambient temperature",
                    "E3", "sensor_report", at="01:30:00Z", temperature_c=6),
            _source("S1", "Automation command log near last contact",
                    "E1", "command_record", at="01:30:01Z",
                    command="off", issuer="Fictional Night Power Rule",
                    physical_confirmation=False, upstream_trigger="rule schedule"),
            _source("S4", "Mesh topology configuration",
                    "E4", "configuration", at="00:00:00Z",
                    expected_router="Fictional Mesh Node", actual_path="unknown"),
            _source("S2", "MQTT driver versus device health reports",
                    "E2", "sensor_report", at="01:40:00Z",
                    driver_broker_session="connected", plug_health="offline",
                    proves_plug_online=False),
        ],
        "gold_sources": ("S1", "S2"),
        "required_kinds": ("state_report", "command_record", "issuer_record", "sensor_report"),
    },
}

_SOURCE_KIND = {
    "state_report": {"state_report"},
    "command_record": {"command_record"},
    "issuer_record": {"command_record"},
    "sensor_report": {"sensor_report"},
    "app_decision": {"app_decision"},
    "coverage_gap": {"coverage_gap"},
    "physical_confirmation": {"physical_confirmation"},
    "upstream_cause": {"upstream_cause"},
    "absence_proven": {"absence_proven"},
}
_MAX_CALLS_IN_HOUR = 10
_MAX_SELECTED = 2
_MAX_TEXT = 1800


def _json_object(raw: str) -> dict:
    if not isinstance(raw, str) or not 1 <= len(raw) <= 14000:
        raise ValueError("missing or excessive response")
    value = raw.strip()
    if value.startswith(chr(96) * 3):
        marker = chr(96) * 3
        m = re.fullmatch(re.escape(marker) + r"(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n" +
                         re.escape(marker), value, flags=re.I)
        if m is None:
            raise ValueError("invalid JSON fence")
        value = m.group(1)
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("JSON object required")
    return parsed


def _plan_response(raw: str, scenario: dict) -> list[str]:
    data = _json_object(raw)
    if set(data) != {"schema", "select_sources"} or data["schema"] != "homebrain-stage5-plan.v1":
        raise ValueError("invalid plan schema")
    ids = data["select_sources"]
    valid = {s["id"] for s in scenario["catalog"]}
    if (not isinstance(ids, list) or not 1 <= len(ids) <= _MAX_SELECTED
            or any(not isinstance(i, str) or i not in valid for i in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("unsafe or duplicate source choice")
    return ids


def _answer_response(raw: str, accessible_records: list[dict]) -> dict:
    data = _json_object(raw)
    if (set(data) != {"schema", "answer", "findings", "limitations"}
            or data["schema"] != "homebrain-stage5-answer.v1"):
        raise ValueError("invalid answer schema")
    answer = data["answer"]
    if not isinstance(answer, str) or not 15 <= len(answer.strip()) <= _MAX_TEXT:
        raise ValueError("invalid user explanation")
    if not isinstance(data["limitations"], list) or not 1 <= len(data["limitations"]) <= 4:
        raise ValueError("uncertainty statement required")
    if any(not isinstance(x, str) or not 3 <= len(x.strip()) <= 250 for x in data["limitations"]):
        raise ValueError("invalid limitation statement")
    findings = data["findings"]
    if not isinstance(findings, list) or not 1 <= len(findings) <= 8:
        raise ValueError("missing or excessive claims")
    allowed = {r["id"] for r in accessible_records}
    seen = set()
    for row in findings:
        if (not isinstance(row, dict) or set(row) != {"kind", "source_ids"}
                or row["kind"] not in _SOURCE_KIND
                or not isinstance(row["source_ids"], list)
                or not 1 <= len(row["source_ids"]) <= 3
                or any(not isinstance(s, str) or s not in allowed for s in row["source_ids"])
                or len(row["source_ids"]) != len(set(row["source_ids"]))):
            raise ValueError("unverifiable claim or invalid source citation")
        signature = (row["kind"], tuple(sorted(row["source_ids"])))
        if signature in seen:
            raise ValueError("duplicate claims")
        seen.add(signature)
    return data


def _audit(scenario: dict, selected: list[str], answer: dict) -> dict:
    golden = set(scenario["gold_sources"])
    chosen = set(selected)
    allowed = [scenario["initial"]] + [
        rec for item in scenario["catalog"] if item["id"] in chosen
        for rec in item["records"]
    ]
    records = {r["id"]: r for r in allowed}
    scored = []
    supported_types = set()
    for finding in answer["findings"]:
        kind = finding["kind"]
        kinds = _SOURCE_KIND[kind]
        witnesses = [records[rid] for rid in finding["source_ids"]]
        # No combination of merely nearby events proves a physical outcome,
        # unique upstream cause or absence. The fictional corpus contains
        # no direct verified records for any of those classes.
        proven = bool(witnesses) and all(x["kind"] in kinds for x in witnesses)
        if kind == "issuer_record":
            proven = proven and all(bool(x.get("issuer")) for x in witnesses)
        if proven:
            supported_types.add(kind)
        scored.append({
            "kind": kind,
            "source_ids": finding["source_ids"],
            "host_source_proven": proven,
        })
    unsupported = sum(not item["host_source_proven"] for item in scored)
    high_risk = sum((not item["host_source_proven"]) and
                    item["kind"] in {"physical_confirmation", "upstream_cause", "absence_proven"}
                    for item in scored)
    required = set(scenario["required_kinds"])
    return {
        "source_choices": [{"source_id": item, "expected_relevance": item in golden}
                           for item in selected],
        "relevant_source_recall": f"{len(chosen & golden)}/{len(golden)}",
        "irrelevant_source_selections": len(chosen - golden),
        "findings": scored,
        "proven_cited_findings": len(scored) - unsupported,
        "unsupported_cited_findings": unsupported,
        "high_risk_unsupported_findings": high_risk,
        "required_finding_coverage": f"{len(required & supported_types)}/{len(required)}",
        "uncovered_expected_finding_types": sorted(required - supported_types),
        "prose_semantics_independently_verified": False,
        "answer_completeness_proven": False,
        "human_clarity_review_required": True,
        "publisher_approval": False,
    }


def stage5_status(transport: Any) -> dict:
    status = benchmark_status(transport)
    return {
        "available": status["available"],
        "reason": status["reason"],
        "model": status["model"],
        "cases": [{"id": k, "title": v["title"]} for k, v in _CASES.items()],
        "maximum_cloud_requests_per_test": 2,
        "existing_primary_account_only": True,
        "no_live_mcp_or_devices": True,
        "publication_approval": False,
    }


def _safe_cloud_error(exc: Exception, phase: str) -> BenchmarkError:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        category = ("credentials/permissions" if code in (401, 403)
                    else "quota/rate limit" if code == 429
                    else "model/endpoint" if code == 404
                    else "request format" if code == 400
                    else "provider server error" if code >= 500
                    else "provider response error")
    elif isinstance(exc, httpx.TimeoutException):
        category = "timeout (allowance may have been used)"
    elif isinstance(exc, httpx.RequestError):
        category = "connection error"
    elif isinstance(exc, EmptyOllamaAssistantMessage):
        category = "empty assistant response"
    elif isinstance(exc, (ValueError, KeyError, TypeError, json.JSONDecodeError)):
        category = "invalid structured model response"
    else:
        category = "unexpected benchmark processing error"
    return BenchmarkError(502, f"Stage 5 {phase} failed: {category}. No retry was attempted.")


class Stage5Benchmark:
    def __init__(self, *, clock=None):
        self._clock = clock if clock is not None else time.monotonic
        self._lock = asyncio.Lock()
        self._calls: deque[float] = deque()

    async def _ask(self, transport: Any, messages: list[dict]) -> str:
        # Count a provider attempt BEFORE dispatch, including timeouts. No
        # retry, no local fallback, no household rotation, no tool declarations.
        self._calls.append(self._clock())
        reply = await transport._chat_post(
            messages, [], base_url=transport.base_url,
            model_name=transport.model_name, api_key=transport.api_key,
            timeout=httpx.Timeout(min(90.0, max(10.0, transport.timeout_seconds))),
            keep_alive=None, disable_thinking=True,
        )
        if reply.get("tool_calls"):
            raise ValueError("tool calls forbidden")
        return reply.get("content", "")

    async def run_case(self, transport: Any, case_id: str, *, confirmed: bool) -> dict:
        if confirmed is not True:
            raise BenchmarkError(400, "Confirm permission for up to two Ollama Cloud requests.")
        if case_id not in _CASES:
            raise BenchmarkError(400, "Unknown Stage 5 fictional scenario.")
        ready = stage5_status(transport)
        if not ready["available"]:
            raise BenchmarkError(503, "The existing primary official Ollama Cloud connection is unavailable.")
        if self._lock.locked():
            raise BenchmarkError(429, "Another Stage 5 test is running.")
        now = self._clock()
        while self._calls and now - self._calls[0] >= 3600:
            self._calls.popleft()
        if len(self._calls) > _MAX_CALLS_IN_HOUR - 2:
            raise BenchmarkError(429, "Stage 5 hourly allowance reached. No cloud calls were made.")
        if self._calls and now - self._calls[-1] < 10:
            raise BenchmarkError(429, "Stage 5 cooldown active. No cloud calls were made.")
        case = _CASES[case_id]
        async with self._lock:
            initial = case["initial"]
            catalog = [{"id": src["id"], "name": src["name"]}
                       for src in case["catalog"]]
            first = [
                {"role": "system", "content": (
                    "Investigate a FICTIONAL smart-home incident. All available "
                    "sources are synthetic and read-only. Select up to two "
                    "additional records you would inspect, without suggested "
                    "answers or external tools. Return ONLY JSON with exact keys "
                    "schema and select_sources. schema is homebrain-stage5-plan.v1. "
                    "select_sources is an array of one or two distinct source IDs."
                )},
                {"role": "user", "content": json.dumps(
                    {"question": case["question"], "initial_observation": initial,
                     "available_sources": catalog}, separators=(",", ":"))},
            ]
            started = self._clock()
            before = len(self._calls)
            try:
                selection = _plan_response(await self._ask(transport, first), case)
            except Exception as exc:
                raise _safe_cloud_error(exc, "evidence selection") from None
            sources = [src for src in case["catalog"] if src["id"] in selection]
            accessible = [initial] + [record for s in sources for record in s["records"]]
            second = [
                {"role": "system", "content": (
                    "Explain a fictional incident in natural language, based "
                    "ONLY on the shown records. Preserve uncertainty and never "
                    "promote commands, nearby timing or app settings to proven "
                    "physical outcomes or causes. Write the answer yourself; "
                    "there are no candidate conclusions. Output ONLY one JSON "
                    "object with exact keys schema, answer, findings, limitations. "
                    "schema: homebrain-stage5-answer.v1. answer: natural concise "
                    "paragraph up to 1800 chars. findings: array 1-8 of {kind, "
                    "source_ids}, where kind is one of state_report, "
                    "command_record, issuer_record, sensor_report, app_decision, "
                    "coverage_gap, physical_confirmation, upstream_cause, "
                    "absence_proven; source_ids names 1-3 record IDs actually "
                    "shown. limitations: array of 1-4 short strings describing "
                    "unverified facts. No extra JSON keys or markdown."
                )},
                {"role": "user", "content": json.dumps({
                    "question": case["question"],
                    "initial_observation": initial,
                    "chosen_source_records": [{"source_id": s["id"], "records": s["records"]}
                                              for s in sources],
                }, separators=(",", ":"))},
            ]
            try:
                draft = _answer_response(await self._ask(transport, second), accessible)
                audit = _audit(case, selection, draft)
            except Exception as exc:
                raise _safe_cloud_error(exc, "final explanation") from None
            return {
                "success": True,
                "title": case["title"],
                "case_id": case_id,
                "model": ready["model"],
                "cloud_requests_attempted": len(self._calls) - before,
                "elapsed_ms": round((self._clock() - started) * 1000),
                "answer": draft["answer"],
                "limitations": draft["limitations"],
                "synthetic_only": True,
                "no_live_device_access": True,
                **audit,
            }


__all__ = ["Stage5Benchmark", "stage5_status", "BenchmarkError"]
