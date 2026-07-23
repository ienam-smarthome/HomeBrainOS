import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from hub_firmware_backup_retry import install_firmware_backup_settle_retry


class Result:
    def __init__(self, *, is_error=False, text="", data=None):
        self.is_error = is_error
        self.text = text
        self.data = data


class MCP:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


class Workflow:
    def __init__(self, first, retry_result):
        self.first = first
        self.application = SimpleNamespace(mcp=MCP(retry_result))

    async def _update(self):
        return self.first


def backup_required_answer():
    return {
        "success": False,
        "message": "Invalid params: BACKUP REQUIRED: No hub backup found within the last 24 hours.",
        "technical": json.dumps(
            {
                "backup": {
                    "recent": True,
                    "verified_by": "hub_list_backups_after_create",
                    "post_create_checks": [{"checked": True, "recent": True}],
                }
            }
        ),
    }


def test_retries_once_after_verified_backup_guard_lag(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    workflow = Workflow(backup_required_answer(), Result(is_error=False, data={"success": True}))
    install_firmware_backup_settle_retry(workflow, settle_seconds=4)

    answer = asyncio.run(workflow._update())

    assert answer["success"] is True
    assert answer["intent"] == "hub-firmware-update-requested-after-backup-settle"
    assert workflow.application.mcp.calls == [("hub_update_firmware", {"confirm": True})]


def test_does_not_retry_without_verified_recent_backup(monkeypatch):
    async def no_sleep(_seconds):
        raise AssertionError("sleep must not be called")

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    first = {
        "success": False,
        "message": "BACKUP REQUIRED",
        "technical": json.dumps({"backup": {"recent": False}}),
    }
    workflow = Workflow(first, Result(is_error=False))
    install_firmware_backup_settle_retry(workflow)

    answer = asyncio.run(workflow._update())

    assert answer is first
    assert workflow.application.mcp.calls == []
