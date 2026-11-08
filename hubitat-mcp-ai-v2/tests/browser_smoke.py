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
| **Desk lamp** | \`off\` | $21.0^\circ\text{C}$ |

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
   elif "/api/diagnostics/status" in request.url:data={"status":"disabled","last":{}}
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
  page.locator("#recorderNotice").wait_for()
  assert "disabled" in page.locator("#recorderNotice").inner_text()
  page.locator("#askTab").click()
  assert page.locator("#question").is_visible()
  assert not errors,errors
  page.screenshot(path=str(Path(os.environ.get("RUNNER_TEMP","/tmp"))/f"v2-ui-{width}.png"),full_page=True)
  page.close()
 browser.close()
server.shutdown()
print("Desktop/mobile browser acceptance passed: formatting, XSS, export, history/reset, tabs and recorder state.")
