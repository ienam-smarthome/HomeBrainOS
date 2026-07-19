from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "hubitat-mcp-ai"


def test_addon_docs_explain_supervisor_metadata_reload():
    docs = (ADDON_DIR / "DOCS.md").read_text(encoding="utf-8")

    assert "ha supervisor reload" in docs
    assert "Installed version" in docs
    assert "Latest version" in docs
    assert "Check for updates" in docs
    assert "Refresh Hubitat devices" in docs
