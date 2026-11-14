"""Offline V2 UI before/after visual fixtures. Never sends real MCP/model calls."""
from __future__ import annotations
import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui-screenshots-v2"
OUT.mkdir(exist_ok=True)
NEXT = (ROOT / "hubitat-mcp-ai-v2" / "rootfs" / "app" / "ui.html").read_text()
PREV = subprocess.run(
    ["git", "show", "origin/main:hubitat-mcp-ai-v2/rootfs/app/ui.html"],
    cwd=ROOT, capture_output=True, text=True, check=True,
).stdout
FIXTURE = {
    "success": True, "elapsed_ms": 1930, "rounds": 2,
    "answer": "## Fictional room check\n\nThe **demo room lamp** reports off in the returned read-only source. This is a synthetic fixture, not a current home measurement.",
    "tool_calls": [
        {"name": "hub_get_device", "success": True, "supports_live_claim": True,
         "elapsed_ms": 169, "response": "FICTIONAL READ ONLY"},
        {"name": "hub_get_app_config", "success": True, "supports_live_claim": False,
         "elapsed_ms": 88, "response": "FICTIONAL RULE"},
    ],
    "answer_stage_trace": [{"stage": "pre_source_review", "after_model_round": 2,
                            "tool_receipts_seen": 2, "successful_tool_receipts_seen": 2}],
}

def handler(html: str) -> type[BaseHTTPRequestHandler]:
    class FixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                value, ctype = html.encode(), "text/html; charset=utf-8"
            elif path.endswith("/api/status"):
                payload = {"version": re.search(r'const UI_VERSION="([^"]+)"', html).group(1), "configured": True,
                           "model": "fictional-model", "device_monitor": {
                               "configured": True, "enabled": True},
                           "tts": {"enabled": False},
                           "recorder": {"status": "fixture-only"}}
                value, ctype = json.dumps(payload).encode(), "application/json"
            elif path.endswith("/api/overview"):
                payload = {"available": True, "read_only": True, "returned_devices": 203,
                           "source_declared_total": 203, "inventory_full_coverage_verified": True,
                           "observed_at_utc": "2026-11-14T02:00:00Z",
                           "metrics": {
                               "lights_on": {"count": 3, "devices_with_state": 5,
                                             "members": [{"name": "DEMO lamp"}]},
                               "motion_active": {"count": 1, "devices_with_state": 6,
                                                 "members": [{"name": "DEMO motion"}]},
                               "battery_low": {"count": 2, "devices_with_state": 19,
                                               "members": [{"name": "DEMO battery",
                                                            "battery_pct": 13}]},
                           },
                           "unclassified_on_switches": 0}
                value, ctype = json.dumps(payload).encode(), "application/json"
            else:
                value, ctype = b"{}", "application/json"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(value)
        def log_message(self, *args):
            pass
    return FixtureHandler

# WCAG relative luminance, measured from real computed browser colours.
# Only normal-size text/labels on ordinary CSS surfaces are audited here;
# plot-axis SVG labels are separately protected by the original dark SVG theme.
CONTRAST_JS = """selectors => {
  function parseColour(value) {
    const match = String(value).match(/rgba?\\(([^)]*)\\)/);
    if (!match) return null;
    const nums = match[1].split(',').map(v => Number(v.trim()));
    if (nums.length < 3 || nums.slice(0,3).some(v => !Number.isFinite(v))) return null;
    return {rgb:nums.slice(0,3), alpha:nums.length>3?nums[3]:1};
  }
  function luminance(rgb) {
    const c = rgb.map(n => {
      const v = n/255;
      return v<=0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4);
    });
    return c[0]*0.2126+c[1]*0.7152+c[2]*0.0722;
  }
  function background(element) {
    for (let current=element; current; current=current.parentElement) {
      const colour=parseColour(getComputedStyle(current).backgroundColor);
      if (colour && colour.alpha===1) return colour.rgb;
    }
    return [255,255,255];
  }
  return selectors.map(selector=>{
    const el=document.querySelector(selector);
    if (!el) return {selector,missing:true};
    const fg=parseColour(getComputedStyle(el).color);
    const bg=background(el);
    const l1=fg?luminance(fg.rgb):0,l2=luminance(bg);
    const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    return {selector,contrast:Math.round(ratio*100)/100,
            foreground:getComputedStyle(el).color,
            background:getComputedStyle(el).backgroundColor};
  });
}"""
AUDIT_SELECTORS = {
    "ask": [
        "#ask .compose-subtitle",
        "#ask .voice-privacy",
        "#ask .overview-tile small",
        "#ask .feed-empty span",
    ],
    "diagnostics": [
        "#diagnostics #cards .metric small",
        "#diagnostics #cards .metric strong",
        "#diagnostics #timelineCard h2",
        "#diagnostics #timelineMeta",
        "#diagnostics #timelineCard .legend",
        "#diagnostics #timelineCard .graph-zoom-hint",
        "#diagnostics #timelineReadout",
        "#diagnostics .graph-popout-link",
    ],
    "evaluation": [
        "#evaluation .card h2",
        "#evaluation .card p.muted",
        "#evaluation .eval-meta",
        "#evaluation .eval-upload",
        "#evaluation .eval-consent span",
        "#evaluation .eval-review-stage h3",
    ],
}


def check_contrast(page, area: str, scheme: str, device: str) -> None:
    samples = page.evaluate(CONTRAST_JS, AUDIT_SELECTORS[area])
    bad = [sample for sample in samples if sample.get("missing") or
           sample.get("contrast", 0) < 4.5]
    if bad:
        raise AssertionError(
            f"{area} {scheme} {device}: normal-text contrast below 4.5:1: {bad}"
        )
    print(f"PASS: {area} {scheme} {device}: " +
          ", ".join(f"{x['selector']}={x['contrast']:.2f}:1" for x in samples))


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for stage, html in (("before", PREV), ("after", NEXT)):
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler(html))
                server.daemon_threads = True
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    for color in ("light", "dark"):
                        for device, width, height in (
                            ("desktop", 1280, 900), ("mobile-390px", 390, 844),
                        ):
                            context = browser.new_context(
                                viewport={"width": width, "height": height},
                                color_scheme=color,
                                reduced_motion="reduce",
                            )
                            page = context.new_page()
                            page.goto(f"http://127.0.0.1:{server.server_port}/",
                                      wait_until="domcontentloaded")
                            page.wait_for_timeout(650)
                            page.evaluate("""payload => {
                              const result = {...payload};
                              const first = {...payload, answer:'DEMO read-only question. The demo light reported off.'};
                              showResult('Which fictional lamp was checked?', first.answer, first, 900);
                              if (typeof archivePriorExchange === 'function') {
                                archivePriorExchange();
                              }
                              showResult('Check the fictional room and its source.', result.answer, result, 1930);
                              const banner = document.createElement('div');
                              banner.style.cssText =
                                'padding:8px;background:#eab34b;color:#101827;' +
                                'font:700 11px system-ui;text-align:center;position:relative;z-index:99';
                              banner.textContent = 'SYNTHETIC V2 UI FIXTURE — NO LIVE HUB OR MODEL';
                              document.body.prepend(banner);
                            }""", FIXTURE)
                            page.wait_for_timeout(200)
                            page.screenshot(
                                path=str(OUT / f"{stage}-{color}-{device}.png"),
                                full_page=False,
                            )
                            if stage == "after":
                                check_contrast(page, "ask", color, device)
                                page.locator("#diagnosticsTab").click()
                                page.evaluate("""() => setCards({last:{
                                  free_os_mb:777.4, java_free_mb:23.3,
                                  java_allocated_heap_used_pct:92.9,
                                  native_load_pct:31.5, latency_ms:39.2
                                }})""")
                                check_contrast(page, "diagnostics", color, device)
                                page.screenshot(
                                    path=str(OUT / f"after-{color}-{device}-diagnostics.png"),
                                    full_page=False,
                                )
                                page.locator("#evaluationTab").click()
                                check_contrast(page, "evaluation", color, device)
                                page.screenshot(
                                    path=str(OUT / f"after-{color}-{device}-evaluation.png"),
                                    full_page=False,
                                )
                            context.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=3)
                    server.server_close()
        finally:
            browser.close()
    print("Saved before/after V2 Ask and after-Diagnostics/Evaluation fixture screenshots:", OUT)

if __name__ == "__main__":
    main()
