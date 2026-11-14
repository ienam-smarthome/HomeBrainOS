"""Synthetic, disconnected visual snapshots for the command-first UI pull request.

Only a loopback fixture server is used; no Hubitat, HA, Ollama or real device
connectivity. The base render comes from Git history; the proposed render from
the checkout under test. Screenshots are labelled fictional in-page.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ui-screenshots"
OUTPUT.mkdir(exist_ok=True)
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"


def _renderers() -> dict[str, object]:
    base = subprocess.run(
        ["git", "show", "origin/main:hubitat-mcp-ai/rootfs/app/webui.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    namespace: dict = {"__name__": "_baseline_webui"}
    exec(compile(base, "baseline-webui.py", "exec"), namespace)
    sys.path.insert(0, str(APP))
    from webui import render_page
    return {"before": namespace["render_page"], "after": render_page}


FIXTURE = {
    "success": True,
    "route": "fixture-only",
    "model": "fixture-model",
    "elapsed_ms": 1482,
    "model_tier_requested": "free",
    "message": (
        "The fictional relay proposal is waiting for approval. "
        "No native command has executed. The returned read receipt identifies "
        "a demo device; it does not verify a future physical effect."
    ),
    "confirmation_required": True,
    "pending_action_card": {
        "status": "pending_confirmation",
        "effect_class": "sensitive_write",
        "summary": "1 proposed native write — not executed",
        "actions": [
            {"tool": "hub_manage_rule_machine", "effect": "sensitive_write",
             "command": "create", "fields": [
                 {"kind": "device", "value": "DEMO-1"},
                 {"kind": "time", "value": "01:00"},
                 {"kind": "days", "value": "Monday, Tuesday"},
             ]},
        ],
        "dry_run_available": False,
        "undo_available": False,
        "edits_require_new_proposal": True,
    },
    "metrics": {
        "model_round_details": [{"model": "fixture-model", "elapsed_ms": 833}],
    },
    "evidence": [
        {"tool": "hub_get_device", "success": True,
         "supports_live_claim": True, "elapsed_ms": 140},
        {"tool": "hub_list_rules", "success": True,
         "supports_live_claim": False, "elapsed_ms": 120},
    ],
}


def _handler(page_html: str) -> type[BaseHTTPRequestHandler]:
    class FixtureServer(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                data, mime = page_html.encode("utf-8"), "text/html; charset=utf-8"
            else:
                path = path.removeprefix("/")
                if path.endswith("api/status"):
                    payload = {
                        "mcp": {"online": True, "tools": 48},
                        "ollama": {"configured": True, "model": "fixture-model"},
                        "paid_routing": {"enabled": False},
                        "claude": {"configured": False},
                    }
                elif path.endswith("api/dashboard"):
                    payload = {
                        "success": True, "source": "fixture-inventory",
                        "lights_on": 3, "motion_active": 7, "low_batteries": 2,
                        "devices": 203, "active_rooms": [{"name": "Demo Room"}],
                        "hub_info": {"name": "Fictional Hubitat"},
                    }
                else:
                    payload = {"success": False, "latest": None,
                               "schedule": {}, "status": "not_recorded"}
                data, mime = json.dumps(payload).encode("utf-8"), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: object) -> None:
            pass

    return FixtureServer


def capture() -> None:
    with sync_playwright() as browser:
        chromium = browser.chromium.launch(headless=True)
        try:
            for stage, renderer in _renderers().items():
                html = renderer("HomeBrainOS", "0.18.460")
                server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(html))
                server.daemon_threads = True
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    for theme in ("light", "dark"):
                        for size, width, height in (
                            ("desktop", 1240, 900), ("mobile-390px", 390, 844)
                        ):
                            context = chromium.new_context(
                                viewport={"width": width, "height": height},
                                color_scheme=theme,
                                reduced_motion="reduce",
                            )
                            page = context.new_page()
                            page.goto("http://127.0.0.1:" + str(server.server_port) + "/",
                                      wait_until="domcontentloaded")
                            page.evaluate(
                                """payload => {
                                  const fixture = { ...payload };
                                  if (typeof beginExchange === 'function') {
                                    beginExchange('Check the fictional relay status.');
                                    showAnswer({
                                      success: true, route: 'fixture-only',
                                      message: 'Fictional relay status: inspected only. No changes.',
                                      evidence: [{ tool: 'hub_get_device', success: true,
                                                   supports_live_claim: true, elapsed_ms: 90 }]
                                    });
                                    beginExchange('Propose a fictional relay automation.');
                                  } else {
                                    document.getElementById('query').value =
                                      'Propose a fictional relay automation.';
                                  }
                                  showAnswer(fixture);
                                  const banner = document.createElement('p');
                                  banner.textContent = 'SYNTHETIC UI FIXTURE — NO LIVE HUB OR DEVICES';
                                  banner.style.cssText =
                                    'padding:8px;background:#e7a840;color:#131313;' +
                                    'font:700 11px system-ui;text-align:center;margin:0 0 8px';
                                  document.body.prepend(banner);
                                  if (typeof syncCommandBar === 'function') syncCommandBar();
                                }""",
                                FIXTURE,
                            )
                            page.wait_for_timeout(450)
                            page.screenshot(
                                path=str(OUTPUT / f"{stage}-{theme}-{size}.png"),
                                full_page=False,
                            )
                            context.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
        finally:
            chromium.close()


if __name__ == "__main__":
    capture()
    print("Wrote synthetic UI screenshots to", OUTPUT)
