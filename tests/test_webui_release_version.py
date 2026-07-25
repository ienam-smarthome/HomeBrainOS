from __future__ import annotations

from pathlib import Path


APP_DIR = Path("hubitat-mcp-ai/rootfs/app")


def test_webui_uses_authoritative_application_version() -> None:
    source = (APP_DIR / "device_intelligence_webui.py").read_text(
        encoding="utf-8"
    )

    assert "PWA_RELEASE_VERSION" not in source
    assert "getattr(application, 'VERSION', api.version)" in source
    assert "application.VERSION =" not in source


def test_webui_no_longer_exposes_pwa_assets_or_registration() -> None:
    webui = (APP_DIR / "device_intelligence_webui.py").read_text(
        encoding="utf-8"
    )
    bridge = (APP_DIR / "runtime_route_bridge.py").read_text(
        encoding="utf-8"
    )
    combined = webui + "\n" + bridge

    forbidden = (
        "manifest.webmanifest",
        "service-worker.js",
        "serviceWorker.register",
        "beforeinstallprompt",
        "PWA_MANIFEST",
        "PWA_SCRIPT",
        "PWA_RELEASE_VERSION",
        "PWA_REMOVAL_SCRIPT",
        "PWA_CLEANUP_SERVICE_WORKER",
    )

    assert all(token not in combined for token in forbidden)
