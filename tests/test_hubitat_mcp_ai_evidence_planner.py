from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ai_evidence_domains import install_ai_evidence_domains  # noqa: E402
from ai_evidence_planner import (  # noqa: E402
    AIEvidencePlanner,
    EvidenceRequest,
    is_ai_evidence_query,
)


QUERY = "What are the most important issues at home and is anything wasting power?"


class FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHTTP:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, *, json: dict[str, Any], timeout: float):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.fail:
            raise RuntimeError("direct cloud unavailable")
        assert "tools" not in json
        if len(self.calls) == 1:
            content = {
                "intent": "diagnosis",
                "summary": "Check current issues and measured power",
                "evidence": [
                    {
                        "kind": "home_snapshot",
                        "metrics": [],
                        "devices": [],
                        "hours_back": 24,
                        "limit": 20,
                    },
                    {
                        "kind": "measurements",
                        "metrics": ["power"],
                        "devices": [],
                        "hours_back": 24,
                        "limit": 20,
                    },
                ],
                "confidence": 0.94,
            }
        else:
            content = {
                "status": "need_more",
                "reason": "Device health is required to prioritise faults",
                "additional_evidence": [
                    {
                        "kind": "device_health",
                        "metrics": [],
                        "devices": [],
                        "hours_back": 24,
                        "limit": 20,
                    }
                ],
            }
        return FakeResponse(
            {
                "message": {"role": "assistant", "content": json.dumps(content)},
                "done_reason": "stop",
            }
        )

    @staticmethod
    def last_provider(default: str = ""):
        return "Ollama Cloud Direct"


class FakeOllama:
    cloud_enabled = True
    cloud_model = "gemma4:31b-cloud"
    planner_model = "qwen3.5:4b"
    local_fallback_model = "qwen3.5:4b"
    model = "gemma4:31b-cloud"
    base_url = "http://offline-pc:11434"
    keep_alive = "30m"
    num_ctx = 2048

    def __init__(self, *, fail: bool = False):
        self._http = FakeHTTP(fail=fail)
        self.fail = fail
        self.chat_calls: list[dict[str, Any]] = []

    async def _chat(self, **kwargs):
        self.chat_calls.append(dict(kwargs))
        assert kwargs["tools"] is None
        if self.fail:
            raise RuntimeError("synthesis unavailable")
        return {
            "message": {
                "role": "assistant",
                "content": (
                    "The Fridge Door battery is the clearest confirmed issue at 15%. "
                    "The Fridge is the highest measured live load at 89 W."
                ),
            },
            "_homebrain_model_used": "gemma4:31b-cloud",
            "_homebrain_provider": "Ollama Cloud Direct",
        }


class FakeDeviceIndex:
    def __init__(self):
        self.devices = [
            {
                "id": "1",
                "label": "Fridge Door",
                "room": "Appliances",
                "currentStates": {"battery": 15},
            },
            {
                "id": "2",
                "label": "Fridge",
                "room": "Appliances",
                "currentStates": {"power": 89},
            },
        ]

    async def enriched_devices(self):
        return list(self.devices)

    @staticmethod
    def _groups(item):
        return {"sensor"} if "Door" in item.get("label", "") else {"device", "power"}


class FakeSnapshot:
    async def _load_sources(self, *, force: bool, coverage_errors: list[str]):
        return (
            [{"id": "1"}, {"id": "2"}],
            {"last_refresh_age_seconds": 0},
            {"items": []},
        )

    @staticmethod
    def _build_snapshot(devices, diagnostics, hub_status):
        return {
            "selected_devices": 2,
            "states_read": 2,
            "attention": [
                {
                    "icon": "🪫",
                    "title": "Fridge Door",
                    "value": "15%",
                    "subtitle": "Replace soon",
                }
            ],
            "open_contacts": [],
            "motion_active": [],
            "lights_on": [],
            "devices_on": [{"title": "Fridge", "value": "On"}],
            "heating": [],
        }


class FakeFallback:
    async def _device_health(self):
        return {
            "success": True,
            "offline_devices": [],
            "stale_telemetry": [],
            "quiet_timestamp_devices": [],
            "threshold_hours": 48,
            "message": "No confirmed offline or stale devices.",
        }


class FakeMCP:
    async def call_tool(self, name: str, arguments: dict[str, Any]):
        return SimpleNamespace(is_error=False, text="", data={"healthAlerts": {"active": []}})


class FakeMetricExecutor:
    def __init__(self):
        self.router = SimpleNamespace(
            _device_rows=lambda data: list(data.get("devices") or [])
        )

    async def _fresh_capability_result(self, spec):
        return SimpleNamespace(
            data={
                "devices": [
                    {
                        "id": "2",
                        "label": "Fridge",
                        "room": "Appliances",
                        "currentStates": {"power": 89},
                    }
                ]
            }
        )

    @staticmethod
    def _measurement_rows(rows, spec):
        return [
            {
                "label": "Fridge",
                "room": "Appliances",
                "value": 89.0,
                "aggregate": False,
                "source_attribute": "power",
            }
        ]


class FakeApplication:
    VERSION = "0.7.0"

    def __init__(self, *, fail_ai: bool = False):
        self.ollama = FakeOllama(fail=fail_ai)
        self.fallback = FakeFallback()
        self.mcp = FakeMCP()
        self.OPTIONS = {}

    @staticmethod
    def option_bool(name: str, default: bool = False):
        return default


def make_service(*, fail_ai: bool = False) -> AIEvidencePlanner:
    install_ai_evidence_domains()
    return AIEvidencePlanner(
        FakeApplication(fail_ai=fail_ai),
        FakeDeviceIndex(),
        FakeSnapshot(),
        FakeMetricExecutor(),
        enabled=True,
        prefer_cloud=True,
        max_rounds=2,
        plan_timeout_seconds=12,
        synthesis_timeout_seconds=20,
    )


def test_ai_evidence_candidate_is_broad_but_never_captures_controls_or_fast_reads():
    install_ai_evidence_domains()
    assert is_ai_evidence_query(QUERY)
    assert is_ai_evidence_query("Why is my electricity usage high right now?")
    assert is_ai_evidence_query("What should I improve in the bathroom ventilation setup?")
    assert not is_ai_evidence_query("Turn off Bedroom 1 Light")
    assert not is_ai_evidence_query("Which device is using the most power?")
    assert not is_ai_evidence_query("Are any devices offline or stale?")
    assert not is_ai_evidence_query("Create automation to turn off the lights")


def test_plan_validation_accepts_only_whitelisted_evidence_and_bounded_values():
    service = make_service()
    requests = service._validate_requests(
        [
            {
                "kind": "measurements",
                "metrics": ["power", "made_up"],
                "devices": [],
                "hours_back": 999,
                "limit": 999,
            },
            {
                "kind": "hub_call_device_command",
                "metrics": [],
                "devices": [],
                "hours_back": 24,
                "limit": 20,
            },
            {
                "kind": "recent_events",
                "metrics": [],
                "devices": [],
                "hours_back": 24,
                "limit": 20,
            },
        ]
    )
    assert requests == (
        EvidenceRequest("measurements", ("power",), (), 168, 40),
    )


def test_direct_cloud_selects_evidence_then_requests_one_more_bounded_round():
    service = make_service()
    answer = asyncio.run(service.answer(SimpleNamespace(query=QUERY, history=[])))

    assert answer["success"] is True
    assert answer["route"] == "ollama+evidence-planner"
    assert answer["intent"] == "ai-evidence-planner"
    assert answer["model"] == "gemma4:31b-cloud"
    assert answer["ai_provider"] == "Ollama Cloud Direct"
    assert answer["evidence_sources"] == [
        "home_snapshot",
        "measurements",
        "device_health",
    ]
    assert len(answer["evidence_rounds"]) == 2
    assert answer["review"]["status"] == "need_more"
    assert '"write_tools_available_to_model": false' in (answer["technical"] or "").lower()
    assert "Fridge Door" in answer["message"]
    assert "Fridge" in answer["message"]
    assert len(service.application.ollama._http.calls) == 2
    assert len(service.application.ollama.chat_calls) == 1


def test_ai_failure_returns_deterministic_evidence_instead_of_legacy_agent_error():
    service = make_service(fail_ai=True)
    answer = asyncio.run(
        service.answer(
            SimpleNamespace(query="What are the most important issues at home?", history=[])
        )
    )

    assert answer["success"] is True
    assert answer["route"] == "mcp-evidence-planner"
    assert "model" not in answer
    assert answer["planner_error"]
    assert answer["synthesis_error"] == "synthesis unavailable"
    assert "live snapshot" in answer["message"].lower()
    assert "natural ollama agent could not complete" not in answer["message"].lower()


def test_release_wiring_installs_domains_and_planner_before_tracing():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert entrypoint.index("install_device_health_fast_route(application)") < entrypoint.index(
        "install_ai_evidence_domains()"
    )
    assert entrypoint.index("install_ai_evidence_domains()") < entrypoint.index(
        "install_ai_evidence_planner("
    )
    assert entrypoint.index("install_ai_evidence_planner(") < entrypoint.index(
        "install_request_tracing("
    )
    assert 'version: "0.7.0"' in config
    assert 'RELEASE_VERSION = "0.7.0"' in entrypoint
    assert "ai_evidence_planner_enabled: true" in config
    assert "ai_evidence_planner_max_rounds: 2" in config
