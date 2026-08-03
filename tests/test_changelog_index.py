from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "hubitat-mcp-ai"
CONFIG = ADDON / "config.yaml"
INDEX = ADDON / "CHANGELOG-INDEX.md"
ROOT_README = ROOT / "README.md"


def _configured_version() -> str:
    match = re.search(
        r'^version:\s*["\']?([^"\'\s]+)["\']?\s*$',
        CONFIG.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match is not None, "config.yaml must declare an add-on version"
    return match.group(1)


def test_current_version_has_release_notes_and_index_entry() -> None:
    version = _configured_version()
    release_notes = ADDON / f"CHANGELOG-{version}.md"
    assert release_notes.is_file(), (
        f"Missing release notes for configured add-on version {version}: "
        f"{release_notes.relative_to(ROOT)}"
    )

    index_text = INDEX.read_text(encoding="utf-8")
    expected_link = f"[{version}](CHANGELOG-{version}.md)"
    assert expected_link in index_text, (
        f"CHANGELOG-INDEX.md must identify {version} as the current release"
    )


def test_root_component_version_matches_addon_version() -> None:
    version = _configured_version()
    readme = ROOT_README.read_text(encoding="utf-8")
    component_row = re.search(
        r"\|\s*\[Hubitat MCP AI\]\(hubitat-mcp-ai/README\.md\)\s*"
        r"\|\s*([^|]+?)\s*\|",
        readme,
    )
    assert component_row is not None, "Root README component row is missing"
    assert component_row.group(1).strip() == version


def test_historical_monolithic_changelog_is_not_called_current() -> None:
    index_text = INDEX.read_text(encoding="utf-8").casefold()
    assert "monolithic `changelog.md`" in index_text
    assert "not the current release index" in index_text
