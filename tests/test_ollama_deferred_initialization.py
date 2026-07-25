from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"


def _source(name: str) -> str:
    return (APP_DIR / name).read_text(encoding="utf-8")


def test_entrypoint_core_requests_deferred_legacy_agent_initialization():
    source = _source("entrypoint_core.py")

    assert 'os.environ["HOMEBRAIN_DEFER_OLLAMA_INIT"] = "1"' in source
    assert source.index("HOMEBRAIN_DEFER_OLLAMA_INIT") < source.index(
        "import app as application"
    )


def test_app_preserves_standalone_agent_but_supports_deferred_startup():
    source = _source("app.py")

    assert "class DeferredOllamaAgent" in source
    assert 'os.environ.get("HOMEBRAIN_DEFER_OLLAMA_INIT") == "1"' in source
    assert "ollama = DeferredOllamaAgent()" in source
    assert "ollama = ClaudeStyleOllamaAgent(" in source

    ast.parse(source, filename="app.py")


def test_final_runtime_agent_remains_unified():
    import sys

    sys.path.insert(0, str(APP_DIR))

    import entrypoint_core
    from ollama_agent_unified import UnifiedAdaptiveMCPAgent

    assert type(entrypoint_core.application.ollama) is UnifiedAdaptiveMCPAgent
    assert not getattr(
        entrypoint_core.application.ollama,
        "deferred_initialization",
        False,
    )
