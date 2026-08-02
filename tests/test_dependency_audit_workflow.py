from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dependency-audit.yml"
REQUIREMENTS = "hubitat-mcp-ai/rootfs/app/requirements.txt"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_dependency_audit_targets_shipped_requirements() -> None:
    text = workflow_text()

    assert REQUIREMENTS in text
    assert "python -m pip_audit" in text
    assert "--requirement hubitat-mcp-ai/rootfs/app/requirements.txt" in text


def test_dependency_audit_tool_is_pinned() -> None:
    text = workflow_text()

    assert "pip-audit==2.10.1" in text
    assert "pip install pip-audit\n" not in text


def test_dependency_audit_is_blocking_but_preserves_report() -> None:
    text = workflow_text()

    assert "continue-on-error: true" in text
    assert "uses: actions/upload-artifact@v4" in text
    assert "if: always()" in text
    assert "if: steps.audit.outcome != 'success'" in text
    assert "exit 1" in text


def test_dependency_audit_runs_on_changes_and_weekly() -> None:
    text = workflow_text()

    assert "pull_request:" in text
    assert "push:" in text
    assert "schedule:" in text
    assert 'cron: "17 5 * * 1"' in text
    assert "workflow_dispatch:" in text
