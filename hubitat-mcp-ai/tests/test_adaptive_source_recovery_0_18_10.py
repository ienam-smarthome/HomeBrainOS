"""Regress actual live source-reader failure and safe generic read-gateway recovery."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from evidence_gateway_contract import normalize_gateway_read, missing_required_read_fields
from groovy_source_investigation import GroovySourceService, _excerpts


class Audit:
    def __init__(self):
        self.rows = []
    def record(self, gateway, args, **meta):
        self.rows.append((gateway, args, meta))


class AlmostFullPageMCP:
    """Hub reads 48,000 then 47,999 chars but advertises +48k nextOffset.

    A smaller 16k retry of the same offset succeeds and yields complete
    contiguous source. This matches the 0.18.9 truncation/mismatch symptom.
    """
    def __init__(self, *, shrink_recovers=True):
        body = (
            "void initialize() {\n state.motionLockout = [:]\n}\n"
            + ("// Other unrelated Groovy code\n" * 6150)
            + "void updated() {\n initialize()\n}\n"
        )
        self.code = (body[:186457 - 44].ljust(186457 - 44, " ")
                     + "void updated() {\\n  initialize()\\n}\\n".replace("\\n", "\n").ljust(44, " "))
        assert len(self.code) == 186457
        self.calls = []
        self.shrink_recovers = shrink_recovers

    async def list_tools(self):
        return [
            SimpleNamespace(name="hub_search_tools", input_schema={}),
            SimpleNamespace(name="hub_read_apps_code",
                input_schema={"properties":{"tool":{"enum":[
                    "hub_get_app_config", "hub_list_apps", "hub_get_source",
                ]}}}),
        ]

    async def call_tool(self, name, payload):
        self.calls.append((name, payload))
        if name == "hub_search_tools":
            data = {"results":[{"gateway":"hub_read_apps_code","tool":"hub_get_source"}]}
        else:
            assert name == "hub_read_apps_code"
            op = payload["tool"]
            if op == "hub_get_app_config":
                data = {"app":{"id":"4019"}}
            elif op == "hub_list_apps":
                data = {"apps":[{"id":"4019","appTypeId":"1453"}]}
            elif op == "hub_get_source":
                args = payload["args"]
                assert args["id"] == "1453" and args["type"] == "app"
                start, size = args["offset"], args["length"]
                assert size in (48000,16000,8000)
                requested_end = min(len(self.code), start+size)
                drift = ((start == 48000 and size == 48000)
                         or (not self.shrink_recovers and start >= 48000))
                text_end = max(start, requested_end-1) if drift else requested_end
                chunk = self.code[start:text_end]
                data = {
                    "success":True, "appId":1453, "version":96,
                    "source":chunk, "offset":start, "totalLength":len(self.code),
                    "nextOffset":requested_end,
                    "hasMore":requested_end < len(self.code),
                }
            else:
                raise AssertionError(op)
        return SimpleNamespace(data=data, is_error=False)


def test_one_character_source_drift_recovers_without_gap_and_reaches_eof():
    async def run():
        mcp = AlmostFullPageMCP()
        audit = Audit()
        result = await GroovySourceService(mcp,audit).inspect(
            "4019",symbols=["initialize()", "updated()"],
        )
        assert result.retrieved
        assert result.complete
        assert "complete by declared length" in result.message
        assert "Smaller-page recovery attempts: 1" in result.message
        assert "updated()" in result.message
        requests = [call["args"] for name,call in mcp.calls
                    if name=="hub_read_apps_code" and call["tool"]=="hub_get_source"]
        assert requests[0]["offset"]==0
        assert requests[1]["offset"]==48000 and requests[1]["length"]==48000
        assert requests[2]["offset"]==48000 and requests[2]["length"]==16000
        assert requests[-1]["offset"]+len(mcp.code[requests[-1]["offset"]:]) >= len(mcp.code)
        assert any(not meta["success"] for _,args,meta in audit.rows
                   if isinstance(args,dict) and args.get("tool")=="hub_get_source")
    asyncio.run(run())


def test_permanent_server_offset_mismatch_fails_closed():
    async def run():
        mcp = AlmostFullPageMCP(shrink_recovers=False)
        result = await GroovySourceService(mcp,Audit()).inspect("4019")
        assert result.retrieved and not result.complete
        assert "full source coverage unverified" in result.message
        assert "Retrieval limitation:" in result.message
    asyncio.run(run())


def test_model_nested_source_read_envelope_is_flattened_only_when_read_only():
    malformed = {
        "tool":"hub_get_source",
        "args":{"tool":"hub_get_source",
                "args":{"id":"1453","type":"app","offset":48000,"length":16000}},
    }
    normal = normalize_gateway_read("hub_read_apps_code",malformed)
    assert normal["args"] == {"id":"1453","type":"app",
                              "offset":48000,"length":16000}
    assert not missing_required_read_fields("hub_read_apps_code",normal)
    assert missing_required_read_fields("hub_read_apps_code",{
        "tool":"hub_get_source","args":{"id":"1453"},
    }) == ("type",)
    assert normalize_gateway_read("hub_manage_rule_machine",malformed) == malformed


def test_method_definitions_prioritized_and_late_symbols_not_starved():
    src = ("// updated() was mentioned in a comment\n"
           + "void updated() {\n updatedHandler()\n}\n"
           + ("// state.motionLockout use\n" * 180)
           + "private Long calculateExpiry() {\n return now() + 120000L\n}\n")
    excerpts, symbols = _excerpts(src,[
        "state.motionLockout", "updated()", "calculateExpiry()"
    ])
    assert set(symbols)=={
        "state.motionLockout","updated()","calculateExpiry()"
    }
    assert any("void updated() {" in snippet for snippet in excerpts)
    assert any("private Long calculateExpiry()" in snippet for snippet in excerpts)



def test_full_source_request_is_unresolved_without_full_coverage():
    from shared_investigation_completion import apply_shared_investigation_completion
    from types import SimpleNamespace
    prompt = ("Inspect the complete Groovy source of installed app 4019 "
              "and examine updated() and initialize().")
    evidence = [{
        "tool":"homebrain_read_groovy_source", "success":True,
        "effect":"read", "mutates":False,
        "details":{"sourceRetrieved":True,
                   "fullImplementationVerified":False,
                   "verifiedCharacters":95999,
                   "declaredTotalCharacters":186457,
                   "verifiedPages":2},
    }]
    outcome = SimpleNamespace(route="unified-mcp-agent",
        request_class="live-read",message="Incomplete analysis",
        evidence=evidence,metrics={"outcome":"success","counters":{}},
        investigation_coverage=None)
    result = apply_shared_investigation_completion(outcome, prompt)
    assert result.metrics["outcome"] == "unresolved"
    assert result.investigation_coverage["objectiveSatisfied"] is False
    assert result.investigation_coverage["chunkCoverage"]["chunksObserved"] == 2
    assert result.investigation_coverage["chunkCoverage"]["verifiedCharacters"] == 95999


def test_complete_workbench_source_is_reported_as_full_coverage():
    from shared_investigation_completion import apply_shared_investigation_completion
    from types import SimpleNamespace
    evidence = [{
        "tool":"homebrain_read_groovy_source", "success":True,
        "effect":"read", "mutates":False,
        "details":{"sourceRetrieved":True,"fullImplementationVerified":True,
                   "verifiedCharacters":186457,
                   "declaredTotalCharacters":186457,"verifiedPages":11},
    }]
    outcome = SimpleNamespace(route="unified-mcp-agent",
        request_class="live-read",message="Source read.",
        evidence=evidence,metrics={"outcome":"success","counters":{}},
        investigation_coverage=None)
    result = apply_shared_investigation_completion(
        outcome,"Inspect the full Groovy source of installed app 4019.")
    assert result.investigation_coverage["fullImplementationVerified"] is True
    assert result.investigation_coverage["chunkCoverage"]["coverage"] == "complete"
    assert result.investigation_coverage["chunkCoverage"]["chunksObserved"] == 11
    assert result.metrics["outcome"] == "success"
