"""Regression: live direct source chunks are evidence; only contiguous spans prove full code."""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from source_evidence_metadata import source_read_metadata, contiguous_source_coverage
from general_evidence_completion import assess_task_source_coverage
from shared_investigation_completion import apply_shared_investigation_completion
from tool_executor import ToolExecutor
from mcp_client import MCPToolResult


ARGS = {"tool":"hub_get_source","args":{"id":"1453","type":"app","offset":0,"length":20000}}


def _receipt(offset, length, total=186457, identifier="1453"):
    return {
        "tool":"hub_read_apps_code","sub_tool":"hub_get_source",
        "arguments":{"tool":"hub_get_source","args":{"id":identifier,"offset":offset}},
        "effect":"read","mutates":False,"success":True,
        "details":{"sourceRetrieved":True,"sourceCodeId":identifier,
                   "offset":offset,"chunkLength":length,"totalLength":total},
    }


def test_direct_source_call_records_actual_raw_text_not_only_success_flag():
    text = "private int getMotionLockoutDurationMinutes() { return 30 }\n"
    data = {"success":True,"appId":1453,"source":text,
            "totalLength":186457,"offset":0,"chunkLength":len(text),
            "hasMore":True,"nextOffset":len(text)}
    details=source_read_metadata("hub_read_apps_code",ARGS,data)
    assert details == {
        "sourceRetrieved":True, "sourceCodeId":"1453",
        "offset":0,"chunkLength":len(text),"totalLength":186457,
    }
    assert "source" not in str(details).lower().replace("sourceretrieved","").replace("sourcecodeid","")
    row=_receipt(0,len(text))
    assert assess_task_source_coverage(("source_code",), [row]).sources_checked


def test_source_status_or_file_pointer_does_not_count_as_raw_code():
    data={"success":True,"sourceFile":"mcp-source-app-1453.groovy",
          "source":"","totalLength":186457}
    details=source_read_metadata("hub_read_apps_code",ARGS,data)
    assert details["sourceRetrieved"] is False
    row=_receipt(0,100)
    row["details"]=details
    assert not assess_task_source_coverage(("source_code",),[row]).sources_checked


def test_contiguous_read_proves_full_implementation():
    records=[_receipt(0,20000),_receipt(20000,20000),_receipt(40000,146457)]
    result=contiguous_source_coverage(records)
    assert result["fullImplementationVerified"] is True
    assert result["totalLength"] == 186457


def test_gap_and_disjoint_source_code_ids_fail_closed():
    records=[_receipt(0,25384),_receipt(60000,25384)]
    coverage=contiguous_source_coverage(records)
    assert coverage["fullImplementationVerified"] is False
    assert coverage["coverage"] == "gapped"
    records=[_receipt(0,20000,40000),_receipt(20000,20000,40000,identifier="9999")]
    assert contiguous_source_coverage(records)["fullImplementationVerified"] is False


def test_code_investigation_completion_reflects_real_direct_chunks():
    receipts=[_receipt(0,20000,total=40000),_receipt(20000,20000,total=40000)]
    obj=SimpleNamespace(
        route="unified-mcp-agent",request_class="live-read",
        message="Evidence-based explanation.",evidence=receipts,
        metrics={"outcome":"success","counters":{}},
        investigation_coverage=None)
    result=apply_shared_investigation_completion(
        obj,"Inspect the actual Groovy source for installed app 4019.")
    assert result.investigation_coverage["domain"]=="source_code"
    assert result.investigation_coverage["fullImplementationVerified"] is True
    assert result.investigation_coverage["sourceCoverage"]["missingSourceKinds"]==[]
    assert "Source evidence unavailable" not in result.message


def test_executor_metadata_is_sanitized_for_direct_raw_source():
    content="void initialize() {\nstate.motionLockout = [:]\n}\n"
    result=MCPToolResult(name="hub_read_apps_code",arguments=ARGS,raw={},
        text="",data={"success":True,"source":content,"offset":0,
                      "totalLength":len(content)},is_error=False)
    meta=source_read_metadata(result.name,result.arguments,result.data)
    assert meta["sourceRetrieved"] is True
    assert meta["chunkLength"]==len(content)
    assert content not in str(meta)
