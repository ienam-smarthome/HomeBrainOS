from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TEMPORARY_GITHUB_FILES = {
    "ci-touch.txt",
    "full-validation-trigger",
    "measurement-wording-trigger",
    "placeholder-unused",
}


def test_released_versions_are_not_embedded_in_workflow_filenames():
    offenders = [
        path.name
        for path in sorted(WORKFLOWS.glob("*"))
        if path.is_file() and re.search(r"\d+\.\d+\.\d+", path.name)
    ]

    assert offenders == [], (
        "Release-specific workflows must be replaced by reusable CI or release "
        f"automation: {', '.join(offenders)}"
    )


def test_temporary_ci_trigger_artifacts_are_not_tracked():
    github_dir = ROOT / ".github"
    offenders = sorted(
        name for name in TEMPORARY_GITHUB_FILES if (github_dir / name).exists()
    )

    assert offenders == [], (
        "Temporary CI trigger artifacts must not remain in the repository: "
        + ", ".join(offenders)
    )


def test_rule_writes_are_opt_in_for_new_installations():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "  rule_write_enabled: false" in config
    assert 'option_bool("rule_write_enabled", False)' in entrypoint
