from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_diagnostics_hybrid import install_hybrid_ollama_diagnostics  # noqa: E402
from ollama_hybrid_profile import resolve_hybrid_profile  # noqa: E402


def test_legacy_saved_qwen_value_is_overridden_when_cloud_preference_is_on():
    profile = resolve_hybrid_profile(
        {
            "ollama_model": "qwen3.5:4b",
            "ollama_planner_model": "qwen3.5:4b",
            "ollama_cloud_enabled": True,
            "ollama_prefer_cloud_response": True,
            "ollama_cloud_model": "gemma4:31b-cloud",
            "ollama_local_fallback_model": "qwen3.5:4b",
        }
    )

    assert profile["configured_response_model"] == "qwen3.5:4b"
    assert profile["effective_response_model"] == "gemma4:31b-cloud"
    assert profile["effective_routine_model"] == "gemma4:31b-cloud"
    assert profile["planner_model"] == "qwen3.5:4b"
    assert profile["local_fallback_model"] == "qwen3.5:4b"
    assert profile["legacy_saved_model_overridden"] is True


def test_explicit_local_only_preference_keeps_qwen_response_model():
    profile = resolve_hybrid_profile(
        {
            "ollama_model": "qwen3.5:4b",
            "ollama_cloud_enabled": True,
            "ollama_prefer_cloud_response": False,
            "ollama_cloud_model": "gemma4:31b-cloud",
            "ollama_local_fallback_model": "qwen3.5:4b",
        }
    )

    assert profile["effective_response_model"] == "qwen3.5:4b"
    assert profile["effective_routine_model"] == "qwen3.5:4b"
    assert profile["legacy_saved_model_overridden"] is False


def test_hybrid_diagnostics_reports_cloud_response_planner_and_fallback():
    profile = resolve_hybrid_profile(
        {
            "ollama_model": "qwen3.5:4b",
            "ollama_planner_model": "qwen3.5:4b",
            "ollama_cloud_enabled": True,
            "ollama_prefer_cloud_response": True,
            "ollama_cloud_model": "gemma4:31b-cloud",
            "ollama_local_fallback_model": "qwen3.5:4b",
        }
    )

    async def original(force: bool = False):
        return {
            "success": True,
            "runtime": {
                "online": True,
                "model": "gemma4:31b-cloud",
                "planner_model": "qwen3.5:4b",
                "cloud_model": "gemma4:31b-cloud",
                "cloud_present": True,
                "local_fallback_model": "qwen3.5:4b",
                "local_fallback_present": True,
                "last_agent": {"state": "idle"},
            },
            "display": {},
        }

    app = SimpleNamespace(
        OPTIONS={"ollama_model": "qwen3.5:4b"},
        ollama_hybrid_profile=profile,
        build_ollama_diagnostics=original,
    )
    install_hybrid_ollama_diagnostics(app)
    answer = asyncio.run(app.build_ollama_diagnostics(force=True))

    assert answer["model"] == "gemma4:31b-cloud"
    assert "Effective response model: gemma4:31b-cloud (cloud)" in answer["message"]
    assert "Saved response setting: qwen3.5:4b" in answer["message"]
    metrics = {item["label"]: item["value"] for item in answer["display"]["metrics"]}
    assert metrics["Cloud"] == "Ready"
    assert metrics["Response"] == "gemma4:31b-cloud"
    assert metrics["Planner"] == "qwen3.5:4b"
    assert metrics["Fallback"] == "qwen3.5:4b"


def test_release_exposes_cloud_preference_and_0417_version():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "version: '0.4.17-alpha'" in config
    assert "ollama_prefer_cloud_response: true" in config
    assert "ollama_prefer_cloud_response: bool" in config
    assert 'RELEASE_VERSION = "0.4.17-alpha"' in entrypoint
    assert "resolve_hybrid_profile" in entrypoint
    assert "install_hybrid_ollama_diagnostics" in entrypoint
