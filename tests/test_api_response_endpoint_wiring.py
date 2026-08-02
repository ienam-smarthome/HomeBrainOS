from __future__ import annotations

from pathlib import Path


APP = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
    / "app.py"
)


def test_api_ask_uses_stable_response_builder() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "from api_response_builder import build_agent_response" in source
    ask_source = source.split('@app.post("/api/ask")', 1)[1]
    assert "return build_agent_response(" in ask_source
    assert '"metrics":' not in ask_source


def test_api_ask_passes_runtime_metadata_to_builder() -> None:
    source = APP.read_text(encoding="utf-8")
    ask_source = source.split('@app.post("/api/ask")', 1)[1]

    assert "outcome," in ask_source
    assert "model=agent.model_name" in ask_source
    assert "elapsed_ms=round((time.perf_counter() - started) * 1000)" in ask_source
    assert "version=VERSION" in ask_source
