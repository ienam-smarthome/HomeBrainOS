from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_supervisor_refresh_guidance_uses_store_reload_path():
    guide = (ROOT / "docs" / "supervisor-store-refresh.md").read_text(encoding="utf-8")

    assert "ha supervisor reload" in guide
    assert "Check for updates" in guide
    assert "Restarting Hubitat MCP AI does not refresh repository metadata" in guide
    assert "Supervisor" in guide
