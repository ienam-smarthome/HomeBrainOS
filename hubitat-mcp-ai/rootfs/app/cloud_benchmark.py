"""Optional, synthetic-only Ollama Cloud benchmark using the installed account.

Isolated from the native MCP agent, journal and device control. Only a
bounded, fictional Stage 4A source packet and predetermined test assertions
reach the already-configured primary cloud model. Model text is NOT certified
by the synthetic assertion score.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import time
from typing import Any

import httpx

from stage4_narrative_contract import build_stage4_evidence_packet


class BenchmarkError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _command(device: str, issuer: str, action: str) -> dict:
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": device}},
        "details": {"observedEvents": [{
            "name": "command-" + action,
            "date": "2026-01-01T12:00:00Z",
            "producedBy": {"appId": issuer, "name": "Fictional Controller"},
        }]},
    }


def _history() -> dict:
    return {
        "tool": "homebrain_evidence_journal",
        "success": True, "effect": "read",
        "evidence_kind": "group_archived_input_history",
        "arguments": {"device_id": "904"},
        "details": {"deviceId": "904", "gapCount": 2, "truncated": True,
                    "observations": [{
                        "device_id": "904", "attribute": "contact",
                        "value": "open", "timestamp_basis": "collector-received",
                        "date": "2026-01-01T12:01:00Z",
                    }]},
    }


# Labels are withheld from the model. These labels are synthetic benchmark
# expectations, NOT evidence that a model's unconstrained prose is sound.
_CASES = {
    "lighting": {
        "title": "Lighting command and cause",
        "question": "What can be concluded from the recorded lighting command?",
        "receipts": [_command("901", "801", "setLevel")],
        "checks": [
            ("c1", "A brightness command is recorded.", True),
            ("c2", "The initiating motion sensor has been identified.", False),
            ("c3", "The lamp has been independently verified as physically on.", False),
            ("c4", "The source identifies the immediate issuing application.", True),
        ],
    },
    "heating": {
        "title": "Heating setpoint versus physical heat",
        "question": "Does the setpoint command demonstrate boiler or radiator operation?",
        "receipts": [_command("902", "802", "setHeatingSetpoint")],
        "checks": [
            ("c1", "A heating setpoint command is recorded.", True),
            ("c2", "The boiler is proven to have fired.", False),
            ("c3", "The radiator valve is proven to have opened.", False),
            ("c4", "The recorded command identifies its immediate issuing app.", True),
        ],
    },
    "ventilation": {
        "title": "Fan command and humidity attribution",
        "question": "What does the fan command establish about cause and effect?",
        "receipts": [_command("903", "803", "off")],
        "checks": [
            ("c1", "The source records a fan OFF command.", True),
            ("c2", "The fan motor is independently confirmed stopped.", False),
            ("c3", "Humidity was the established cause of this command.", False),
            ("c4", "An application is recorded as the immediate command issuer.", True),
        ],
    },
    "history": {
        "title": "Contact history and missing records",
        "question": "What does the contact observation and archive coverage establish?",
        "receipts": [_history()],
        "checks": [
            ("c1", "A contact open report was recorded.", True),
            ("c2", "The contact timestamp is an independently verified device clock.", False),
            ("c3", "The archive is complete, proving no other contact events occurred.", False),
            ("c4", "The stored history explicitly reports missing coverage.", True),
        ],
    },
}
_MAX_PER_HOUR = 8
_COOLDOWN_SECONDS = 10
_MAX_EXPLANATION = 1400


def benchmark_status(transport: Any) -> dict[str, Any]:
    cloud_ready = bool(
        getattr(transport, "configured", False)
        and getattr(transport, "base_url", None) == "https://ollama.com"
        and getattr(transport, "api_key", None)
        and getattr(transport, "model_name", None)
    )
    return {
        "available": cloud_ready,
        "reason": ("Uses your configured primary Ollama Cloud account."
                   if cloud_ready else
                   "Configure the primary Ollama Cloud key and official HTTPS endpoint in the add-on."),
        "model": str(getattr(transport, "model_name", "") or "") if cloud_ready else None,
        "cases": [{"id": key, "title": item["title"]} for key, item in _CASES.items()],
        "per_run_cloud_requests": 1,
        "calls_may_consume_account_allowance": True,
        "local_fallback_allowed": False,
        "device_or_hub_access": False,
        "production_publisher_changed": False,
    }


def _parse_response(raw: str, scenario: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, str) or not 1 <= len(raw) <= 12000:
        raise ValueError("invalid model content")
    result = json.loads(raw)
    if not isinstance(result, dict) or set(result) != {"schema", "explanation", "assessments"}:
        raise ValueError("invalid result format")
    if result["schema"] != "homebrain-cloud-benchmark.v1":
        raise ValueError("incorrect schema")
    prose = result["explanation"]
    if (not isinstance(prose, str) or not prose.strip()
            or not 1 <= len(prose) <= _MAX_EXPLANATION or "\x00" in prose):
        raise ValueError("invalid explanation")
    claims = result["assessments"]
    if not isinstance(claims, list) or len(claims) != len(scenario["checks"]):
        raise ValueError("missing assessments")
    expected_ids = {row[0] for row in scenario["checks"]}
    classifications = {}
    for entry in claims:
        if (not isinstance(entry, dict) or set(entry) != {"id", "verdict"}
                or not isinstance(entry["id"], str)
                or entry["id"] not in expected_ids
                or entry["id"] in classifications
                or entry["verdict"] not in ("supported", "not_established")):
            raise ValueError("invalid assessment")
        classifications[entry["id"]] = entry["verdict"]
    if set(classifications) != expected_ids:
        raise ValueError("incomplete assessments")
    checks = []
    for ident, statement, expected in scenario["checks"]:
        actual = classifications[ident] == "supported"
        checks.append({
            "statement": statement,
            "model_verdict": classifications[ident],
            "expected_verdict": "supported" if expected else "not_established",
            "correct": actual == expected,
            "unsupported_claim_wrongly_accepted": not expected and actual,
        })
    correct = sum(bool(row["correct"]) for row in checks)
    high_risk_false_accepts = sum(bool(row["unsupported_claim_wrongly_accepted"]) for row in checks)
    return {
        "explanation": prose,
        "evidence_checks": checks,
        "checks_correct": correct,
        "checks_total": len(checks),
        "unsupported_conclusions_wrongly_accepted": high_risk_false_accepts,
        "unsupported_conclusions_total": sum(not x[2] for x in scenario["checks"]),
        "structured_evidence_accuracy_pct": round(100 * correct / len(checks)),
        "prose_semantics_independently_validated": False,
        "publication_approval": False,
    }


class CloudBenchmark:
    """No retries, no persistent report, and no side effects outside cloud inference."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._attempts: deque[float] = deque()

    async def run_case(self, transport: Any, case_id: str, *, confirmed: bool) -> dict[str, Any]:
        if confirmed is not True:
            raise BenchmarkError(400, "Confirm that this test may consume your Ollama Cloud allowance.")
        if case_id not in _CASES:
            raise BenchmarkError(400, "Unknown synthetic benchmark scenario.")
        meta = benchmark_status(transport)
        if not meta["available"]:
            raise BenchmarkError(503, "The primary Ollama Cloud connection is not configured for the official endpoint.")
        if self._lock.locked():
            raise BenchmarkError(429, "Another cloud benchmark is already running.")
        current = time.monotonic()
        while self._attempts and current - self._attempts[0] >= 3600:
            self._attempts.popleft()
        if len(self._attempts) >= _MAX_PER_HOUR:
            raise BenchmarkError(429, "Cloud benchmark hourly request limit reached.")
        if self._attempts and current - self._attempts[-1] < _COOLDOWN_SECONDS:
            raise BenchmarkError(429, "A recent benchmark used the cloud. Try again shortly.")
        # Charge at most one request even if parsing fails or a timeout follows.
        self._attempts.append(current)
        async with self._lock:
            spec = _CASES[case_id]
            packet = build_stage4_evidence_packet(spec["receipts"])
            user = {
                "question": spec["question"],
                "fictional_verified_source_packet": packet,
                "candidate_conclusions": [
                    {"id": item[0], "statement": item[1]}
                    for item in spec["checks"]
                ],
            }
            messages = [
                {"role": "system", "content": (
                    "You are assessing a wholly fictional smart-home event. "
                    "No tools or home access are available. Explain what the "
                    "supplied evidence actually establishes, naturally and concisely. "
                    "A command does not prove physical execution, a recorded "
                    "issuer does not prove the upstream trigger, and truncated "
                    "history does not establish absence. Classify EACH provided "
                    "candidate conclusion as supported or not_established. "
                    "Do not invent device actions or source records. Reply with "
                    "ONLY a JSON object with exact keys schema, explanation, "
                    "assessments. Schema value: homebrain-cloud-benchmark.v1. "
                    "Explanation: one short paragraph <= 1400 characters. "
                    "Assessments: array of objects with keys id and verdict. "
                    "Do not output any additional prose or markdown."
                )},
                {"role": "user", "content": json.dumps(user, separators=(",", ":"), ensure_ascii=True)},
            ]
            started = time.monotonic()
            try:
                # This is the EXISTING configured ChatTransport, bypassing its
                # local/paid/failover routes. Exactly one cloud POST, zero MCP
                # tools, zero retries and no household/history context.
                answer = await transport._chat_post(
                    messages, [], base_url=transport.base_url,
                    model_name=transport.model_name, api_key=transport.api_key,
                    timeout=httpx.Timeout(min(90.0, max(10.0, transport.timeout_seconds))),
                    keep_alive=None,
                )
                if answer.get("tool_calls"):
                    raise ValueError("tool calls are forbidden in the benchmark")
                scored = _parse_response(answer.get("content", ""), spec)
            except Exception:
                # Never echo a provider error, prompt, credential or raw content.
                raise BenchmarkError(502, "Cloud test failed or returned an invalid assessment. No retry was attempted.") from None
            elapsed_ms = round((time.monotonic() - started) * 1000)
            return {
                "success": True,
                "case_id": case_id,
                "title": spec["title"],
                "model": meta["model"],
                "provider": "Ollama Cloud (existing primary account)",
                "elapsed_ms": elapsed_ms,
                "synthetic_only": True,
                "cloud_calls_attempted": 1,
                "no_mcp_tools_used": True,
                "no_device_operations": True,
                "account_allowance_may_be_consumed": True,
                **scored,
            }


__all__ = ["CloudBenchmark", "BenchmarkError", "benchmark_status"]
