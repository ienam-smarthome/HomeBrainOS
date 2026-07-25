from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from release_version import (  # noqa: E402
    PREVIOUS_RELEASE_VERSION,
    RELEASE_VERSION,
    runtime_release_version,
)


def test_shared_release_constants_match_current_addon_release():
    assert PREVIOUS_RELEASE_VERSION == "0.10.86"
    assert RELEASE_VERSION == "0.10.120"


def test_runtime_release_version_uses_baked_value_when_present(tmp_path):
    baked = tmp_path / ".homebrain-build-version"
    baked.write_text("0.10.120\n", encoding="utf-8")

    assert runtime_release_version(baked) == "0.10.120"


def test_runtime_release_version_falls_back_to_release_constant(tmp_path):
    missing = tmp_path / "missing-version"

    assert runtime_release_version(missing) == RELEASE_VERSION


def test_entrypoints_use_shared_release_source_without_stale_versions():
    core = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from release_version import" in core
    assert "from release_version import" in entrypoint
    assert 'RELEASE_VERSION = "0.10.55"' not in core
    assert 'PREVIOUS_RELEASE_VERSION = "0.10.54"' not in core
    assert "application.VERSION = RUNTIME_RELEASE_VERSION" in core
    assert "application.app.version = RUNTIME_RELEASE_VERSION" in core
