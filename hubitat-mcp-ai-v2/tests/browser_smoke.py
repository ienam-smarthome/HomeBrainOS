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
  requests=[];resets=[]
  def api(route):
   request=route.request
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
  page.route("**/api/**",api)
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
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
  page.locator("summary",has_text="Technical details").click()
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
  assert "5m CPU equivalent" in page.locator("#incidentTimeline").text_content()
  page.locator("#timelineLayout").select_option("split")
  assert "independent scale" in page.locator("#incidentTimeline").text_content()
  page.locator("#plotExtent").select_option("full")
  assert "fitted to recorded observations" not in page.locator("#timelineMeta").inner_text()
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
  count_before=len(requests)
  page.locator("#timelineAsk").click()
  assert page.locator("#ask").is_visible()
  assert "do not change anything" in page.locator("#question").input_value().lower()
  assert len(requests)==count_before, "Preparing an AI question must never submit it"
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
  page.locator("#askTab").click()
  assert page.locator("#question").is_visible()
  assert not errors,errors
  page.screenshot(path=str(Path(os.environ.get("RUNNER_TEMP","/tmp"))/f"v2-ui-{width}.png"),full_page=True)
  page.close()
 browser.close()
server.shutdown()
print("Desktop/mobile browser acceptance passed: formatting, XSS, export, history/reset, tabs and recorder state.")
