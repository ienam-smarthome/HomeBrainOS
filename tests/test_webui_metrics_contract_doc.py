from __future__ import annotations

from pathlib import Path


def test_webui_metrics_contract_documents_privacy_boundary() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "WEBUI_METRICS_PRESENTATION.md"
    ).read_text(encoding="utf-8")

    assert "ignores every unknown key" in text
    assert "prompt text" in text
    assert "session identifiers" in text
    assert "raw expandable response JSON" in text
