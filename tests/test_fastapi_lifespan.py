from __future__ import annotations

from pathlib import Path


APP_DIR = Path("hubitat-mcp-ai/rootfs/app")


def test_base_application_uses_fastapi_lifespan() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")

    assert "from contextlib import asynccontextmanager" in source
    assert "@asynccontextmanager" in source
    assert "async def lifespan(" in source
    assert "lifespan=lifespan" in source
    assert "await mcp.close()" in source
    assert "await ollama.close()" in source
    assert '@app.on_event("shutdown")' not in source
    assert '@app.on_event("startup")' not in source


def test_maintained_entrypoint_composes_base_lifespan() -> None:
    source = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")

    assert "_base_lifespan = app.router.lifespan_context" in source
    assert "async with _base_lifespan(current_app):" in source
    assert "device_index.summary_result()" in source
    assert "device_index.metadata_result()" in source
    assert "await request_registry.cancel_all()" in source
    assert "app.router.lifespan_context = maintained_lifespan" in source
    assert '@app.on_event("shutdown")' not in source
    assert '@app.on_event("startup")' not in source


def test_active_requests_cancel_before_base_clients_close() -> None:
    entrypoint = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")
    application = (APP_DIR / "app.py").read_text(encoding="utf-8")

    assert "await request_registry.cancel_all()" in entrypoint
    assert "finally:" in entrypoint
    assert "await mcp.close()" in application
    assert "await ollama.close()" in application
