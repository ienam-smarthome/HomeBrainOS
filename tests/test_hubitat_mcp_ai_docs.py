from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "hubitat-mcp-ai"


def test_addon_docs_explain_supervisor_metadata_reload():
    docs = (ADDON_DIR / "DOCS.md").read_text(encoding="utf-8")

    assert "ha supervisor reload" in docs
    assert "Installed version" in docs
    assert "Latest version" in docs
    assert "Check for updates" in docs
    assert "Refresh Hubitat devices" in docs


def test_addon_control_api_is_ingress_only_by_default():
    config = yaml.safe_load(
        (ADDON_DIR / "config.yaml").read_text(encoding="utf-8")
    )

    assert config["ingress"] is True
    assert config["ports"]["8788/tcp"] is None

    readme = (ADDON_DIR / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    assert "authenticated Home Assistant ingress" in normalized_readme
    assert "direct host-port mapping is disabled by default" in normalized_readme
