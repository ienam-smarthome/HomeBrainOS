from pathlib import Path


def test_release_092_metadata_is_aligned():
    root = Path(__file__).resolve().parents[1]
    config = (root / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (root / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py").read_text(encoding="utf-8")
    assert 'version: "0.9.2"' in config
    assert 'RELEASE_VERSION = "0.9.2"' in entrypoint
    assert 'PREVIOUS_RELEASE_VERSION = "0.9.1"' in entrypoint
