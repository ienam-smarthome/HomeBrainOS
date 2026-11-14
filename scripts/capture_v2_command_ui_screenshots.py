"""Offline V2 UI before/after visual fixtures. Never sends real MCP/model calls."""
from __future__ import annotations
import json
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
                payload = {"version": "2.0.0-alpha.81" if "2.0.0-alpha.81" in html
                           else "2.0.0-alpha.80", "configured": True,
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
                            context.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=3)
                    server.server_close()
        finally:
            browser.close()
    print("Saved eight V2-only synthetic UI screenshots:", OUT)

if __name__ == "__main__":
    main()
