"""Opt-in, in-app synthetic Ollama Cloud benchmark.

Uses only the already-configured PRIMARY direct-cloud account and exact model.
Never invokes the ordinary agent, MCP, local fallback, paid routing or controls.
A source-shaped citation is not semantic proof; the browser displays an
unverified model proposal so its actual reasoning can be inspected.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import httpx

from stage4_narrative_contract import (
    build_stage4_evidence_packet, validate_stage4_model_draft,
)
from stage4k_frozen_answer_audit import freeze_stage4k_answer

_CLOUD_HOST = "https://ollama.com"
_COOLDOWN_SECONDS = 90
_MAX_RESPONSE = 32768
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,95}$")
_CASES = (
    ("lighting", "Lighting command",
     "What can be concluded from an issued brightness command? Explain whether the initiating motion sensor or physical light state is proven.",
     "A brightness command is recorded. The sensor that initiated it and the light's physical response are not established.",
     "101", "201", "setLevel"),
    ("heating", "Heating demand",
     "What does a recorded heating setpoint command prove? Can it establish that the boiler fired or radiator valves opened?",
     "A heating setpoint command was issued. The boiler firing and valve opening are not independently proven.",
     "102", "202", "setHeatingSetpoint"),
    ("ventilation", "Ventilation fan",
     "What does the recorded fan OFF command establish? Does it prove the fan motor stopped or that humidity caused the command?",
     "A fan OFF command is recorded, but physical motor response and humidity as the upstream cause are not proven.",
     "103", "203", "off"),
    ("history", "History coverage",
     "Explain the contact reading's clock basis and what the partial archived history does not prove.",
     "The contact observation has a collector reception timestamp, not an independently established source time. The recorded gap prevents claiming complete history or absence of other events.",
     "104", "", ""),
)


class BenchmarkUnavailable(Exception):
    """Safe, user-displayable status without provider error details."""


class BenchmarkBusy(Exception):
    """A prior request is running or a cooldown remains."""


def _constructed_receipt(case: tuple[str, ...]) -> dict[str, Any]:
    _, _, _, _, device, issuer, action = case
    if action:
        return {
            "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": device}},
            "details": {"observedEvents": [{
                "name": "command-" + action,
                "date": "2026-01-01T12:00:00Z",
                "producedBy": {"appId": issuer,
                               "name": "Fictional Test Controller"},
            }]},
        }
    return {
        "tool": "homebrain_evidence_journal",
        "success": True, "effect": "read",
        "evidence_kind": "group_archived_input_history",
        "arguments": {"device_id": device},
        "details": {
            "deviceId": device, "gapCount": 2, "truncated": True,
            "observations": [{
                "device_id": device, "attribute": "contact", "value": "open",
                "timestamp_basis": "collector-received",
                "date": "2026-01-01T12:01:00Z",
            }],
        },
    }


def _schema(packet: dict[str, Any]) -> dict[str, Any]:
    ids = [fact["fact_id"] for fact in packet["facts"]]
    if not ids or len(ids) > 8 or len(set(ids)) != len(ids):
        raise ValueError("invalid synthetic source")
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "schema": {"const": "homebrain-cloud-benchmark.v1"},
            "sentences": {
                "type": "array", "minItems": 1, "maxItems": 3,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "text": {"type": "string", "minLength": 1,
                                 "maxLength": 500},
                        "fact_ids": {
                            "type": "array", "minItems": 1, "maxItems": 2,
                            "uniqueItems": True,
                            "items": {"type": "string", "enum": ids},
                        },
                    },
                    "required": ["text", "fact_ids"],
                },
            },
        },
        "required": ["schema", "sentences"],
    }


def _frozen_draft(proposal: Any, packet: dict[str, Any]) -> dict[str, Any]:
    """Host builds exact typed source witnesses, not model assertions."""
    if (not isinstance(proposal, dict)
            or set(proposal) != {"schema", "sentences"}
            or proposal["schema"] != "homebrain-cloud-benchmark.v1"
            or not isinstance(proposal["sentences"], list)
            or not 1 <= len(proposal["sentences"]) <= 3):
        raise ValueError("invalid benchmark output")
    facts = {f["fact_id"]: f for f in packet["facts"]}
    rows = []
    for sentence in proposal["sentences"]:
        if not isinstance(sentence, dict) or set(sentence) != {"text", "fact_ids"}:
            raise ValueError("invalid sentence")
        text = sentence["text"]
        ids = sentence["fact_ids"]
        if (not isinstance(text, str) or not text.strip()
                or len(text) > 500 or "\x00" in text
                or not isinstance(ids, list) or not 1 <= len(ids) <= 2
                or any(not isinstance(fid, str) or fid not in facts for fid in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("invalid source citation")
        witnesses = []
        for fid in ids:
            fact = facts[fid]
            if fact["kind"] == "coverage_limit":
                keys = ("fact_id", "kind", "entity_id", "source",
                        "gap_count", "truncated", "complete")
            elif fact["kind"] in ("issued_command", "reported_state", "input_report"):
                keys = ("fact_id", "kind", "entity_id", "attribute",
                        "value", "clock_basis", "time_utc",
                        "issuer_app_id", "physical_ack_verified")
            else:
                raise ValueError("unknown evidence kind")
            witnesses.append({field: fact[field] for field in keys})
        rows.append({"text": text, "citations": ids, "claims": witnesses})
    return {"schema": "homebrain-stage4-draft.v1",
            "sections": [{"name": "evidence", "sentences": rows}]}


class CloudBenchmark:
    """Bounded, no-retry direct-cloud evaluation using an existing transport.

    No disk writes or provider conversation history. In-memory cooldown and
    lock guard against accidental double tap / concurrent credit spending.
    """

    def __init__(self, transport: Any, *, cooldown_seconds: float = _COOLDOWN_SECONDS):
        self.transport = transport
        self._lock = asyncio.Lock()
        self._last_attempt = float("-inf")
        self._cooldown = cooldown_seconds

    def _configured(self) -> bool:
        t = self.transport
        return (
            t.configured and t.base_url == _CLOUD_HOST
            and bool(_MODEL_RE.fullmatch(t.model_name))
        )

    def status(self) -> dict[str, Any]:
        remaining = max(0, self._cooldown - (time.monotonic() - self._last_attempt))
        return {
            "configured": self._configured(),
            "model": self.transport.model_name if self._configured() else None,
            "provider": "Ollama Cloud (existing primary account)",
            "cases": [{"id": c[0], "title": c[1]} for c in _CASES],
            "running": self._lock.locked(),
            "retry_after_seconds": int(remaining + 0.999),
            "manual_only": True, "one_cloud_request_per_run": True,
            "household_data_used": False, "mcp_tools_enabled": False,
            "model_fallback_enabled": False, "publisher_changed": False,
        }

    async def run(self, case_id: str) -> dict[str, Any]:
        if not self._configured():
            raise BenchmarkUnavailable(
                "The primary Ollama Cloud key and official HTTPS endpoint must be configured."
            )
        case = next((c for c in _CASES if c[0] == case_id), None)
        if case is None:
            raise ValueError("Unknown synthetic benchmark case")
        if self._lock.locked():
            raise BenchmarkBusy("A benchmark is already running.")
        async with self._lock:
            if time.monotonic() - self._last_attempt < self._cooldown:
                raise BenchmarkBusy("Benchmark cooldown active; avoid repeat cloud usage.")
            self._last_attempt = time.monotonic()
            receipt = _constructed_receipt(case)
            packet = build_stage4_evidence_packet([receipt])
            prompt = {
                "question": case[2],
                "evidence_packet": packet,
                "required_schema": "homebrain-cloud-benchmark.v1",
            }
            request_body = {
                "model": self.transport.model_name,
                "stream": False,
                "format": _schema(packet),
                "messages": [
                    {"role": "system", "content":
                        "Explain the fictional evidence clearly and naturally. "
                        "Never invent physical effects, upstream causes, absent events "
                        "or complete history. Use only the supplied synthetic facts. "
                        "Respond in JSON using 1-3 concise sentences with exact "
                        "fact_ids for each sentence. Exact citations do not prove "
                        "your natural-language claims."},
                    {"role": "user", "content": json.dumps(prompt, separators=(",", ":"))},
                ],
                "options": {"temperature": 0, "num_predict": 1000},
            }
            start = time.monotonic()
            try:
                response = await self.transport.client.post(
                    _CLOUD_HOST + "/api/chat", json=request_body,
                    headers={"Authorization": "Bearer " + self.transport.api_key},
                    timeout=httpx.Timeout(90.0, connect=6.0),
                    follow_redirects=False,
                )
                if response.status_code != 200:
                    raise BenchmarkUnavailable(
                        "Ollama Cloud did not accept the benchmark. Check the configured account allowance and model."
                    )
                if len(response.content) > _MAX_RESPONSE:
                    raise BenchmarkUnavailable("Ollama Cloud response exceeded benchmark limits.")
                outer = response.json()
                content = outer["message"]["content"]
                if not isinstance(content, str) or not 1 <= len(content) <= 24000:
                    raise ValueError("missing model content")
                proposal = json.loads(content)
                draft = _frozen_draft(proposal, packet)
                valid = validate_stage4_model_draft(draft, packet)
                if valid["structured_claims_valid"] is not True:
                    raise ValueError("unverified structured envelope")
                digest = freeze_stage4k_answer([receipt], draft)
            except BenchmarkUnavailable:
                raise
            except Exception:
                # Never place provider body, generated prose or credentials in logs.
                raise BenchmarkUnavailable(
                    "Cloud request or source-citation validation failed; no device action was performed."
                ) from None
            return {
                "success": True,
                "domain": case[0],
                "title": case[1],
                "model": self.transport.model_name,
                "elapsed_seconds": round(time.monotonic() - start, 2),
                "answer": "\n\n".join(s["text"] for s in proposal["sentences"]),
                "expected_evidence": case[3],
                "source_bound": True,
                "frozen_answer_digest": digest["draft_sha256"],
                "verified_structured_claims": valid["claims_supported"],
                "structured_claims_valid": True,
                "semantic_accuracy_verified": False,
                "independent_review_required": True,
                "publication_approval": False,
                "cloud_calls_attempted": 1,
                "mcp_calls_attempted": 0,
                "device_actions_executed": False,
            }
