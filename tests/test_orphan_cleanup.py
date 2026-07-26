from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"


def test_confirmed_orphan_modules_are_absent():
    for module in (
        "humidity_home_insight.py",
        "named_rule_match_guard.py",
        "sitecustomize.py",
        "thermal_home_insight.py",
    ):
        assert not (APP_DIR / module).exists()


def test_structured_mcp_results_are_owned_by_the_client():
    source = (APP_DIR / "mcp_client.py").read_text(encoding="utf-8")

    assert 'structured = result.get("structuredContent")' in source
    assert "data = structured if structured is not None" in source
