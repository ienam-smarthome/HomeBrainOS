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


def test_pytest_pipelines_cannot_hide_failures_behind_tee():
    workflows = ROOT / ".github" / "workflows"
    offenders: list[str] = []

    for path in sorted(workflows.glob("*.yml")):
        source = path.read_text(encoding="utf-8")
        if "pytest" in source and "| tee" in source and "set -o pipefail" not in source:
            offenders.append(path.name)

    assert offenders == [], (
        "Workflows piping pytest through tee must enable pipefail: "
        + ", ".join(offenders)
    )


def test_ci_installs_the_shared_test_dependency_definition():
    test_requirements = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")
    assert "pytest-asyncio" in test_requirements

    for name in ("hubitat-mcp-ai-tests.yml", "validate.yml"):
        workflow = (
            ROOT / ".github" / "workflows" / name
        ).read_text(encoding="utf-8")
        assert "requirements-test.txt" in workflow
        assert "scripts/run_release_gate.py" in workflow


def test_default_cache_profile_reduces_hub_load_without_caching_writes():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")
    broker = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "mcp_state_broker.py"
    ).read_text(encoding="utf-8")

    for setting in (
        "mcp_device_cache_seconds: 20",
        "mcp_catalog_cache_seconds: 300",
        "mcp_hub_cache_seconds: 60",
        "device_index_ttl_seconds: 30",
        "device_index_capability_ttl_seconds: 300",
        "device_index_metadata_ttl_seconds: 600",
        "dashboard_refresh_seconds: 60",
    ):
        assert setting in config

    assert 'options.get("mcp_catalog_cache_seconds") or 300' in entrypoint
    assert 'options.get("device_index_metadata_ttl_seconds") or 600' in entrypoint
    assert "if policy is None:" in broker
    assert "await self._invalidate_for_write(name)" in broker
