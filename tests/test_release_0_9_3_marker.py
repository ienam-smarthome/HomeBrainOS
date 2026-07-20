from pathlib import Path


def test_schema_safe_search_release_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "hubitat-mcp-ai" / "CHANGELOG-0.9.3.md").exists()
