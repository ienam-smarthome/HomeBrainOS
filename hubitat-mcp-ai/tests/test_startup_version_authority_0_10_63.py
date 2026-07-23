from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"


def test_mcp_tool_catalogue_installer_cannot_mutate_runtime_version(monkeypatch):
    sys.path.insert(0, str(APP_DIR))
    from mcp_tool_catalogue import install_mcp_tool_catalogue

    routes: list[tuple[str, object]] = []
    startup_handlers: list[object] = []

    class FakeApi:
        version = "0.10.63"

        def get(self, path):
            def decorator(handler):
                routes.append((path, handler))
                return handler

            return decorator

        def on_event(self, event):
            def decorator(handler):
                if event == "startup":
                    startup_handlers.append(handler)
                return handler

            return decorator

    application = SimpleNamespace(VERSION="0.10.63", app=FakeApi())
    monkeypatch.setattr(
        "mcp_tool_catalogue.install_app_management_capability",
        lambda app: None,
    )

    install_mcp_tool_catalogue(application, object())

    assert application.VERSION == "0.10.63"
    assert application.app.version == "0.10.63"
    assert startup_handlers == []
    assert any(path == "/api/mcp-tool-catalogue" for path, _ in routes)


def test_no_stale_release_assignment_remains_in_mcp_tool_catalogue():
    source = (APP_DIR / "mcp_tool_catalogue.py").read_text(encoding="utf-8")
    assert 'application.VERSION = "0.10.56"' not in source
    assert 'application.app.version = "0.10.56"' not in source
    assert "on_event(\"startup\")" not in source
