"""General LLM-selectable source workbench; complete, non-overlapping retrieval."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from groovy_source_investigation import GroovySourceService, _excerpts, _validated_symbols
from source_evidence_metadata import contiguous_source_coverage


class Evidence:
    def __init__(self):
        self.rows = []
    def record(self, gateway, arguments, **meta):
        self.rows.append((gateway, arguments, meta))


class SourceMCP:
    def __init__(self):
        self.calls = []
        start = "private int getThreshold() {\n  return 21\n}\n"
        ending = (
            "\nvoid updated() {\n  state.lastRefresh = now()\n}\n"
            "Long lastRefresh = state.lastRefresh\n"
        )
        self.code = start + ("// generic Groovy implementation padding\n" * 6000)
        self.code = (self.code[:186457 - len(ending)] + ending)
        assert len(self.code) == 186457
    async def list_tools(self):
        return [
            SimpleNamespace(name="hub_read_apps_code",
                input_schema={"properties":{"tool":{"enum":[
                    "hub_get_app_config", "hub_list_apps", "hub_get_source"
                ]}}}),
            SimpleNamespace(name="hub_search_tools", input_schema={}),
        ]
    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if gateway == "hub_search_tools":
            data={"results":[{"gateway":"hub_read_apps_code","tool":"hub_get_source"}]}
        else:
            assert gateway == "hub_read_apps_code"
            op=arguments["tool"]
            if op == "hub_get_app_config":
                data={"app":{"id":"5551"}}
            elif op == "hub_list_apps":
                data={"apps":[{"id":"5551","appTypeId":"1099"}]}
            elif op == "hub_get_source":
                a=arguments["args"]
                assert a["id"]=="1099" and a["type"]=="app"
                assert a["length"]==48000
                offset=a["offset"]
                assert offset in (0,48000,96000,144000)
                chunk=self.code[offset:offset + a["length"]]
                data={"success":True,"appId":1099,"source":chunk,
                      "offset":offset,"totalLength":len(self.code),
                      "chunkLength":len(chunk),"nextOffset":offset+len(chunk),
                      "hasMore":offset+len(chunk)<len(self.code),"version":96}
            else:
                raise AssertionError("Unexpected leaf: "+op)
        return SimpleNamespace(data=data,is_error=False)


def test_complete_arbitrary_186457_char_implementation_in_four_source_reads():
    async def run():
        mcp=SourceMCP()
        evidence=Evidence()
        report=await GroovySourceService(mcp,evidence).inspect(
            "5551",symbols=["getThreshold", "updated()", "lastRefresh"]
        )
        assert report.complete is True
        assert report.retrieved is True
        assert "186457" in report.message
        assert "updated()" in report.message
        assert "lastRefresh" in report.message
        assert "complete by declared length" in report.message
        calls=[args["args"] for _,args in mcp.calls
               if args.get("tool")=="hub_get_source"]
        assert [x["offset"] for x in calls] == [0,48000,96000,144000]
        assert all(a["length"]==48000 for a in calls)
    asyncio.run(run())


def test_no_matching_symbols_still_counts_as_retrieved_raw_source():
    async def run():
        report=await GroovySourceService(SourceMCP(),Evidence()).inspect(
            "5551",symbols=["unknownMethod"]
        )
        assert report.complete and report.retrieved
        assert "unknownMethod" in report.message
    asyncio.run(run())


def test_symbol_validation_is_bounded_and_safe():
    values=["updated()", "state.lastRefresh", "getThreshold", "../../../secrets", "a" * 120]
    assert _validated_symbols(values)==("updated()","state.lastRefresh","getThreshold")
    snippets, found=_excerpts(
        "void updated() {\n state.lastRefresh=now()\n}\n",
        ["updated()", "state.lastRefresh"],
    )
    assert len(snippets)==1
    assert "updated()" in found and "state.lastRefresh" in found


def test_overlapping_source_reads_are_contiguous_but_not_complete():
    receipts=[]
    for offset,length in [(0,63999),(25000,63999),(50000,63999),
                          (75000,64000),(100000,64000)]:
        receipts.append({"success":True,"effect":"read","mutates":False,
            "details":{"sourceRetrieved":True,"sourceCodeId":"1453",
                       "offset":offset,"chunkLength":length,
                       "totalLength":186457}})
    result=contiguous_source_coverage(receipts)
    assert result["coverage"]=="partial"
    assert result["fullImplementationVerified"] is False
