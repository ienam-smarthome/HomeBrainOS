"""Browser acceptance with synthetic API replies; never contacts a model or hub."""
import json, os, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
html=(Path(__file__).parents[1]/"rootfs/app/ui.html").read_text()
version=re.search(r'const UI_VERSION="([^"]+)"',html)[1]
answer=r"""## Reported state

| Device | State | Temperature |
| --- | --- | --- |
| **Desk lamp** | `off` | $21.0^\circ\text{C}$ |

Heating $\rightarrow$ Idle; $22.0 \rightarrow 21.0^\circ\text{C}$.
<svg onload=alert(1)><script>window.injected=true</script></svg>
Unknown: $\frac{1}{2}$.
"""
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header("Content-Type","text/html");self.end_headers();self.wfile.write(html.encode())
 def log_message(self,*args):pass
server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 browser=p.chromium.launch()
 for width in [1280,390]:
  page=browser.new_page(viewport={"width":width,"height":1000})
  requests=[];resets=[];bench={"imported":False,"answered":False,"scored":False};bench_runs=[];lab={"answered":False,"graded":False};lab_runs=[];paired={"answered":False,"graded":False};paired_runs=[]
  def api(route):
   request=route.request
   if "/api/reasoning-ab/" in request.url:
    assert request.headers.get("x-homebrain-request")=="1"
    route_name=request.url.split("/api/reasoning-ab/")[1].split("?")[0]
    criteria=("factual_grounding","source_completeness","causal_calibration",
              "command_outcome","usefulness")
    if route_name=="status":
     data={"schema":"homebrain-v2-reasoning-holdout-status.v1",
           "synthetic_only":True,"running":False,"error":None,
           "cases":[{"id":"hold-01","title":"Freezer power dip and alleged outage",
                     "domain":"energy_history",
                     "arms":{label:("completed" if paired["answered"] else "not_run")
                             for label in ("A","B")},
                     "ready_to_rate":paired["answered"],"graded":paired["graded"]}]}
    elif route_name=="case/hold-01":
     ratings={label:{name:2 for name in criteria} for label in ("A","B")}
     data={"id":"hold-01","title":"Freezer power dip and alleged outage",
           "domain":"energy_history",
           "question":"Did <script>window.injected=true</script> lose electric power?",
           "synthetic_only":True,
           "arms":{label:{
               "success":True,
               "answer":"A <img src=x onerror=window.injected=true> is not confirmed" if label=="A"
                         else "B <script>window.injected=true</script> no outage proof",
               "rounds":3,"elapsed_ms":1500,"client_contract_errors":1,
               "simulator_rejections":0,"simulated_commands":0,
               "coverage":[{"label":"Power history","observed":True},
                           {"label":"Switch history","observed":False}],
               "tool_calls":[{"name":"hub_read_devices",
                              "response":"mock <script>not executable</script>"}],
             } for label in ("A","B")} if paired["answered"] else {},
           "ratings":ratings if paired["graded"] else None}
    elif route_name=="run":
     values=request.post_data_json
     assert values["case_id"]=="hold-01"
     assert values["model_execution_consent"] is True
     assert values["cloud_transfer_consent"] is True
     assert values["retry_failed"] is False
     paired_runs.append(values)
     paired["answered"]=True
     data={"started":True,"case_id":"hold-01",
           "synthetic_only":True,"live_mcp_calls":0,"live_device_actions":0}
    elif route_name=="case/hold-01/score":
     data_scores=request.post_data_json["scores"]
     assert set(data_scores)=={"A","B"}
     assert all(set(data_scores[label])==set(criteria) for label in ("A","B"))
     paired["graded"]=True;data={"saved":True,"mapping_hidden":True}
    elif route_name=="report":
     data={"schema":"homebrain-v2-reasoning-holdout-report.v1",
           "synthetic_only":True,"cases_prepared":6,
           "paired_answers_completed":int(paired["answered"]),
           "paired_blind_ratings":int(paired["graded"]),
           "condition_mapping_revealed":False,
           "live_mcp_calls":0,"live_device_actions":0,"cases":[]}
    elif route_name=="stop":data={"stop_requested":False}
    elif route_name=="delete":
     assert request.post_data_json["confirm_delete"] is True
     paired["answered"]=False;paired["graded"]=False;data={"deleted":True}
    else:raise AssertionError("Unknown reasoning experiment browser route "+route_name)
    route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
    return
   if "/api/autonomous/" in request.url:
    assert request.headers.get("x-homebrain-request")=="1"
    path=request.url.split("/api/autonomous/")[1].split("?")[0]
    if path=="status":
     data={"version":"synthetic-autonomous-first-answer.v1","synthetic_only":True,
      "running":False,"error":None,
      "cases":[{"id":"lab-05","title":"Stale sensor vs verified outage",
                "domain":"telemetry","answered":lab["answered"],"graded":lab["graded"]}]}
    elif path=="case/lab-05":
     data={"id":"lab-05","title":"Stale sensor vs verified outage",
       "domain":"telemetry","question":"Investigate <script>window.injected=true</script> synthetic stale telemetry.",
       "synthetic_only":True,
       "answer":"Stale readings; <img src=x onerror=window.injected=true> is unverified." if lab["answered"] else None,
       "ratings":{name:2 for name in ("factual_grounding","source_completeness","causal_calibration",
        "command_outcome","usefulness")} if lab["graded"] else None,
       "success":True,"rounds":3,"elapsed_ms":3000,"simulated_commands":0,
       "blocked_attempts":0,"unsafe_live_actions":0,
       "tool_calls":[{"name":"hub_read_history","response":"synthetic <script>not executable</script>"}] if lab["answered"] else None,
       "coverage":[{"label":"Device health classification","observed":True},
                   {"label":"Event history checked","observed":False}] if lab["answered"] else None}
    elif path=="run":
     values=request.post_data_json
     assert values["case_id"]=="lab-05"
     assert values["model_execution_consent"] is True
     assert values["cloud_transfer_consent"] is True
     lab_runs.append(values);lab["answered"]=True
     data={"started":True,"case_id":"lab-05","synthetic_only":True,"live_mcp_calls":0}
    elif path=="case/lab-05/score":
     scores=request.post_data_json["scores"]
     assert len(scores)==5 and set(scores)=={"factual_grounding","source_completeness",
      "causal_calibration","command_outcome","usefulness"}
     lab["graded"]=True;data={"saved":True}
    elif path=="report":
     data={"schema":"homebrain-v2-autonomous-first-answer.v1","synthetic_only":True,
      "cases_prepared":6,"cases_answered":int(lab["answered"]),"cases_graded":int(lab["graded"]),
      "live_mcp_calls":0,"live_device_actions":0,
      "cases":[{"case":"lab-05","observed_evidence_checks":1,"required_evidence_checks":2}]}
    elif path=="stop":data={"stop_requested":False}
    elif path=="delete":
     assert request.post_data_json["confirm_delete"] is True
     lab["answered"]=False;lab["graded"]=False;data={"deleted":True}
    else:raise AssertionError("Unknown autonomous browser path "+path)
    route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
    return
   if "/api/benchmark/" in request.url:
    assert request.headers.get("x-homebrain-request")=="1"
    path=request.url.split("/api/benchmark/")[1].split("?")[0]
    if path=="status":
     data={"imported":bench["imported"],"running":False,"error":None,
      "cases":[{"id":"case-001","answered":bench["answered"],"graded":bench["scored"]}] if bench["imported"] else []}
    elif path=="import":
     assert request.headers.get("content-type")=="application/zip"
     bench["imported"]=True;data={"imported":True,"pairs":1,"model_calls":0}
    elif path=="run":
     values=request.post_data_json
     assert values["case_ids"]==["case-001"]
     assert values["private_evidence_consent"] is True
     assert values["cloud_transfer_consent"] is True
     assert "tools" not in values
     bench_runs.append(values);bench["answered"]=True
     data={"started":True,"pending":2}
    elif path=="case/case-001":
     data={"id":"case-001","question":"Synthetic private <img onerror=window.injected=true>?",
      "source":[{"tool":"read","result":"<script>window.injected=true</script>"}],
      "both_answered":bench["answered"],
      "answers":{"A":"Synthetic <script>answer A</script>","B":"Answer B"} if bench["answered"] else {},
      "ratings":{label:{"ratings":{name:None for name in
        ("factual_grounding","source_completeness","causal_calibration","command_outcome","usefulness")}}
          for label in ("A","B")}}
    elif path=="case/case-001/score":
     recorded=request.post_data_json["scores"]
     assert set(recorded)=={"A","B"}
     assert all(len(recorded[label])==5 for label in recorded)
     bench["scored"]=True;data={"saved":True}
    elif path=="report":
     data={"schema":"homebrain-v2-fixed-source-report.v1",
      "blind_reviewed_pairs":1 if bench["scored"] else 0,
      "private_values_exported":False,
      "condition_effects":{"factual_grounding":{"role_notes_better":1}}}
    elif path=="stop":data={"stop_requested":False}
    elif path=="delete":
     assert request.post_data_json["confirm_delete"] is True
     bench["imported"]=False;bench["answered"]=False;bench["scored"]=False
     data={"deleted":True}
    else:raise AssertionError("Unexpected benchmark route "+path)
    route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
    return
   if "/api/status" in request.url:data={"version":version,"configured":True,"model":"fixture-model"}
   elif "/api/conversation/clear" in request.url:
    assert request.headers.get("x-homebrain-request")=="1"
    resets.append(request.post_data_json["conversation_id"]);data={"cleared":True}
   elif "/api/ask" in request.url:
    assert request.headers.get("x-homebrain-request")=="1"
    requests.append(request.post_data_json)
    data={"success":True,"answer":answer,"rounds":2,"elapsed_ms":100,"tool_calls":[]}
   elif "/api/diagnostics/status" in request.url:data={"status":"online","cpu_cores":4,"last":{"native_load5":0.7,"native_load_pct":17.5}}
   elif "/api/diagnostics/timeline" in request.url:
    data={"range_start":"2026-11-08T06:00:00Z","range_end":"2026-11-08T12:40:00Z","probe_seconds":30,
          "metrics":{
           "free_os_mb":{"observed_metric_points":4,"source_sample_count":4,"samples":[
             {"recorded_at":"2026-11-08T12:00:00Z","reachable":1,"diag_segment":0,"free_os_mb":830.0},
             {"recorded_at":"2026-11-08T12:00:30Z","reachable":1,"diag_segment":0,"free_os_mb":834.0},
             {"recorded_at":"2026-11-08T12:01:00Z","reachable":1,"diag_segment":0,"free_os_mb":810.0},
             {"recorded_at":"2026-11-08T12:02:00Z","reachable":1,"diag_segment":0,"free_os_mb":828.0}
           ]},
           "native_free_os_mb":{"observed_metric_points":2,"source_sample_count":2,"samples":[
             {"recorded_at":"2026-11-08T12:00:00Z","reachable":1,"diag_segment":0,"native_sample_label":"12:00","native_free_os_mb":845.0},
             {"recorded_at":"2026-11-08T12:05:00Z","reachable":1,"diag_segment":0,"native_sample_label":"12:05","native_free_os_mb":855.0}
           ]},
           "native_load_pct":{"observed_metric_points":3,"source_sample_count":40,"samples":[
             {"recorded_at":"2026-11-08T12:00:00Z","reachable":1,"diag_segment":0,"native_sample_label":"12:00","native_load_pct":15.0},
             {"recorded_at":"2026-11-08T12:05:00Z","reachable":1,"diag_segment":0,"native_sample_label":"12:05","native_load_pct":22.0},
             {"recorded_at":"2026-11-08T12:10:00Z","reachable":1,"diag_segment":0,"native_sample_label":"12:10","native_load_pct":35.0}
           ]}
          },
          "reboots":[{"occurred_at":"2026-11-08T12:14:00Z","firmware":"2.5.3.119","source":"hub_events_json_systemStart"}],
          "incidents":[{"kind":"hub-unreachable","started_at":"2026-11-08T12:20:00Z","recovered_at":"2026-11-08T12:24:00Z"}]}
   elif "/api/diagnostics/history" in request.url:
    percent="metric=native_load_pct" in request.url
    key="native_load_pct" if percent else "native_load5"
    values=[12.5,18.0,16.5,25.5] if percent else [0.50,0.72,0.66,1.02]
    data={"range_start":"2026-11-08T11:50:00Z","range_end":"2026-11-08T12:40:00Z",
          "metric":key,"cpu_cores":4,"observed_metric_points":4,"source_sample_count":40,
          "samples":[
            {"recorded_at":t,"reachable":1,"native_sample_label":label,
             "diag_segment":segment,key:value}
            for t,label,segment,value in zip(
             ["2026-11-08T12:00:00Z","2026-11-08T12:05:00Z",
              "2026-11-08T12:10:00Z","2026-11-08T12:30:00Z"],
             ["12:00","12:05","12:10","12:30"],[0,0,0,1],values)
          ],"incidents":[],"reboots":[]}
   else:data={"range_start":"2026-11-07T00:00:00Z","range_end":"2026-11-08T00:00:00Z","metrics":{}}
   route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
  page.context.route("**/api/**",api)
  errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
  page.goto(f"http://127.0.0.1:{server.server_port}")
  page.locator("#question").fill("Read-only fixture question")
  page.locator("#send").click()
  page.locator("#answer table").wait_for()
  assert page.locator("#answer strong").inner_text()=="Desk lamp"
  assert "21.0°C" in page.locator("#answer").inner_text()
  assert "Heating → Idle" in page.locator("#answer").inner_text()
  assert "22.0 → 21.0°C" in page.locator("#answer").inner_text()
  assert r"$\frac{1}{2}$" in page.locator("#answer").inner_text()
  assert page.locator("#answer svg").count()==0

  assert page.evaluate("window.injected===undefined")
  assert page.locator("#rawAnswer").text_content()==answer
  # Display-only UK formatting: original source and local-time ambiguities survive.
  date_parts=page.evaluate("""() => {
    const rendered=renderAnswer(
      'Timestamp: 2026-11-10T08:10:10.107+0000. Summer: 2026-07-10T08:10:10Z. No zone: 2026-11-10T08:10:10.');
    const dates=[...rendered.querySelectorAll('time')];
    return {
      formatted:dates.map(node=>node.textContent),
      original:dates[0].getAttribute('title'),
      datetime:dates[0].getAttribute('datetime'),
      unqualified:rendered.textContent.includes('No zone: 2026-11-10T08:10:10.')
    };
  }""")
  assert date_parts["formatted"]==[
    "10 Nov 2026, 08:10:10.107 GMT",
    "10 Jul 2026, 09:10:10 BST"
  ],date_parts
  assert "2026-11-10T08:10:10.107+0000" in date_parts["original"]
  assert date_parts["datetime"]=="2026-11-10T08:10:10.107+00:00"
  assert date_parts["unqualified"] is True
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
  # Speak/read-aloud controls stay compact and do not alter private answer receipts.
  assert page.locator("#speak").is_visible()
  assert page.locator("#readAnswer").is_enabled()
  assert page.locator("#readAnswers").is_visible()
  assert page.locator("#voiceStatus").get_attribute("role")=="status"
  page.evaluate("""() => {
    window.__spoken=[];
    window.__audioStops=0;
    window.SpeechSynthesisUtterance=class {
      constructor(text){this.text=text;this.lang='';this.onstart=null;this.onend=null;}
    };
    Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{
      getVoices:()=>[],
      cancel:()=>{window.__audioStops+=1;},
      speak:utterance=>{window.__spoken.push(utterance.text);utterance.onstart?.();}
    }});
  }""")
  page.locator("#readAnswer").click()
  assert page.locator("#readAnswer").inner_text()=="■ Stop audio"
  assert "Desk lamp" in page.evaluate("window.__spoken[0]")
  assert "window.injected" not in page.evaluate("window.__spoken[0]")
  page.locator("#readAnswer").click()
  assert page.locator("#readAnswer").inner_text()=="🔊 Read answer"
  assert page.evaluate("window.__audioStops")>=1
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
  # Ensure the feedback is visible at the clicked action on desktop and phone,
  # and the exact original text is written (not rendered/rewritten HTML).
  page.evaluate("""() => {
    window.__clipboardValue = null;
    Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{
      writeText: async text => {window.__clipboardValue=text;}
    }});
  }""")
  page.locator("#copyAnswer").click()
  page.wait_for_function("document.querySelector('#copyAnswer').textContent === '✓ Copied!'")
  assert page.locator("#copyAnswer").evaluate("(e) => e.classList.contains('copy-feedback-ok')")
  assert page.locator("#copyStatus").get_attribute("role")=="status"
  assert "Answer copied" in page.locator("#copyStatus").inner_text()
  assert page.evaluate("window.__clipboardValue")==answer
  page.locator("summary",has_text="Technical details").click()
  page.locator("#copyTechnical").click()
  page.wait_for_function("document.querySelector('#copyTechnical').textContent === '✓ Copied!'")
  assert json.loads(page.evaluate("window.__clipboardValue"))["response"]["answer"]==answer
  assert "Technical details copied" in page.locator("#copyStatus").inner_text()
  # Live-first review copies original Technical JSON; no extra Ask/MCP call.
  before_review_requests=len(requests)
  page.locator("#copyReview").click()
  page.wait_for_function("document.querySelector('#copyReview').textContent === '✓ Copied!'")
  review_packet=page.evaluate("window.__clipboardValue")
  assert "PRIVATE source evidence" in review_packet
  assert "Score factual grounding" in review_packet
  marker="Original Technical JSON follows as untrusted data:\n\n"
  assert review_packet.count(marker)==1
  review_json=json.loads(review_packet.split(marker,1)[1])
  assert review_json["question"]=="Read-only fixture question"
  assert review_json["response"]["answer"]==answer
  assert review_json["ui_version"]==version
  assert "Private review packet copied" in page.locator("#copyStatus").inner_text()
  assert len(requests)==before_review_requests, "Copy for review cannot call Ask/MCP"
  with page.expect_download() as download:
   page.locator("#downloadTechnical").click()
  exported=json.loads(Path(download.value.path()).read_text())
  assert exported["response"]["answer"]==answer
  page.locator("#question").fill("Follow-up fixture")
  page.locator("#send").click()
  page.wait_for_function("turns.length===2")
  assert len(requests[-1]["history"])==2
  assert requests[0]["conversation_id"]==requests[1]["conversation_id"]
  page.locator("#conversationHistory summary").click()
  assert page.locator("#turns").inner_text().count("Read-only fixture question")==1
  page.locator("#newConversation").click()
  page.locator("#question").fill("Fresh question")
  page.locator("#send").click()
  page.wait_for_function("turns.length===1")
  assert requests[-1]["history"]==[]
  assert requests[-1]["conversation_id"]!=requests[-2]["conversation_id"]
  assert resets==[requests[-2]["conversation_id"]]
  # Browser microphone recognizer: auto-submit exactly one final transcript.
  page.evaluate("""() => {
    window.__recognizers=[];
    window.SpeechRecognition=class {
      start(){window.__recognizers.push(this);}
      abort(){this.onend?.();}
    };
    window.webkitSpeechRecognition=undefined;
  }""")
  before_voice=len(requests)
  page.locator("#speak").click()
  assert page.locator("#speak").get_attribute("aria-pressed")=="true"
  page.evaluate("""() => {
    const recognizer=window.__recognizers.at(-1);
    const row=[{transcript:'How is the hallway temperature?'}];row.isFinal=true;
    recognizer.onresult({results:[row]});
    recognizer.onend();
  }""")
  page.wait_for_function("turns.length===2")
  assert len(requests)==before_voice+1
  assert requests[-1]["question"]=="How is the hallway temperature?"
  assert page.locator("#question").input_value()==requests[-1]["question"]
  assert page.locator("#speak").get_attribute("aria-pressed")=="false"
  # Stop listening cancels; it must not send a partial or phantom question.
  before_cancel=len(requests)
  page.locator("#speak").click()
  page.locator("#speak").click()
  assert len(requests)==before_cancel
  assert "cancelled" in page.locator("#voiceStatus").inner_text().lower()
  page.evaluate("window.SpeechRecognition=undefined;window.webkitSpeechRecognition=undefined")
  page.locator("#speak").click()
  assert "not supported" in page.locator("#voiceStatus").inner_text()
  assert len(requests)==before_cancel
  page.locator("#diagnosticsTab").click()
  page.wait_for_function("document.querySelector('#source').textContent.startsWith('online')")
  page.locator("#incidentTimeline path").first.wait_for()
  assert page.locator("#incidentTimeline path").count()>=2
  assert page.locator("#incidentTimeline circle").count()>=2
  assert "4 external OS-memory observations" in page.locator("#timelineMeta").inner_text()
  assert "3 distinct native 5m CPU readings" in page.locator("#timelineMeta").inner_text()
  assert "fitted to recorded observations" in page.locator("#timelineMeta").inner_text()
  assert "Confirmed startup" in page.locator("#timelineEvents").inner_text()
  assert "Connectivity loss" in page.locator("#timelineEvents").inner_text()
  assert "Lowest observed OS memory" in page.locator("#timelineEvents").inner_text()
  assert "Highest observed 5m CPU load" in page.locator("#timelineEvents").inner_text()
  assert page.locator("#timelineSource").get_attribute("href")=="api/diagnostics/timeline?hours=6"
  assert not page.locator("#timelineInspect").is_disabled()
  page.locator("#timelineInspect").click()
  assert "saved_external_recorder_only" in page.locator("#timelineEvidence").inner_text()
  assert "causality" in page.locator("#timelineEvidence").inner_text()
  page.locator("#incidentTimeline").focus()
  page.keyboard.press("Home")
  assert "Selected" in page.locator("#timelineReadout").inner_text()
  page.keyboard.press("ArrowRight")
  assert "Selected" in page.locator("#timelineReadout").inner_text()
  page.locator("#timelineLayout").select_option("combined")
  assert "5m CPU load equivalent" in page.locator("#incidentTimeline").text_content()
  page.locator("#timelineLayout").select_option("split")
  assert "independent scale" in page.locator("#incidentTimeline").text_content()
  assert "Native OS memory" in page.locator("#timelineCoverage").inner_text()
  assert "not 0%" in page.locator("#timelineCoverage").inner_text()
  # The new source-specific layout has distinct panel locations/scales.
  positions=page.evaluate("""() => ({
    external:timelineShown.yFor('memory',830),
    native:timelineShown.yFor('nativeMemory',850),
    cpu:timelineShown.yFor('cpu',15),
    height:document.querySelector('#incidentTimeline').viewBox.baseVal.height,
    extras:[...document.querySelectorAll('#incidentTimeline circle')]
     .filter(e=>!e.id&&e.dataset.role!=='isolated-source-sample').length
  })""")
  assert positions["external"]<positions["native"]<positions["cpu"],positions
  assert positions["height"]>=540,positions
  assert positions["extras"]==0,"No permanent per-point/extrema dot decorations"
  # Two aligned tall panels are taller and each has an independent scale.
  page.locator("#timelineLayout").select_option("tall")
  assert page.locator("#timelinePair").is_visible()
  assert page.locator("#incidentTimeline").evaluate("(el)=>el.viewBox.baseVal.height")>=720
  pair_areas=page.evaluate("""() => ({
    top:timelineShown.panels.memory,
    bottom:timelineShown.panels.cpu,
    visible:timelineShown.visibleKinds
  })""")
  assert pair_areas["top"]["bottom"]<pair_areas["bottom"]["top"],pair_areas
  assert pair_areas["visible"]==["memory","cpu"],pair_areas
  page.locator("#timelinePair").select_option("native-cpu")
  assert page.evaluate("timelineShown.visibleKinds.join(',')")=="nativeMemory,cpu"
  assert page.locator("#incidentTimeline path[stroke='#70b9ff']").count()==0
  assert page.locator("#incidentTimeline path[stroke='#c4a1ff']").count()==1
  page.locator("#timelinePair").select_option("external-native")
  assert page.evaluate("timelineShown.visibleKinds.join(',')")=="memory,nativeMemory"
  assert page.locator("#incidentTimeline path[stroke='#6ee7b7']").count()==0
  page.locator("#timelineLayout").select_option("overlay")
  assert "CPU load equivalent" in page.locator("#incidentTimeline").text_content()
  page.locator("#timelineLayout").select_option("split")
  assert page.locator("#timelinePair").is_hidden()
  page.locator("#timelineLayout").select_option("tall")
  page.locator("#timelinePair").select_option("native-cpu")
  page.locator("#plotExtent").select_option("full")
  assert "fitted to recorded observations" not in page.locator("#timelineMeta").inner_text()
  # A real new-tab popout refetches the same saved recorder data; no native
  # Hubitat MCP invocation, new query endpoints or chart-source URLs.
  assert page.locator("#timelinePopout").get_attribute("target")=="_blank"
  with page.expect_popup() as popup_info:
   page.locator("#timelinePopout").click()
  popup=popup_info.value
  popup.locator("#incidentTimeline path").first.wait_for()
  assert "graph_view=timeline" in popup.url
  assert "layout=tall" in popup.url and "pair=native-cpu" in popup.url
  assert popup.locator("#timelineLayout").input_value()=="tall"
  assert popup.locator("#timelinePair").input_value()=="native-cpu"
  assert popup.locator("#timelineCard").is_visible()
  assert popup.locator("#detailCard").is_hidden()
  assert popup.locator("#timelineReturn").is_visible()
  assert popup.locator("#incidentTimeline").evaluate("(el)=>el.getBoundingClientRect().height")>=380
  viewport=popup.locator("#incidentTimeline").evaluate("""el=>({
   width:el.viewBox.baseVal.width,
   height:el.viewBox.baseVal.height,
   cssWidth:el.getBoundingClientRect().width
  })""")
  assert viewport["width"]>=860 and viewport["height"]>=780
  assert viewport["width"]>=viewport["cssWidth"]-4
  # Span midnight and compare the real text bounding boxes for collisions.
  popup.evaluate("""() => {
   timelineData.range_start='2026-11-07T06:00:00Z';
   document.querySelector('#plotExtent').value='full';
   drawIncidentTimeline();
  }""")
  labels=popup.locator("#incidentTimeline [data-axis=time]")
  assert labels.count()>=3
  bounds=labels.evaluate_all("els=>els.map(el=>{const b=el.getBBox();return {left:b.x,right:b.x+b.width}})")
  assert all(bounds[i]["right"]<=bounds[i+1]["left"]+1
             for i in range(len(bounds)-1)),bounds
  popup.locator("#incidentTimeline").focus()
  popup.keyboard.press("Home")
  popup.keyboard.press("ArrowRight")
  assert "Selected" in popup.locator("#timelineReadout").inner_text()
  # Drag a translucent selection through both synchronized time panels.
  base_span=popup.evaluate("timelineShown.end-timelineShown.start")
  geom=popup.evaluate("""() => {
   const svg=document.querySelector('#incidentTimeline'),
    rect=svg.getBoundingClientRect(),p=timelineShown.plot,
    vx=svg.viewBox.baseVal.width,vy=svg.viewBox.baseVal.height;
   const px=ratio=>rect.left+(p.left+(p.right-p.left)*ratio)*rect.width/vx;
   return {x1:px(.2),x2:px(.7),x3:px(.35),x4:px(.75),
    y:rect.top+(p.top+30)*rect.height/vy};
  }""")
  popup.mouse.move(geom["x1"],geom["y"])
  popup.mouse.down()
  popup.mouse.move(geom["x2"],geom["y"],steps=8)
  assert popup.locator("#timelineBrush").get_attribute("visibility")=="visible"
  popup.mouse.up()
  assert popup.evaluate("diagnosticZoom!==null")
  assert popup.evaluate("timelineShown.end-timelineShown.start")<base_span
  assert "Zoomed to" in popup.locator("#timelineZoomInfo").inner_text()
  assert popup.locator("#resetTimelineZoom").is_enabled()
  first_zoom=popup.evaluate("timelineShown.end-timelineShown.start")
  popup.mouse.move(geom["x3"],geom["y"])
  popup.mouse.down()
  popup.mouse.move(geom["x4"],geom["y"],steps=6)
  popup.mouse.up()
  assert popup.evaluate("timelineShown.end-timelineShown.start")<first_zoom
  popup.locator("#resetTimelineZoom").click()
  assert popup.evaluate("diagnosticZoom===null")
  assert popup.locator("#resetTimelineZoom").is_disabled()
  assert popup.evaluate("timelineShown.end-timelineShown.start")==base_span
  popup.mouse.click(geom["x1"],geom["y"])
  assert popup.evaluate("diagnosticZoom===null")
  assert "Selected" in popup.locator("#timelineReadout").inner_text()
  popup.close()
  page.locator("#timelineLayout").select_option("split")
  page.locator("#plotExtent").select_option("fit")
  assert page.locator("#recorderNotice").is_hidden()
  page.evaluate("""() => {
    window.__loadLines = 0;
    window.__loadTicks = [];
    const context = CanvasRenderingContext2D.prototype;
    const nativeLineTo = context.lineTo, nativeFillText = context.fillText;
    context.lineTo = function(x,y) {
      if (this.strokeStyle === '#70b9ff') window.__loadLines++;
      return nativeLineTo.call(this,x,y);
    };
    context.fillText = function(value,x,y) {
      window.__loadTicks.push(String(value));
      return nativeFillText.call(this,value,x,y);
    };
  }""")
  page.locator("#metric").select_option("native_load_pct")
  page.wait_for_function("window.__loadLines >= 2")
  assert page.evaluate("window.__loadLines") == 2, "Only adjacent native samples should connect, not across a source gap"
  assert page.evaluate("window.__loadTicks.some(x => /^\\d+(?:\\.\\d+)?%$/.test(x))"), "Native load equivalent Y-axis must display percent, not raw load"
  assert "12.5%" in page.locator("#plotStats").inner_text()
  assert "25.5%" in page.locator("#plotStats").inner_text()
  assert "Native 5m load equivalent (%)" in page.locator("#detailPrimaryLegend").inner_text()
  assert page.locator("#detailCpuLegend").is_hidden(), "Only the selected detail series should appear in its legend"
  assert "configured CPU core count" in page.locator("#source").inner_text()
  assert "Configured CPU cores: 4" in page.locator("#source").inner_text()
  assert "not measured CPU utilisation" in page.locator("#source").inner_text()
  assert "No interpolation" in page.locator("#detailReadout").inner_text()
  assert "Native 5m load equivalent" in page.locator("#detailReadout").inner_text()
  assert "%" in page.locator("#detailReadout").inner_text()
  # A raw/unscaled view remains available for inspecting the original source load.
  page.locator("#metric").select_option("native_load5")
  page.wait_for_function("window.__loadLines >= 4")
  assert page.evaluate("window.__loadTicks.some(x => /^\\d+(?:\\.\\d+)? load$/.test(x))")
  assert "0.5 load" in page.locator("#plotStats").inner_text()
  assert "Native 5m load (raw)" in page.locator("#detailPrimaryLegend").inner_text()
  assert "unscaled" in page.locator("#source").inner_text()
  with page.expect_popup() as detailed_info:
   page.locator("#detailPopout").click()
  detailed=detailed_info.value
  detailed.locator("#graph").wait_for()
  detailed.wait_for_function("document.querySelector('#graph').width > 0")
  assert "graph_view=detail" in detailed.url
  assert detailed.locator("#detailCard").is_visible()
  assert detailed.locator("#timelineCard").is_hidden()
  assert detailed.locator("#detailReturn").is_visible()
  assert detailed.locator("#metric").input_value()=="native_load5"
  assert detailed.locator("#graph").evaluate("(e)=>e.getBoundingClientRect().height")>=380
  detail_span=detailed.evaluate("timelineWindow(timelineData).end-timelineWindow(timelineData).start")
  box=detailed.locator("#graph").bounding_box()
  dx1=box["x"]+60+(box["width"]-80)*.18
  dx2=box["x"]+60+(box["width"]-80)*.74
  dy=box["y"]+box["height"]*.55
  detailed.mouse.move(dx1,dy)
  detailed.mouse.down()
  detailed.mouse.move(dx2,dy,steps=6)
  assert detailed.evaluate("zoomBrush?.kind==='detail'")
  detailed.mouse.up()
  assert detailed.evaluate("diagnosticZoom!==null")
  assert detailed.evaluate("timelineWindow(timelineData).end-timelineWindow(timelineData).start")<detail_span
  assert detailed.locator("#resetDetailZoom").is_enabled()
  assert "Zoomed to" in detailed.locator("#detailZoomInfo").inner_text()
  detailed.locator("#resetDetailZoom").click()
  assert detailed.evaluate("diagnosticZoom===null")
  assert detailed.locator("#resetDetailZoom").is_disabled()
  detailed.close()
  count_before=len(requests)
  page.locator("#timelineAsk").click()
  assert page.locator("#ask").is_visible()
  assert "do not change anything" in page.locator("#question").input_value().lower()
  assert len(requests)==count_before, "Preparing an AI question must never submit it"
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
  # Optional experimental tabs remain accessible but collapsed by default.
  assert not page.locator("#labMenu").evaluate("(el) => el.open")
  page.locator("#labMenu > summary").click()
  assert page.locator("#labMenu").evaluate("(el) => el.open")
  # Simulate the complete phone/tablet A/B workflow with no model or hub.
  page.locator("#benchmarkTab").click()
  assert page.locator("#benchmark").is_visible()
  page.wait_for_function("document.querySelector('#benchStatus').textContent.includes('No private benchmark')")
  page.locator("#benchZip").set_input_files({
   "name":"synthetic-private.zip","mimeType":"application/zip","buffer":b"PKSYNTHETIC"
  })
  page.locator("#benchImport").click()
  page.wait_for_function("document.querySelector('#benchPilot1').value === 'case-001'")
  assert page.locator("#benchRun").is_enabled()
  assert page.locator("#benchImport").is_disabled()
  page.locator("#benchRun").click()
  assert "Approve both" in page.locator("#benchRunStatus").inner_text()
  assert len(bench_runs)==0
  page.locator("#benchPrivateConsent").check()
  page.locator("#benchCloudConsent").check()
  page.locator("#benchRun").click()
  page.wait_for_function("document.querySelector('#benchSave').disabled === false")
  assert len(bench_runs)==1
  assert "<script>answer A</script>" in page.locator("#benchAnswerA").inner_text()
  assert page.locator("#benchAnswerA script").count()==0
  assert page.locator("#benchQuestion img").count()==0
  page.locator("#benchOriginalSources summary").click()
  assert "<script>window.injected=true</script>" in page.locator("#benchSource").inner_text()
  assert page.evaluate("window.injected===undefined")
  for select in page.locator("#benchScoresA select").all()+page.locator("#benchScoresB select").all():
   select.select_option("2")
  page.locator("#benchSave").click()
  page.wait_for_function("document.querySelector('#benchStatus').textContent.includes('1 blind scored')")
  page.locator("#benchReportButton").click()
  page.wait_for_function("document.querySelector('#benchReportPreview').textContent.includes('blind_reviewed_pairs')")
  with page.expect_download() as download:
   page.locator("#benchDownload").click()
  exported=json.loads(Path(download.value.path()).read_text())
  assert exported["blind_reviewed_pairs"]==1
  assert exported["private_values_exported"] is False
  assert "SYNTHETIC" not in json.dumps(exported)
  assert len(requests)==count_before,"Benchmark cannot send an Ask/MCP request"
  # Autonomous lab uses fictional native-shaped MCP only. UI must display
  # untrusted model/source content as text and never call the live Ask endpoint.
  page.locator("#autonomousTab").click()
  assert page.locator("#autonomous").is_visible()
  page.wait_for_function("document.querySelector('#autolabSelect').value === 'lab-05'")
  # Case list loads before asynchronous case detail. Wait for its actual
  # untrusted question text; selector readiness alone is not content readiness.
  page.wait_for_function(
   "() => document.querySelector('#autolabQuestion').textContent.includes('<script>window.injected=true</script>')")
  assert "<script>window.injected=true</script>" in page.locator("#autolabQuestion").inner_text()
  assert page.locator("#autolabQuestion script").count()==0
  page.locator("#autolabRun").click()
  assert "approve both" in page.locator("#autolabStatus").inner_text().lower()
  assert len(lab_runs)==0
  page.locator("#autolabModelConsent").check()
  page.locator("#autolabCloudConsent").check()
  page.locator("#autolabRun").click()
  page.wait_for_function("document.querySelector('#autolabAnswer').textContent.includes('Stale readings')")
  assert len(lab_runs)==1
  assert page.locator("#autolabAnswer img").count()==0
  assert page.evaluate("window.injected===undefined")
  assert "Retrieved" in page.locator("#autolabCoverage").inner_text()
  assert "Not retrieved" in page.locator("#autolabCoverage").inner_text()
  page.locator("#autolabRun").is_disabled()
  for select in page.locator("#autolabScores select").all():
   select.select_option("2")
  page.locator("#autolabSave").click()
  page.wait_for_function("document.querySelector('#autolabStatus').textContent.includes('1 manually scored')")
  page.get_by_role("button",name="Generate report").last.click()
  page.wait_for_function("document.querySelector('#autolabReportPreview').textContent.includes('cases_graded')")
  with page.expect_download() as download:
   page.locator("#autolabDownload").click()
  summary=json.loads(Path(download.value.path()).read_text())
  assert summary["cases_graded"]==1
  assert summary["live_mcp_calls"]==0
  assert "window.injected" not in json.dumps(summary)
  assert len(requests)==count_before,"Autonomous sandbox must not use real Ask/MCP"
  # Blind paired reasoning study: no real MCP calls, safe untrusted text,
  # separate A/B scoring and report that is not prematurely unblinded.
  page.locator("#reasoningTab").click()
  assert page.locator("#reasoning").is_visible()
  # Case options load before the separate asynchronous detail fetch completes.
  # Wait for the genuine fictional question, then test the same XSS contract.
  page.wait_for_function("document.querySelector('#reasoningSelect').value === 'hold-01'")
  page.wait_for_function(
   "document.querySelector('#reasoningQuestion').textContent.includes('<script>window.injected=true</script>')")
  assert "<script>window.injected=true</script>" in page.locator("#reasoningQuestion").inner_text()
  assert page.locator("#reasoningQuestion script").count()==0
  page.locator("#reasoningRun").click()
  assert "Approve both" in page.locator("#reasoningStatus").inner_text()
  assert not paired_runs
  page.locator("#reasoningModelConsent").check()
  page.locator("#reasoningCloudConsent").check()
  page.locator("#reasoningRun").click()
  page.wait_for_function("document.querySelector('#reasoningAnswerA').textContent.includes('not confirmed')")
  assert len(paired_runs)==1
  assert page.locator("#reasoningAnswerA img").count()==0
  assert page.locator("#reasoningAnswerB script").count()==0
  assert page.evaluate("window.injected===undefined")
  assert "Power history" in page.locator("#reasoningMetricsA").inner_text()
  assert "Client schema errors: 1" in page.locator("#reasoningMetricsB").inner_text()
  for select in page.locator("#reasoningScoresA select").all():
   select.select_option("2")
  for select in page.locator("#reasoningScoresB select").all():
   select.select_option("1")
  page.locator("#reasoningSave").click()
  page.wait_for_function("document.querySelector('#reasoningSave').disabled && document.querySelector('#reasoningStatus').textContent.includes('1 blindly scored')")
  assert all(el.is_disabled() for el in page.locator("#reasoningScoresA select").all())
  assert all(el.is_disabled() for el in page.locator("#reasoningScoresB select").all())
  assert "saved and locked" in page.locator("#reasoningReviewStatus").inner_text()
  page.get_by_role("button",name="Generate aggregate report").click()
  page.wait_for_function("document.querySelector('#reasoningReportPreview').textContent.includes('paired_blind_ratings')")
  with page.expect_download() as download:
   page.locator("#reasoningDownload").click()
  exported_pair=json.loads(Path(download.value.path()).read_text())
  assert exported_pair["paired_blind_ratings"]==1
  assert exported_pair["condition_mapping_revealed"] is False
  assert "window.injected" not in json.dumps(exported_pair)
  assert len(requests)==count_before,"Reasoning A/B cannot use real Ask/MCP"
  page.locator("#askTab").click()
  assert page.locator("#question").is_visible()
  assert not page.locator("#labMenu").evaluate("(el) => el.open")
  assert not errors,errors
  page.screenshot(path=str(Path(os.environ.get("RUNNER_TEMP","/tmp"))/f"v2-ui-{width}.png"),full_page=True)
  page.close()
 browser.close()
server.shutdown()
print("Desktop/mobile browser acceptance passed: clipboard, formatting, popouts, drag-zoom/reset, timeline inspection and recorder state.")
