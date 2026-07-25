from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"


def test_architecture_and_analysis_tools_are_present():
    assert (ROOT / "docs" / "ARCHITECTURE.md").is_file()
    assert (ROOT / "CONTRIBUTING.md").is_file()
    assert (ROOT / "scripts" / "analyze_imports.py").is_file()
    assert (ROOT / "scripts" / "analyze_clusters.py").is_file()


def test_confirmed_orphan_ollama_agent_was_removed():
    assert not (APP_DIR / "ollama_agent.py").exists()
    assert (APP_DIR / "ollama_agent_unified.py").is_file()


def test_analysis_scripts_parse_without_execution():
    for relative in ("scripts/analyze_imports.py", "scripts/analyze_clusters.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        ast.parse(source, filename=relative)


def test_current_release_metadata_is_aligned():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    release_source = (APP_DIR / "release_version.py").read_text(encoding="utf-8")
    readme = (ROOT / "hubitat-mcp-ai" / "README.md").read_text(encoding="utf-8")
    assert 'version: "0.10.117"' in config
    assert 'PREVIOUS_RELEASE_VERSION = "0.10.86"' in release_source
    assert 'RELEASE_VERSION = "0.10.117"' in release_source
    assert "from release_version import" in entrypoint
    assert "runtime_release_version" in entrypoint
    assert "Current add-on version: **0.10.117**" in readme
