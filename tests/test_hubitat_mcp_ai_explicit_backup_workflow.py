from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from backup_intent import is_explicit_backup_request  # noqa: E402
from hub_backup_workflow import install_explicit_hub_backup_workflow  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeBackupService:
    def __init__(self, result: tuple[bool, dict]):
        self.result = result
        self.calls = []

    async def _read_best_practice_key(self):
        self.calls.append("guide")
        return "BP-TEST-1234"

    async def _ensure_backup(self, key, *, force=False):
        self.calls.append((key, force))
        return self.result


def request(query: str):
    return SimpleNamespace(query=query)


def application(service: FakeBackupService):
    async def fallback(_request):
        return {"route": "fallback", "message": "fallback"}

    app = SimpleNamespace(ask=fallback, VERSION="0.10.2")
    install_explicit_hub_backup_workflow(app, service)
    return app


def test_explicit_backup_wording_is_intent_based_and_questions_are_not_writes():
    for query in (
        "perform a backup",
        "please create a full hub backup now",
        "can you back up my hub",
        "would you backup the hub",
        "trigger the database backup",
    ):
        assert is_explicit_backup_request(query)
    for query in (
        "list backups",
        "why did the backup fail?",
        "restore backup",
        "backup status",
        "is backup enabled?",
    ):
        assert not is_explicit_backup_request(query)


def test_explicit_backup_bypasses_ai_and_forces_guarded_create():
    service = FakeBackupService(
        (True, {"created": True, "result": {"fileName": "Hubitat-2026-07-21.lzf"}})
    )
    app = application(service)

    answer = asyncio.run(app.ask(request("perform a backup")))

    assert answer["success"] is True
    assert answer["route"] == "mcp-backup"
    assert answer["model"] is None
    assert "Hubitat-2026-07-21.lzf" in answer["message"]
    assert service.calls == ["guide", ("BP-TEST-1234", True)]
    assert classify_query("perform a backup").route == "mcp-backup"


def test_pending_backup_reports_no_duplicate_and_does_not_claim_failure():
    service = FakeBackupService(
        (False, {"started": True, "pending": True, "error": "transport timeout"})
    )
    app = application(service)

    answer = asyncio.run(app.ask(request("run a hub backup")))

    assert answer["success"] is False
    assert answer["intent"] == "hub-backup-pending"
    assert "did not start a second backup" in answer["message"]
    technical = json.loads(answer["technical"])
    assert technical["duplicate_write_prevented"] is True


def test_backup_questions_continue_to_the_normal_answer_stack():
    service = FakeBackupService((True, {}))
    app = application(service)

    answer = asyncio.run(app.ask(request("when was the last backup?")))

    assert answer["route"] == "fallback"
    assert service.calls == []


def test_entrypoint_installs_backup_route_outside_unified_agent_before_tracing():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    unified = entrypoint.index("install_unified_mcp_agent_orchestrator(application)")
    backup = entrypoint.index("install_explicit_hub_backup_workflow(application, automation_rule_workflow)")
    tracing = entrypoint.index("install_request_tracing(")
    assert unified < backup < tracing
