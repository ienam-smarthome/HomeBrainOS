from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
ADDON_DIR = ROOT / "hubitat-mcp-ai"


def test_entrypoint_rebinds_routes_after_app_controller_installation():
    source = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    app_install = source.index("install_named_app_controller(_core.application)")
    route_rebind = source.index("install_runtime_route_bridge(_core.application)")
    assert app_install < route_rebind
    assert 'RELEASE_VERSION = "0.10.64"' in source


def test_runtime_version_is_baked_into_each_addon_image():
    dockerfile = (ADDON_DIR / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    assert "ARG BUILD_VERSION" in dockerfile
    assert '/app/.homebrain-build-version' in dockerfile
    assert 'io.hass.version="${BUILD_VERSION}"' in dockerfile
    assert 'Path("/app/.homebrain-build-version")' in entrypoint
    assert "RUNTIME_RELEASE_VERSION = _runtime_release_version()" in entrypoint
    assert "application.VERSION = RUNTIME_RELEASE_VERSION" in entrypoint
    assert "application.BAKED_VERSION = RUNTIME_RELEASE_VERSION" in entrypoint


def test_runtime_bridge_recreates_ask_home_and_version_routes_dynamically():
    source = (APP_DIR / "runtime_route_bridge.py").read_text(encoding="utf-8")
    assert "install_cancellable_ask(application)" in source
    assert 'getattr(application, "VERSION", api.version)' in source
    assert '"/manifest.webmanifest"' in source
    assert '"/api/runtime-version"' in source
    assert '"baked_version"' in source
    assert '"application_version"' in source
    assert '"rendered_version"' in source
    assert '"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"' in source
    assert '"Clear-Site-Data": \'"cache"\'' in source
    assert '"X-HomeBrain-Version": version' in source


def test_rendered_version_is_rewritten_after_all_ui_patches():
    import sys

    sys.path.insert(0, str(APP_DIR))
    from runtime_route_bridge import enforce_rendered_version

    stale = (
        '<script>const TITLE="Hubitat MCP AI",VERSION="0.10.56";'
        "document.getElementById('version').textContent='v'+VERSION;</script>"
    )
    rendered = enforce_rendered_version(stale, "0.10.64")
    assert 'VERSION="0.10.64"' in rendered
    assert 'VERSION="0.10.56"' not in rendered


def test_runtime_bridge_removes_pwa_and_retires_old_workers():
    source = (APP_DIR / "runtime_route_bridge.py").read_text(encoding="utf-8")
    assert "remove_pwa_markup" in source
    assert "PWA_CLEANUP_SERVICE_WORKER" in source
    assert "self.registration.unregister()" in source
    assert "hubitat-mcp-ai-shell-" in source
    assert "serviceWorker.getRegistrations()" in source
    assert "registration.unregister()" in source
    assert "serviceWorker.register" not in source
    assert "caches.match('./')" not in source


def test_life360_app_phrase_is_owned_by_deterministic_app_parser():
    import sys

    sys.path.insert(0, str(APP_DIR))
    from named_app_control import parse_app_intent

    intent = parse_app_intent("disable Life360 app")
    assert intent is not None
    assert intent.kind == "write"
    assert intent.action == "disable"
    assert "life360" in intent.variants
