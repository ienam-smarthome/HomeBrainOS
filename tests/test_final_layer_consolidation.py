from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"


def test_final_catalogue_and_context_layers_use_canonical_modules():
    for retired in (
        "device_intelligence_catalogue_safe.py",
        "device_intelligence_duplicate_safe.py",
        "conversation_context_safe.py",
    ):
        assert not (APP_DIR / retired).exists()

    entrypoint = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")
    catalogue = (
        APP_DIR / "device_intelligence_catalogue.py"
    ).read_text(encoding="utf-8")
    context = (APP_DIR / "conversation_context.py").read_text(encoding="utf-8")

    assert (
        "from device_intelligence_catalogue import "
        "CapabilityCatalogueDeviceIndex"
    ) in entrypoint
    assert (
        "from conversation_context import install_conversation_context"
    ) in entrypoint
    assert "async def exact_device(" in catalogue
    assert "metadata_orphans_dropped" in catalogue
    assert "def _device_context_active(" in context
    assert "explicit_device_result" in context
