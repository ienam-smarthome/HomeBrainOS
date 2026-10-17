"""Read-only source evidence, app/code ID separation and shortcut regressions."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from groovy_source_investigation import (
    GroovySourceService, requested_groovy_app_id, source_code_id,
)
from rule_machine_analysis import parse_rule_analysis_request
from scoped_app_status_read import scoped_status_app_id
from targeted_lockout_config import current_lockout_config_app_id


REQUEST = (
    "Inspect the actual Groovy implementation used by Livingroom Light 1 "
    "automation (app 4019). Find the declaration of motionOffLockoutMinutes, "
    "its default value, the getter that reads the persisted setting, and how "
    "state.motionLockout stores and calculates expiry timestamps. Read-only."
)


def test_groovy_request_outweighs_three_config_only_shortcuts():
    assert requested_groovy_app_id(REQUEST) == "4019"
    assert parse_rule_analysis_request(REQUEST) is None
    assert scoped_status_app_id(REQUEST) is None
    assert current_lockout_config_app_id(REQUEST) is None


def test_current_configuration_is_not_source_analysis():
    prompt = "Inspect the current Rule Machine settings for app 4019."
    assert requested_groovy_app_id(prompt) is None
    assert parse_rule_analysis_request(prompt) == ("4019", None)


def test_source_id_not_equated_with_instance():
    assert source_code_id({"app": {"id": "4019", "codeId": 1453}}, "4019") == "1453"
    assert source_code_id({"app": {"id": "4019"}}, "4019") is None
    assert source_code_id({"app": {"id": "9999", "codeId": 1453}}, "4019") is None
    assert source_code_id({"app": {"id": "4019", "codeId": 1453}}, "9999") is None


class Evidence:
    def __init__(self):
        self.items = []
    def record(self, tool, arguments, **kwargs):
        self.items.append({"tool": tool, "arguments": arguments, **kwargs})


class FakeMCP:
    def __init__(self, *, code=True, source=True):
        self.calls = []
        self.code, self.source = code, source
        source_text = (
            "input 'motionOffLockoutMinutes', 'number', defaultValue: 30\n"
            "private int getMotionLockoutDurationMinutes() {\n"
            "  Integer configured = safeToInteger(settings.motionOffLockoutMinutes)\n"
            "  return Math.max(1, Math.min(1440, configured ?: 30))\n"
            "}\n"
            "void startMotionLockoutForDevice() {\n"
            "  state.motionLockout = [device: now() + (minutes * 60000L)]\n"
            "}\n"
        )
        self.chunks = [source_text[:100], source_text[100:210], source_text[210:]]
        self.total = len(source_text)
    async def list_tools(self):
        return [
            SimpleNamespace(name="hub_search_tools", input_schema={}),
            SimpleNamespace(name="hub_read_apps_code", input_schema={}),
        ]
    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "hub_search_tools":
            data = {"results": [
                {"tool": "hub_get_app_source", "gateway": "hub_read_apps_code"}
            ]}
        elif args["tool"] == "hub_get_app_config":
            data = {"app": {"id": "4019", **({"codeId": "1453"} if self.code else {})}}
        elif args["tool"] == "hub_get_app_source":
            assert self.source
            idx = len([c for c in self.calls if c[1].get("tool") == "hub_get_app_source"])-1
            assert args["args"]["codeId"] == "1453" if self.code else args["args"]["appId"] == "4019"
            assert idx < 3
            data = {"sourceChunk": self.chunks[idx], "totalChars": self.total,
                    "nextOffset": sum(len(x) for x in self.chunks[:idx+1])
                    if idx < 2 else None, "version": 96}
        return SimpleNamespace(data=data, is_error=False)


def test_source_chunks_are_read_and_excerpts_are_grounded():
    async def run():
        mcp = FakeMCP()
        receipts = Evidence()
        report = await GroovySourceService(mcp, receipts).inspect("4019")
        assert report.retrieved
        assert "defaultValue: 30" in report.message
        assert "getMotionLockoutDurationMinutes" in report.message
        assert "code ID: 1453" in report.message
        assert "complete by declared length" in report.message
        calls = [c for c in mcp.calls if c[1].get("tool") == "hub_get_app_source"]
        assert len(calls) == 3
        assert len(receipts.items) == 5
        assert all(not row["mutates"] for row in receipts.items)
    asyncio.run(run())


def test_no_unverified_source_id_or_unsupported_source_claim():
    async def run():
        mcp = FakeMCP(code=False)
        # Intentionally no fabricated 1453 fallback; app-scoped source read may work.
        report = await GroovySourceService(mcp, Evidence()).inspect("4019")
        assert "code ID: 1453" not in report.message
        assert all(
            "codeId" not in c[1].get("args", {}) for c in mcp.calls
        )
    asyncio.run(run())


def test_unavailable_source_capability_reports_missing_not_conjectured():
    class MissingSource(FakeMCP):
        async def call_tool(self, name, args):
            if name == "hub_search_tools":
                self.calls.append((name, args))
                return SimpleNamespace(data={"results":[]}, is_error=False)
            return await super().call_tool(name,args)
    async def run():
        mcp = MissingSource()
        report = await GroovySourceService(mcp, Evidence()).inspect("4019")
        assert report.retrieved is False
        assert "No source-read operation was verified" in report.message
        assert "state.motionLockout" not in report.message
        assert not any(c[1].get("tool") == "hub_get_app_source" for c in mcp.calls)
    asyncio.run(run())


def test_direct_source_tool_uses_direct_arguments_not_facade():
    class DirectSource(FakeMCP):
        async def list_tools(self):
            return [
                SimpleNamespace(name="hub_get_app_source", input_schema={}),
                SimpleNamespace(name="hub_read_apps_code", input_schema={}),
            ]
        async def call_tool(self, name, args):
            if name == "hub_get_app_source":
                self.calls.append((name, args))
                assert args == {"codeId": "1453"}
                return SimpleNamespace(
                    data={"sourceCode": "private int getMotionLockoutDurationMinutes() {\n"
                                        " return Math.max(1, Math.min(1440, 30))\n}\n"}, is_error=False,
                )
            return await super().call_tool(name, args)
    async def run():
        mcp = DirectSource()
        await GroovySourceService(mcp, Evidence()).inspect("4019")
        assert any(name == "hub_get_app_source" for name, _ in mcp.calls)
    asyncio.run(run())
