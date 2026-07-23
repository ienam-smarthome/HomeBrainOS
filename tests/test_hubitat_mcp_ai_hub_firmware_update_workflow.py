from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from hub_firmware_update_workflow import (  # noqa: E402
    install_hub_firmware_update_workflow,
)
from mcp_client import MCPToolResult  # noqa: E402


def request(query: str, session_id: str = "browser-1"):
    return SimpleNamespace(query=query, session_id=session_id, history=[])


class FakeMCP:
    def __init__(
        self,
        *,
        error: bool = False,
        update_available: bool | None = True,
    ) -> None:
        self.error = error
        self.update_available = update_available
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            platform = {
                "currentVersion": "2.5.1.132",
                "available": self.update_available,
            }
            if self.update_available is True:
                platform.update(
                    {
                        "availableVersion": "2.5.1.133",
                        "channel": "beta",
                    }
                )
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "firmwareVersion": "2.5.1.132",
                    "platformUpdate": platform,
                },
                is_error=False,
            )
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="Admin writes disabled" if self.error else "Update accepted",
            data={},
            is_error=self.error,
        )


class FakeBackupService:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, Any]] = []

    async def _read_best_practice_key(self):
        self.calls.append(("guide", None))
        return "BP-CONFIRM-2401"

    async def _ensure_backup(self, key: str):
        self.calls.append(("backup", key))
        if self.ok:
            return True, {"recent": True, "created": True, "status": "complete"}
        return False, {"error": "Backup creation failed", "created": False}


def make_application(*, error: bool = False, ttl_seconds: float = 120):
    fallback_calls: list[str] = []

    async def fallback(value: Any):
        fallback_calls.append(value.query)
        return {"success": True, "route": "fallback"}

    application = SimpleNamespace(ask=fallback, mcp=FakeMCP(error=error))
    backup_service = FakeBackupService()
    workflow = install_hub_firmware_update_workflow(
        application, backup_service, ttl_seconds=ttl_seconds
    )
    return application, workflow, fallback_calls, backup_service


def test_update_prompts_with_clickable_actions_then_executes_once():
    async def scenario():
        application, _, fallback_calls, backup_service = make_application()
        prompt = await application.ask(request("update software"))
        confirmed = await application.ask(request("yes"))
        repeated = await application.ask(request("yes"))
        return application, backup_service, fallback_calls, prompt, confirmed, repeated

    application, backup_service, fallback_calls, prompt, confirmed, repeated = asyncio.run(scenario())
    assert prompt["confirmation_required"] is True
    assert prompt["intent"] == "hub-firmware-update-confirmation-required"
    assert prompt["display"]["metrics"][:2] == [
        {"label": "Installed", "value": "2.5.1.132", "icon": "🧩"},
        {"label": "Available", "value": "2.5.1.133 (beta)", "icon": "⬆️"},
    ]
    assert prompt["display"]["actions"] == [
        {
            "label": "Yes - update hub",
            "query": "Yes",
            "tone": "danger",
            "icon": "⬆️",
        },
        {
            "label": "No - cancel",
            "query": "No",
            "tone": "secondary",
            "icon": "✖️",
        },
    ]
    assert application.mcp.calls == [
        (
            "hub_get_info",
            {"includeAppUpdate": False, "includeHealthAlerts": True},
        ),
        ("hub_update_firmware", {"confirm": True}),
    ]
    assert backup_service.calls == [
        ("guide", None),
        ("backup", "BP-CONFIRM-2401"),
    ]
    assert confirmed["intent"] == "hub-firmware-update-requested"
    assert repeated["route"] == "fallback"
    assert fallback_calls == ["yes"]


def test_no_cancels_and_yes_from_another_session_cannot_execute():
    async def scenario():
        application, _, fallback_calls, _ = make_application()
        await application.ask(request("upgrade hub firmware"))
        unrelated = await application.ask(request("yes", session_id="browser-2"))
        cancelled = await application.ask(request("no"))
        return application, fallback_calls, unrelated, cancelled

    application, fallback_calls, unrelated, cancelled = asyncio.run(scenario())
    assert unrelated["route"] == "fallback"
    assert cancelled["intent"] == "hub-firmware-update-cancelled"
    assert application.mcp.calls == [
        (
            "hub_get_info",
            {"includeAppUpdate": False, "includeHealthAlerts": True},
        )
    ]
    assert fallback_calls == ["yes"]


def test_expired_confirmation_does_not_execute():
    async def scenario():
        application, workflow, fallback_calls, _ = make_application()
        workflow.ttl_seconds = 0
        await application.ask(request("update hub software"))
        answer = await application.ask(request("yes"))
        return application, fallback_calls, answer

    application, fallback_calls, answer = asyncio.run(scenario())
    assert answer["route"] == "fallback"
    assert application.mcp.calls == [
        (
            "hub_get_info",
            {"includeAppUpdate": False, "includeHealthAlerts": True},
        )
    ]
    assert fallback_calls == ["yes"]


def test_rejected_update_reports_failure_without_retry():
    async def scenario():
        application, _, _, _ = make_application(error=True)
        await application.ask(request("update software"))
        answer = await application.ask(request("confirm"))
        return application, answer

    application, answer = asyncio.run(scenario())
    assert answer["intent"] == "hub-firmware-update-failed"
    assert "Admin writes disabled" in answer["message"]
    assert application.mcp.calls == [
        (
            "hub_get_info",
            {"includeAppUpdate": False, "includeHealthAlerts": True},
        ),
        ("hub_update_firmware", {"confirm": True}),
    ]


def test_backup_failure_blocks_update_and_reports_the_real_reason():
    async def scenario():
        fallback_calls: list[str] = []

        async def fallback(value: Any):
            fallback_calls.append(value.query)
            return {"success": True, "route": "fallback"}

        application = SimpleNamespace(ask=fallback, mcp=FakeMCP())
        backup_service = FakeBackupService(ok=False)
        install_hub_firmware_update_workflow(application, backup_service)
        await application.ask(request("update software"))
        answer = await application.ask(request("yes"))
        return application, backup_service, answer

    application, backup_service, answer = asyncio.run(scenario())
    assert answer["intent"] == "hub-firmware-update-backup-failed"
    assert "was not started" in answer["message"]
    assert "Backup creation failed" in answer["message"]
    assert application.mcp.calls == [
        (
            "hub_get_info",
            {"includeAppUpdate": False, "includeHealthAlerts": True},
        )
    ]
    assert backup_service.calls == [
        ("guide", None),
        ("backup", "BP-CONFIRM-2401"),
    ]


def test_up_to_date_status_lists_installed_version_without_confirmation():
    async def scenario():
        fallback_calls: list[str] = []

        async def fallback(value: Any):
            fallback_calls.append(value.query)
            return {"success": True, "route": "fallback"}

        application = SimpleNamespace(
            ask=fallback,
            mcp=FakeMCP(update_available=False),
        )
        backup_service = FakeBackupService()
        install_hub_firmware_update_workflow(application, backup_service)
        return application, backup_service, await application.ask(request("update software"))

    application, backup_service, answer = asyncio.run(scenario())
    assert answer["intent"] == "hub-firmware-up-to-date"
    assert "confirmation_required" not in answer
    assert "2.5.1.132" in answer["message"]
    assert "actions" not in answer["display"]
    assert backup_service.calls == []
    assert [name for name, _ in application.mcp.calls] == ["hub_get_info"]


def test_release_installs_firmware_workflow_outside_ai_routes():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    assert (
        "from hub_firmware_update_workflow import install_hub_firmware_update_workflow"
        in entrypoint
    )
    assert "hub_firmware_update_workflow = install_hub_firmware_update_workflow(" in entrypoint
    assert entrypoint.index("install_unified_mcp_agent_orchestrator") < entrypoint.index(
        "hub_firmware_update_workflow = install_hub_firmware_update_workflow("
    )
