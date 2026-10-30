"""Reception-only co-occurrence: useful patterns, never causal clock proof."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))
from group_journal_recovery import recover_group_journal,recover_input_journal
from unified_investigation_bridge import collect_unified_evidence,unified_investigation_instruction
from unified_incident_digest import source_incident_digest
from investigation_evidence_cycle import cross_source_discovery_checkpoint

Q=("Why did Zone Alpha Light and Zone Beta Light repeatedly turn ON and OFF "
   "between 14:50 and 15:30 GMT on 30 October 2026?")
ON=["14:50:37.871","14:51:54.329","14:57:53.526","15:07:14.132","15:28:13.424"]
OFF=["14:51:36.184","14:52:26.500","14:58:30.641","15:11:09.744","15:29:15.678"]
ACTIVE=["14:50:39.031","14:51:55.033","14:57:54.775","15:07:15.326","15:28:14.720"]
INACTIVE=["14:51:27.399","14:52:17.777","14:58:21.845","15:11:00.795","15:29:06.845"]

def d(t):
    return "2026-10-30T"+t+"+00:00"

def native(ident):
    return {"success":True,"effect":"read","mutates":False,
        "supports_live_claim":True,"tool":"hub_read_devices",
        "sub_tool":"hub_list_device_events",
        "arguments":{"tool":"hub_list_device_events","args":{"deviceId":str(ident)}},
        "details":{"observedEvents":[]}}

def lookup(ident,name):
    return {"success":True,"effect":"read","mutates":False,
        "tool":"hub_read_devices","evidence_kind":"targeted_device_lookup",
        "details":{"reportedDeviceState":{"deviceId":str(ident),"label":name}}}

def evt(i,attribute,value,time,basis):
    return {"stream":"events","device_id":str(i),"attribute":attribute,
            "value":value,"observed_at":d(time),"timestamp_basis":basis}

class Journal:
    enabled=True
    _started=True
    def query(self,**args):
        i=args["device_id"]
        if i in ("101","102"):
            rows=[evt(i,"switch","on",t,"source") for t in ON]
            rows +=[evt(i,"switch","off",t,"source") for t in OFF]
        else:
            rows=[evt(i,"motion","active",t,"collector-received") for t in ACTIVE]
            rows +=[evt(i,"motion","inactive",t,"collector-received") for t in INACTIVE]
            # Source time unverified even though receipt times are close.
            if i=="201":
                rows=[evt(i,"motion","inactive","14:50:00.000",
                          "collector-received") for _ in range(25)]+rows
        return {"events":rows,"gaps":[{"reason":"disconnect"}],
                "truncated":i=="201"}

class Recorder:
    def __init__(self):
        self.rows=[lookup(101,"Zone Alpha Light"),
                   lookup(102,"Zone Beta Light"),
                   native(101),native(102),native(201)]
    def record(self,tool,arguments,**kw):
        # Actual EvidenceRecorder.redact bounds all nested arrays at 20.
        info=kw.get("details")
        if info and isinstance(info.get("observations"),list):
            info=dict(info)
            info["observations"]=info["observations"][:20]
            kw["details"]=info
        self.rows.append({"tool":tool,"arguments":arguments,**kw})

def run():
    r=Recorder()
    j=Journal()
    async def go():
        await recover_group_journal(journal=j,recorder=r,question=Q,receipts=r.rows)
        return await recover_input_journal(journal=j,recorder=r,question=Q,receipts=r.rows)
    inp=asyncio.run(go())
    return r,inp

def test_full_page_pattern_survives_receipt_array_compaction():
    r,inp=run()
    assert inp["attempted"]==1
    assert inp["source_observations"]==0
    assert inp["collector_observations"]==35
    details=[row["details"] for row in r.rows
             if row.get("evidence_kind")=="group_archived_input_history"][0]
    assert details["returnedObservationCount"]==35
    assert len(details["observations"])==20
    assert details["truncated"] is True
    patt=details["receptionPatternSummary"]
    assert patt["onNearActiveReceptions"]==5
    assert patt["offAfterInactiveReceptions"]==5
    assert patt["crossClockOrderVerified"] is False
    facts=collect_unified_evidence(r.rows,Q)
    assert facts["archived_input_collector_observations"]==20
    assert facts["archived_input_source_observations"]==0
    assert len(facts["independent_input_observations"])==0
    p=facts["archived_input_reception_patterns"][0]
    assert p["on_near_active_receptions"]==5
    assert p["off_after_inactive_receptions"]==5
    assert p["target_source_on_count"]==5
    assert p["target_source_off_count"]==5
    assert p["full_returned_page_analyzed"] is True
    assert p["cross_clock_order_verified"] is False
    assert facts["archived_input_sample_coverage"]==[{
        "device_id":"201","retrieved_observations":35,
        "retained_receipt_observations":20,"query_truncated":True}]
    txt=source_incident_digest(facts)
    assert "5/5 source-time light ON" in txt
    assert "5/5 source-time light OFF" in txt
    assert "Reception timestamps are NOT the original sensor event times" in txt
    assert "partial archived input sample" in txt
    assert "controller issued a command" in txt
    checkpoint=cross_source_discovery_checkpoint(r.rows,Q)
    assert checkpoint and '"receptionOnlyInputCooccurrence"' in checkpoint
    assert '"cross_clock_order_verified": false' in unified_investigation_instruction(r.rows,Q)

def test_no_input_receipt_does_not_invent_reception_pattern():
    r=Recorder()
    facts=collect_unified_evidence(r.rows,Q)
    assert facts
    assert facts["archived_input_reception_patterns"]==[]
    assert "Reception-only pattern" not in (source_incident_digest(facts) or "")

def test_empty_unrelated_and_failed_receipts_are_not_causal_claims():
    r,inp=run()
    for row in r.rows:
        if row.get("evidence_kind")=="group_archived_input_history":
            row["mutates"]=True
    facts=collect_unified_evidence(r.rows,Q)
    assert facts["archived_input_reception_patterns"]==[]
    assert facts["archived_input_collector_observations"]==0
