from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from home_snapshot import (  # noqa: E402
    HomeSnapshotService,
    HybridTruthfulHomeSnapshotService,
    TruthfulHomeSnapshotService,
    install_home_snapshot,
    install_hybrid_home_snapshot,
    install_truthful_home_snapshot,
)


def test_snapshot_layers_are_consolidated_in_the_canonical_module():
    assert issubclass(TruthfulHomeSnapshotService, HomeSnapshotService)
    assert issubclass(
        HybridTruthfulHomeSnapshotService,
        TruthfulHomeSnapshotService,
    )
    assert not (APP_DIR / "home_snapshot_truthful.py").exists()
    assert not (APP_DIR / "home_snapshot_hybrid.py").exists()

    entrypoint = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")
    assert "from home_snapshot import install_hybrid_home_snapshot" in entrypoint
    assert "from home_snapshot_hybrid import" not in entrypoint


@pytest.mark.parametrize(
    ("installer", "expected_type", "expected_timeout"),
    [
        (install_home_snapshot, HomeSnapshotService, 12.0),
        (install_truthful_home_snapshot, TruthfulHomeSnapshotService, 12.0),
        (install_hybrid_home_snapshot, HybridTruthfulHomeSnapshotService, 20.0),
    ],
)
def test_public_installers_preserve_types_and_passthrough(
    installer,
    expected_type,
    expected_timeout,
):
    calls: list[str] = []

    async def original(request):
        calls.append(request.query)
        return {"route": "original"}

    application = SimpleNamespace(
        VERSION="0.10.161",
        ask=original,
    )
    service = installer(application, object(), ai_enabled=False)

    answer = asyncio.run(
        application.ask(SimpleNamespace(query="What is the weather?"))
    )

    assert type(service) is expected_type
    assert service.ai_timeout_seconds == expected_timeout
    assert application.home_snapshot is service
    assert answer == {"route": "original"}
    assert calls == ["What is the weather?"]


def test_hybrid_snapshot_preserves_cloud_and_local_provider_disclosure(
    monkeypatch,
):
    async def truthful_answer(self, _query):
        return {
            "route": "ollama+snapshot",
            "model": self.application.returned_model,
            "display": {"note": "Verified snapshot."},
        }

    monkeypatch.setattr(
        TruthfulHomeSnapshotService,
        "answer",
        truthful_answer,
    )
    application = SimpleNamespace(
        OPTIONS={"ollama_cloud_model": "gemma3:27b-cloud"},
        returned_model="gemma3:27b-cloud",
    )
    service = HybridTruthfulHomeSnapshotService(application, object())

    cloud = asyncio.run(service.answer("Home status"))
    application.returned_model = "qwen3.5:9b"
    local = asyncio.run(service.answer("Home status"))

    assert cloud["ai_provider"] == "Ollama Cloud"
    assert local["ai_provider"] == "Local Ollama fallback"
    assert "local Qwen wrote the summary" in local["display"]["note"]
