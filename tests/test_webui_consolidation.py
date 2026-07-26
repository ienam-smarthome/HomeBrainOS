from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import webui  # noqa: E402


def test_webui_helpers_are_consolidated_in_canonical_module():
    assert callable(webui.render_homebrain_page)
    assert callable(webui.render_page)
    assert callable(webui.patch_clipboard)
    assert callable(webui.patch_http_errors)


def test_retired_webui_wrapper_modules_are_absent():
    assert not (APP_DIR / "webui_homebrain.py").exists()
    assert not (APP_DIR / "webui_clipboard_safe.py").exists()
    assert not (APP_DIR / "webui_http_safe.py").exists()


def test_webui_exports_complete_public_surface():
    assert set(webui.__all__) == {
        "install_clipboard_safe_webui",
        "install_http_safe_webui",
        "patch_clipboard",
        "patch_http_errors",
        "render_homebrain_page",
        "render_page",
    }


def test_repository_tools_use_only_the_canonical_webui_entrypoint():
    for relative_path in (
        "scripts/analyze_imports.py",
        "scripts/analyze_clusters.py",
        "scripts/validate_addon.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "webui_homebrain" not in source
