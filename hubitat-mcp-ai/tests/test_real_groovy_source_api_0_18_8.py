"""End-to-end local source gateway client contract from 2026-10-17 live MCP results."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from groovy_source_investigation import GroovySourceService, source_code_id


class Evidence:
    def __init__(self): self.calls=[]
    def record(self,gateway,args,**kwargs):self.calls.append((gateway,args,kwargs))


class LiveShapeMCP:
    def __init__(self):
        self.calls=[]
        self.code=("input 'motionOffLockoutMinutes','number', defaultValue: 30\n"
                   "private int getMotionLockoutDurationMinutes() {\n"
                   " return settings.motionOffLockoutMinutes ?: 30\n}\n"
                   "void startMotionLockoutForDevice() {\n"
                   "state.motionLockout = [device: now() + 60000L]\n}\n")
        self.code += "  // harmless implementation line\n" * 2800
    async def list_tools(self):
        return [
            SimpleNamespace(name="hub_search_tools",input_schema={}),
            SimpleNamespace(name="hub_read_apps_code",input_schema={
                "type":"object","properties":{"tool":{"type":"string",
                "enum":["hub_get_app_config","hub_list_apps","hub_get_source"]}}}),
        ]
    async def call_tool(self,gateway,args):
        self.calls.append((gateway,args))
        if gateway=="hub_search_tools":
            data={"results":[{"tool":"hub_get_source","gateway":"hub_read_apps_code"}]}
        else:
            assert gateway=="hub_read_apps_code"
            op=args["tool"]
            if op=="hub_get_app_config":
                data={"app":{"id":"4019"}}
            elif op=="hub_list_apps":
                assert args["args"] == {"scope":"instances"}
                data={"apps":[{"id":"9999","appTypeId":"999"},
                              {"id":"4019","appTypeId":"1453"}]}
            else:
                assert op=="hub_get_source"
                leaf=args["args"]
                assert leaf["id"]=="1453" and leaf["type"]=="app"
                assert leaf["length"]==48000
                start=leaf["offset"]
                chunk=self.code[start:start+48000]
                data={"success":True,"appId":1453,"source":chunk,"offset":start,
                      "chunkLength":len(chunk),"totalLength":len(self.code),
                      "hasMore":start+len(chunk)<len(self.code),
                      "nextOffset":start+len(chunk)}
        return SimpleNamespace(data=data,is_error=False)


def test_code_id_can_use_verified_app_type_link():
    assert source_code_id({"app":{"id":"4019","appTypeId":1453}},"4019")=="1453"
    assert source_code_id({"app":{"id":"4020","appTypeId":1453}},"4019") is None


def test_real_groovy_gateway_reads_sequential_offset_pages():
    async def run():
        mcp=LiveShapeMCP(); receipt=Evidence()
        report=await GroovySourceService(mcp,receipt).inspect("4019")
        assert report.retrieved
        assert report.complete
        assert "defaultValue: 30" in report.message
        assert "source" in report.message.lower()
        sources=[call[1]["args"] for call in mcp.calls if call[0]=="hub_read_apps_code"
                 and call[1]["tool"]=="hub_get_source"]
        assert len(sources)>=2
        assert sources[0]["offset"]==0
        assert sources[1]["offset"]==48000
        assert sum(1 for gateway,_,_ in receipt.calls if gateway=="hub_read_apps_code")>=3
    asyncio.run(run())
