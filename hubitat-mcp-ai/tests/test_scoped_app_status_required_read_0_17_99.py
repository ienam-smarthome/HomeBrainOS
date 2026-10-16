"""Required source execution: app status must not terminate after search-only."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from scoped_app_status_read import scoped_status_app_id, read_scoped_app_status


def test_explicit_scoped_app_status_matching():
    assert scoped_status_app_id("What is the current status of Livingroom Light 1 automation (app 4019)?") == 4019
    assert scoped_status_app_id("Show recent logs for app 4019") is None
    assert scoped_status_app_id("Show all active automations") is None


def test_app_status_always_attempts_real_read():
    class FakeMCP:
        def __init__(self):
            self.calls = []
        async def list_tools(self):
            return [SimpleNamespace(name="hub_read_apps_code")]
        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return SimpleNamespace(
                name=name, arguments=arguments, is_error=False,
                data={"success": True, "app": {"id": 4019}, "page": {}}
            )
    async def run():
        fake = FakeMCP()
        out = await read_scoped_app_status(fake, 4019)
        assert fake.calls == [("hub_read_apps_code", {"tool": "hub_get_app_config", "args": {"appId": "4019", "includeSettings": False}})]
        assert out.route == "scoped-app-status"
        assert out.evidence[0]["success"] is True
        assert "configuration was retrieved" in out.message
    asyncio.run(run())


def test_missing_capability_does_not_claim_failed_read():
    class FakeMCP:
        async def list_tools(self):
            return [SimpleNamespace(name="hub_search_tools")]
        async def call_tool(self, *_):
            raise AssertionError("must not attempt unknown tools")
    async def run():
        result = await read_scoped_app_status(FakeMCP(), 4019)
        assert "not available" in result.message
        assert not result.evidence
        assert result.complete is False
    asyncio.run(run())
