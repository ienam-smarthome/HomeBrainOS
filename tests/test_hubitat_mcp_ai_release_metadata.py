from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "hubitat-mcp-ai"
APP_DIR = ADDON_DIR / "rootfs" / "app"


def _required_match(pattern: str, text: str, source: str) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    assert match is not None, f"Missing release metadata in {source}: {pattern}"
    return match


def test_supervisor_version_is_plain_numeric_and_matches_runtime_release():
    config = (ADDON_DIR / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    manifest_version = _required_match(
        r'^version:\s*"(\d+\.\d+\.\d+)"\s*$',
        config,
        "config.yaml",
    ).group(1)
    runtime_version = _required_match(
        r'^RELEASE_VERSION\s*=\s*"([^"]+)"\s*$',
        entrypoint,
        "entrypoint.py",
    ).group(1)

    assert manifest_version == runtime_version
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest_version)
    assert "stage: experimental" in config
    assert "# Previous version:" not in config
    assert "application.VERSION = RELEASE_VERSION" in entrypoint
    assert "application.app.version = RELEASE_VERSION" in entrypoint


def test_changelog_and_cloud_setup_point_to_the_manifest_release():
    config = (ADDON_DIR / "config.yaml").read_text(encoding="utf-8")
    changelog = (ADDON_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    setup_script = (ROOT / "scripts" / "setup-homebrain-ollama-cloud.ps1").read_text(
        encoding="utf-8"
    )

    version = _required_match(
        r'^version:\s*"(\d+\.\d+\.\d+)"\s*$',
        config,
        "config.yaml",
    ).group(1)
    latest_heading = _required_match(
        r"^##\s+([^\s]+)\s*$",
        changelog,
        "CHANGELOG.md",
    ).group(1)

    assert latest_heading == version
    assert f"Hubitat MCP AI {version}." in setup_script


def test_feature_tests_do_not_need_editing_for_each_release_bump():
    current_version = _required_match(
        r'^version:\s*"(\d+\.\d+\.\d+)"\s*$',
        (ADDON_DIR / "config.yaml").read_text(encoding="utf-8"),
        "config.yaml",
    ).group(1)

    offenders: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_hubitat_mcp_ai_*.py")):
        if path.name == Path(__file__).name:
            continue
        if current_version in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == [], (
        "Release numbers belong only in the manifest/runtime/changelog setup path; "
        f"feature tests still hard-code {current_version}: {', '.join(offenders)}"
    )
