"""Per-request Groovy source MCP read cache safety and isolation."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groovy_source_investigation import RequestScopedGroovyMcp


class FakeMcp:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if args.get("tool") == "hub_get_source":
            return SimpleNamespace(is_error=False, data={
                "success": True, "source": "def setReportData() {}",
            })
        if args.get("tool") == "hub_get_app_config":
            return SimpleNamespace(is_error=False, data={
                "success": True, "app": {"appTypeId": 1410},
            })
        return SimpleNamespace(is_error=False, data={"success": True})


@pytest.mark.asyncio
async def test_same_request_source_pages_reused_but_not_cross_request():
    origin = FakeMcp()
    first = RequestScopedGroovyMcp(origin)
    source_args = {
        "tool": "hub_get_source",
        "args": {"id": "1410", "type": "app", "offset": 0, "length": 48000},
    }
    response = await first.call_tool("hub_read_apps_code", source_args)
    assert await first.call_tool("hub_read_apps_code", source_args) is response
    assert first.reused_count == 1
    assert len(origin.calls) == 1

    # Different source spans and installed code IDs never cross-reuse.
    await first.call_tool("hub_read_apps_code", {
        **source_args,
        "args": {**source_args["args"], "offset": 48000},
    })
    await first.call_tool("hub_read_apps_code", {
        **source_args,
        "args": {**source_args["args"], "id": "999"},
    })
    assert len(origin.calls) == 3

    # A fresh user turn gets a new cache; it may see changed source.
    another_turn = RequestScopedGroovyMcp(origin)
    await another_turn.call_tool("hub_read_apps_code", source_args)
    assert another_turn.reused_count == 0
    assert len(origin.calls) == 4


@pytest.mark.asyncio
async def test_source_cache_never_caches_writes_or_failed_responses():
    origin = FakeMcp()
    cache = RequestScopedGroovyMcp(origin)
    write = {"tool": "hub_send_command", "args": {"deviceId": "7182", "command": "off"}}
    await cache.call_tool("hub_manage_devices", write)
    await cache.call_tool("hub_manage_devices", write)
    assert len(origin.calls) == 2
    assert cache.reused_count == 0

    class Failed:
        async def call_tool(self, name, args):
            self.calls += 1
            return SimpleNamespace(is_error=True, data={"success": False})
        def __init__(self):
            self.calls = 0
    failed = Failed()
    scoped = RequestScopedGroovyMcp(failed)
    source = {"tool": "hub_get_source", "args": {"id": "1410", "type": "app", "offset": 0, "length": 100}}
    await scoped.call_tool("hub_read_apps_code", source)
    await scoped.call_tool("hub_read_apps_code", source)
    assert failed.calls == 2
    assert scoped.reused_count == 0
