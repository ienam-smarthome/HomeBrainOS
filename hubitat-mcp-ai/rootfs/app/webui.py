from __future__ import annotations

import html
import json


def render_page(title: str, version: str) -> str:
    """Render the self-contained Home Assistant ingress UI."""

    safe_title = html.escape(title)
    # json.dumps() does not escape a literal "</script>" sequence inside the
    # string it encodes -- these values are interpolated directly into an
    # inline <script> block below, so an unescaped "</script>" in either
    # value would close the script tag early and let anything following it
    # be parsed as raw HTML. title comes from admin/add-on config
    # (web_title), not a remote-input surface, but the escape is cheap and
    # correct defense-in-depth regardless of where the value originates.
    # The standard fix: escape the forward slash in "</" so the JS engine
    # still parses it as the same string via a (harmless) backslash escape,
    # while the raw "</script>" byte sequence never appears in the markup.
    title_json = json.dumps(title).replace("</", "<\\/")
    version_json = json.dumps(version).replace("</", "<\\/")
    return (
        r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0b0c">
<title>__SAFE_TITLE__</title>
<style>
:root{color-scheme:dark;--bg:#0b0b0c;--card:#1f1f21;--tile:#303033;--text:#fff;--muted:#b9b9bd;--blue:#2f7df6;--green:#166534;--red:#991b1b;--amber:#b45309}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,sans-serif}.wrap{max-width:960px;margin:auto;padding:16px}h1{font-size:30px;margin:4px 0 10px}.card{background:var(--card);border-radius:14px;padding:12px;margin:8px 0}.row,.grid{display:flex;gap:8px;flex-wrap:wrap}.pill{padding:8px 12px;border-radius:999px;background:#3a3a3d;font-size:13px}.pill.ok{background:var(--green)}.pill.error{background:var(--red)}.pill strong{margin-left:4px}.status-card{padding:8px 10px;gap:6px;margin:8px 0}.status-card .pill{padding:5px 8px;font-size:11px;line-height:1.15}.status-card .pill strong{margin-left:3px;font-size:11px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.tile{background:var(--tile);border-radius:12px;padding:10px;min-width:0}.big{font-size:20px;font-weight:700;overflow-wrap:anywhere;word-break:break-word}.top-stats{grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:7px}.top-stats .tile{margin:0;padding:7px 5px;min-height:66px;font-size:12px;line-height:1.15}.top-stats .big{font-size:19px}.top-stats .muted{font-size:10px;line-height:1.15;margin-top:2px}.muted{color:var(--muted);font-size:13px}input,button{width:100%;border:0;border-radius:12px;padding:14px;margin:7px 0;font:inherit}input{background:#fff;color:#111}button{background:var(--blue);color:#fff;cursor:pointer}.query-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:7px 0}.query-actions button{margin:0}.answer-options{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin:6px 0}.answer-options label{margin:0}.browser-shortcut{display:none;width:auto;margin:0;padding:8px 10px;font-size:12px}.browser-shortcut.visible{display:inline-block}.secondary{background:#333}.confirm{background:var(--green)}.answer{background:#000;border-radius:12px;padding:14px;min-height:52px;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}.answer-meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.badge{background:#243044;border-radius:999px;padding:4px 8px;font-size:12px}.outcome-badge{font-weight:700}.outcome-positive{background:#14532d;color:#bbf7d0}.outcome-warning{background:#78350f;color:#fde68a}.outcome-neutral{background:#3f3f46;color:#e4e4e7}.outcome-critical{background:#7f1d1d;color:#fecaca}.answer-text{white-space:pre-wrap}.technical{margin-top:12px;color:var(--muted)}.technical summary{cursor:pointer}.technical pre{white-space:pre-wrap;overflow:auto;max-height:260px;background:#111;padding:10px;border-radius:8px}.busy{opacity:.65}
.clear-context{width:auto;margin:0;padding:6px 10px;border-radius:9px;font-size:12px;white-space:nowrap}
.model-tier-picker{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:7px 0 3px}
.model-tier-picker label{font-size:12px;color:var(--muted)}
.model-tier-picker select{width:auto;max-width:100%;background:#303033;color:#fff;border:1px solid #56565c;border-radius:9px;padding:8px 10px;font-size:13px}
.model-tier-note{font-size:11px;color:var(--muted);line-height:1.4}
@media(max-width:520px){.model-tier-picker select{flex:1;min-width:185px}}
.answer-text p{margin:0 0 10px}.answer-text p:last-child{margin-bottom:0}.answer-text h2,.answer-text h3{margin:14px 0 6px;font-size:18px}.answer-text ul,.answer-text ol{margin:6px 0 10px;padding-left:24px}.answer-text li{margin:5px 0}.status-label{display:inline-block;border-radius:999px;padding:2px 8px;margin-right:7px;font-size:11px;font-weight:700;letter-spacing:.03em;vertical-align:1px}.status-active{background:#14532d;color:#bbf7d0}.status-disabled{background:#3f3f46;color:#e4e4e7}.status-paused{background:#78350f;color:#fde68a}.status-broken{background:#7f1d1d;color:#fecaca}.status-unknown{background:#1e3a8a;color:#bfdbfe}.inline-critical{color:#f87171;font-weight:700}.heading-active{color:#4ade80}.heading-disabled{color:#a1a1aa}.heading-paused{color:#fbbf24}.heading-broken{color:#f87171}.heading-unknown{color:#60a5fa}
.health-heading{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.health-status-chip{display:inline-block;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:700}.health-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}
#hubDiagnosticsCard .health-grid{grid-template-columns:repeat(5,minmax(0,1fr))}
@media(max-width:900px){#hubDiagnosticsCard .health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}.health-stat{background:#111;border-radius:10px;padding:10px}.health-ok{color:#4ade80}.health-warn{color:#fbbf24}.health-critical{color:#f87171}.health-neutral{color:#a1a1aa}.health-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.health-actions button{width:auto;margin:0}.health-details{margin-top:10px}.health-details summary{cursor:pointer}.health-domain-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:8px 0 12px}.health-domain{background:#111;border-radius:9px;padding:8px}.health-domain strong{display:block}.health-section{margin-top:10px}.health-list{margin:6px 0 0;padding-left:22px}.health-list li{margin:5px 0;color:#e5e7eb}.health-target-critical,.health-state-critical{color:#f87171;font-weight:600}.health-target-warning,.health-state-warning{color:#fbbf24;font-weight:600}.health-new{font-weight:700}.health-resolved{color:#4ade80}\n.automation-view{white-space:normal}.automation-summary{margin:0 0 10px}.automation-toolbar{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.automation-toolbar input{flex:1 1 220px;margin:0;padding:10px}.automation-toolbar button{width:auto;margin:0;padding:9px 11px;font-size:12px}.automation-filters{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 12px}.automation-filter{width:auto;margin:0;padding:7px 10px;background:#27272a;font-size:12px}.automation-filter.selected{background:var(--blue)}.automation-section{border:1px solid #29292d;border-radius:10px;margin:8px 0;background:#111}.automation-section summary{cursor:pointer;padding:11px 12px;font-weight:700;list-style-position:inside}.automation-section ul{margin:0;padding:0 12px 10px 34px}.automation-section li{margin:6px 0}.automation-section[hidden]{display:none}.automation-kind{color:var(--muted);font-size:11px;margin-left:6px}.automation-empty{color:var(--muted);padding:8px 0}.automation-section-active summary{color:#4ade80}.automation-section-disabled summary{color:#a1a1aa}.automation-section-paused summary{color:#f87171}.automation-section-broken summary{color:#f87171}.automation-section-unknown summary{color:#60a5fa}
.mic-fab{position:fixed;right:18px;bottom:18px;z-index:10;width:64px;height:64px;margin:0;border-radius:50%;font-size:27px;background:var(--green);box-shadow:0 10px 30px rgba(0,0,0,.5)}.mic-fab.listening{background:#dc2626}.copy-button{width:auto;display:block;margin:10px 0 0 auto;padding:7px 10px;font-size:12px}.technical-copy{margin-top:7px}.copy-ok{background:var(--green)}.copy-fail{background:var(--red)}
@media(max-width:520px){.wrap{padding:8px 8px 82px}h1{font-size:23px;margin:2px 0 7px}.card{border-radius:10px;padding:8px;margin:6px 0}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.top-stats{grid-template-columns:repeat(4,minmax(0,1fr));padding:5px;gap:4px}.top-stats .tile{min-height:54px;padding:5px 3px;font-size:10px}.top-stats .big{font-size:17px}.top-stats .muted{display:none}.health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.health-stat{padding:7px}.mic-fab{right:12px;bottom:12px;width:58px;height:58px;font-size:23px}.automation-toolbar input{flex-basis:100%}}
.answer-table-wrap{max-width:100%;overflow-x:auto;margin:8px 0 14px;border:1px solid #38383d;border-radius:9px}
.answer-markdown-table{border-collapse:collapse;width:100%;min-width:max-content;font-size:13px;line-height:1.45}
.answer-markdown-table th,.answer-markdown-table td{border-bottom:1px solid #36363a;padding:8px 10px;text-align:left;vertical-align:top;min-width:90px;max-width:300px;white-space:normal;overflow-wrap:anywhere}
.answer-markdown-table th{background:#28282c;font-weight:700;position:sticky;top:0}
.answer-markdown-table tbody tr:nth-child(even){background:#1b1b1e}
.answer-markdown-table tbody tr:last-child td{border-bottom:0}
.journal-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}
.journal-stat{background:#111;border-radius:9px;padding:9px;min-width:0}
.journal-stat .big{font-size:17px}
.journal-streams{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:12px}
.journal-stream{padding:4px 8px;background:#242427;border-radius:7px}
.journal-stream strong{font-weight:700}
.journal-events,.journal-gaps{margin:7px 0 0;padding:0;list-style:none}
.journal-events li,.journal-gaps li{border-bottom:1px solid #303035;padding:7px 0;overflow-wrap:anywhere;font-size:12px}
.journal-events li:last-child,.journal-gaps li:last-child{border-bottom:0}
.journal-small{font-size:12px;color:var(--muted);line-height:1.4}
.journal-events strong{font-size:13px}
.journal-actions{display:flex;align-items:center;gap:8px;margin-top:8px}
.journal-actions button{width:auto;padding:7px 11px;margin:0;font-size:12px}
@media(max-width:520px){.journal-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.journal-stat{padding:7px}}

.journal-browser-controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin:9px 0}
.journal-browser-controls label{display:block;font-size:12px;color:var(--muted)}
.journal-browser-controls input,.journal-browser-controls select{display:block;width:100%;background:#151518;color:#fff;border:1px solid #49494e;border-radius:7px;margin:4px 0;padding:9px;font-size:14px}
.journal-browser-table-wrap{max-width:100%;overflow:auto;max-height:360px;margin:7px 0}
.journal-browser-table{border-collapse:collapse;width:100%;font-size:12px;min-width:610px}
.journal-browser-table th,.journal-browser-table td{padding:8px;border-bottom:1px solid #39393d;vertical-align:top;text-align:left;overflow-wrap:anywhere}
.journal-browser-table th{position:sticky;top:0;background:#242428}
@media(max-width:520px){.journal-browser-controls{grid-template-columns:1fr 1fr}.journal-browser-controls label:first-child{grid-column:span 2}}


/* Unified read-only incident timeline: two independent metric scales, common x-axis. */
.diag-timeline-legend{display:flex;gap:12px;flex-wrap:wrap;margin:7px 0;color:var(--muted);font-size:12px}
.diag-timeline-legend .swatch{display:inline-block;width:13px;height:3px;margin-right:4px;vertical-align:middle}
.diag-timeline-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:9px 0}
.diag-timeline-actions button,.diag-timeline-actions a{width:auto;margin:0;padding:8px 11px;border-radius:9px;font-size:12px}
.diag-timeline-actions a{background:#333;color:white;text-decoration:none}
#diagTimelineChart{display:block;width:100%;height:auto;max-height:360px;background:#101114;border-radius:9px;touch-action:pan-y}
#diagTimelineChart:focus{outline:2px solid #93c5fd;outline-offset:2px}
#diagChart{display:block;width:100%;height:auto;max-height:375px;background:#101114;border-radius:9px;touch-action:pan-y}
#diagChart:focus-visible{outline:2px solid #93c5fd;outline-offset:2px}
.diag-chart-legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0}
.diag-chart-legend .swatch{display:inline-block;width:18px;height:0;border-top:2px solid #60a5fa;margin-right:5px;vertical-align:middle}
.diag-chart-legend .guide{border-top:2px dotted #cbd5e1}
.diag-chart-legend .startup{border-top:2px dashed #f59e0b}
.diag-timeline-actions label{font-size:12px;color:var(--muted)}
.diag-timeline-actions select{margin-left:5px;padding:7px;border:1px solid #555;border-radius:7px;background:#333;color:#fff;font-size:12px}
#diagTimelineEvents{max-height:310px;overflow-y:auto}
#diagTimelineEvents li{display:flex;gap:7px;align-items:flex-start;flex-wrap:wrap}
#diagTimelineEvents button{width:auto;padding:5px 8px;margin:0 0 0 auto;border-radius:7px;font-size:11px}
#diagTimelineEvents .timeline-evidence{flex:1 1 220px}

/* Explicit incident drill-down; local evidence only, never polling or commands. */
#diagReviewDetails{margin:13px 0;border:1px solid #4b5563;padding:10px;border-radius:10px}
#diagReviewDetails[hidden]{display:none}
.diag-review-controls{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:8px 0}
.diag-review-controls label{font-size:12px;color:var(--muted)}
.diag-review-controls select{background:#333;color:white;border:1px solid #555;border-radius:7px;padding:7px}
.diag-review-controls button,.diag-review-controls a{width:auto;margin:0;padding:7px 10px;font-size:12px}
.diag-review-controls a{background:#333;border-radius:8px;color:white;text-decoration:none}
.diag-review-list{max-height:230px;overflow-y:auto}
.diag-review-list li{font-size:12px;line-height:1.4}
.diag-review-stat{font-size:13px;color:#e5e7eb;line-height:1.6;margin:8px 0}
.diag-review-stat strong{color:white}

/* Command-first shell: prototype geometry, real app data and no network assets. */
:root{color-scheme:dark;--bg:#0a1220;--card:#111c30;--tile:#16243d;--text:#e8eef8;--muted:#b3c4da;--blue:#4ea3ff;--green:#206448;--red:#9f2937;--amber:#bd8525;--edge:#33476a;--focus:#88c7ff;--accent-ink:#06182e}
@media(prefers-color-scheme:light){:root{color-scheme:light;--bg:#f3f6fb;--card:#fff;--tile:#eaf0f9;--text:#13203a;--muted:#51627f;--blue:#1769d1;--green:#0e7050;--red:#bd2c3b;--amber:#9b6200;--edge:#c4d0e2;--focus:#005dc5;--accent-ink:#fff}}
body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15px;line-height:1.5}
.wrap{max-width:1100px;padding:0 18px 48px;min-height:100vh}
.hb-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 0 10px}
.hb-header h1{font-size:19px;font-weight:650;margin:0;letter-spacing:-.03em}
.hb-header h1 small{display:block;font-size:11px;color:var(--muted);font-weight:450;letter-spacing:0}
.connection-host{position:relative}
#connectionPill{width:auto;margin:0;background:var(--card);color:var(--text);border:1px solid var(--edge);border-radius:999px;padding:7px 12px;font-size:12px;white-space:nowrap}
#connectionPill.online{color:var(--text)}
.connection-panel{position:absolute;z-index:35;right:0;top:42px;width:min(340px,calc(100vw - 36px));padding:13px;background:var(--card);border:1px solid var(--edge);border-radius:13px;box-shadow:0 15px 38px #0005}
.connection-panel[hidden]{display:none}.connection-panel strong{font-size:13px}
.connection-panel .status-card{background:none;padding:4px 0;display:flex;margin:10px 0;gap:5px}
.connection-panel .pill{background:var(--tile);color:var(--text);border:1px solid var(--edge);padding:6px 8px}
.connection-panel .pill.ok{background:#126143;color:#fff}.connection-panel .pill.error{background:#93303b;color:#fff}
.connection-panel .pill .muted{color:inherit}.connection-panel .pill strong{font-size:11px}
.connection-meta{color:var(--muted);font-size:12px;margin:7px 0}
#checkConnection{width:auto;margin:3px 0;padding:8px 11px;font-size:12px}
.command-bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:20;background:var(--bg);padding:3px 0 11px}
.command-form{display:flex;align-items:center;gap:10px;background:var(--card);border:1.5px solid var(--edge);border-radius:20px;padding:9px;min-height:78px}
.command-form:focus-within{border-color:var(--blue)}
.command-mic{flex:none;touch-action:none;user-select:none;-webkit-user-select:none;width:52px;height:52px;padding:0;margin:0;border-radius:50%;background:var(--blue);color:var(--accent-ink);border:0;font-size:21px}
.command-mic.listening{background:#b91c1c;color:#fff;box-shadow:0 0 0 3px #b91c1c33}
#query{flex:1;min-width:0;width:100%;max-height:132px;min-height:44px;height:49px;margin:0;border:0;background:transparent;color:var(--text);font:inherit;font-size:17px;line-height:1.45;resize:none;overflow-y:auto;padding:7px 0}
#query:focus-visible{outline:0}
.command-submit{flex:none;width:auto;margin:0;border:0;border-radius:13px;background:var(--tile);color:var(--muted);font-weight:650;padding:13px 18px}
.command-submit.ready:not(:disabled){background:var(--blue);color:var(--accent-ink)}
.command-submit:disabled{opacity:.75;cursor:default}
.command-help{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--muted);padding:6px 3px 0}
.command-bar .model-tier-picker,.command-bar .answer-options{margin:5px 0 0;gap:7px}
.command-bar .model-tier-picker select{background:var(--card);color:var(--text);border:1px solid var(--edge);margin:0}
.command-bar .model-tier-note{margin-top:3px;color:var(--muted)}
.command-bar .model-tier-picker button{padding:6px 10px;margin:0}
.command-bar .answer-options{font-size:12px;color:var(--muted)}
.homebrain-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:18px}
.overview-rail{grid-row:1;min-width:0}
#summaryTiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:7px;margin:0;background:transparent}
#summaryTiles .tile{background:transparent;color:var(--text);border:0;padding:9px 7px;min-width:0;text-align:left;min-height:51px}
#summaryTiles .tile .big{font-size:20px;line-height:1.2}
#summaryTiles .tile div:last-child{font-size:12px;color:var(--muted)}
.overview-note{font-size:11px;color:var(--muted);margin:3px 5px 12px}
.exchange-feed{grid-row:2;display:flex;flex-direction:column;gap:14px;min-width:0}
.feed-empty{color:var(--text);margin:10px 3px 16px;font-size:21px;font-weight:600}
.feed-empty span{display:block;font-weight:400;font-size:14px;color:var(--muted)}
.exchange{background:var(--card);border:1px solid var(--edge);border-radius:15px;padding:15px 17px;margin:0;min-width:0;overflow-wrap:anywhere}
.exchange[hidden]{display:none}.exchange.older{opacity:.76}
.exchange-question{font-size:13px;color:var(--muted);margin:0 0 11px}
.exchange-question strong{color:var(--text);font-weight:550}
.exchange .answer-meta{margin:0 0 10px}.exchange .badge{background:var(--tile);color:var(--text);border:1px solid var(--edge)}
.exchange .answer-text{color:var(--text);font-size:15px;line-height:1.7}
.exchange .answer-text h2,.exchange .answer-text h3{color:var(--text)}
.exchange .answer-table-wrap{border-color:var(--edge)}
.exchange .answer-markdown-table th{background:var(--tile);color:var(--text)}
.exchange .answer-markdown-table td{color:var(--text)}
.exchange .answer-markdown-table tbody tr:nth-child(even){background:var(--tile)}
.exchange .technical pre{background:var(--bg);color:var(--text)}
.exchange-actions{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0 0}
.exchange-actions button{width:auto;display:inline-flex;gap:5px;align-items:center;background:var(--tile);border:1px solid var(--edge);color:var(--text);font-size:12px;padding:7px 10px;margin:0}
.exchange .choice-button{width:auto;margin:5px 6px 5px 0}
.work-trace{border-left:2px solid var(--edge);margin:9px 0 12px 5px;padding-left:14px;font-size:12px;color:var(--muted)}
.work-trace li{padding:2px 0;list-style:none;position:relative}
.work-trace li::before{position:absolute;content:'';height:8px;width:8px;border-radius:50%;background:var(--blue);left:-19px;top:9px}
.work-trace small{float:right;color:var(--muted);font-size:11px}
.trace-summary{cursor:pointer;font-size:12px;color:var(--muted)}
.evidence-drawer{margin-top:12px;border-top:1px solid var(--edge);padding-top:8px}
.evidence-drawer summary{color:var(--muted);font-size:13px;cursor:pointer}
.evidence-row{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--edge);padding:7px 0;font-size:12px;color:var(--text)}
.evidence-row small{color:var(--muted)}
.private-warning{font-size:12px;color:var(--muted);margin:7px 0}
.action-card{border:1px solid var(--edge);border-left:4px solid var(--blue);border-radius:12px;padding:12px;background:var(--tile);margin:12px 0}
.action-card.destructive_write{border-left-color:#eb7880}.action-card.sensitive_write{border-left-color:#f2b84b}
.action-card h3{color:var(--text);font-size:15px;margin:0 0 5px}
.action-card .muted{color:var(--muted)}
.action-card .action-chips{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}
.action-chip{background:var(--card);border:1px solid var(--edge);border-radius:8px;padding:5px 8px;color:var(--text);font-size:12px}
.action-chip input{width:120px;max-width:180px;margin:0;padding:3px 5px;color:var(--text);background:var(--card);border:1px solid var(--edge)}
.action-controls{display:flex;gap:7px;flex-wrap:wrap}
.action-controls button{width:auto;margin:0;padding:8px 13px;font-size:13px;background:var(--card);color:var(--text);border:1px solid var(--edge)}
.action-controls button.confirm{background:var(--blue);color:var(--accent-ink);border:0}
.action-note{margin:8px 0 0;color:var(--muted);font-size:12px}
.monitoring-panels{margin-top:24px;border-top:1px solid var(--edge);padding-top:13px}
.monitoring-panels summary{cursor:pointer;font-size:13px;color:var(--muted)}
.monitoring-body{margin-top:14px}.monitoring-body .card{background:var(--card);border:1px solid var(--edge)}
.monitoring-body .muted,.monitoring-body .journal-small{color:var(--muted)}
.monitoring-body .health-stat,.monitoring-body .journal-stat{background:var(--tile)}
.monitoring-body button,.monitoring-body select{color:var(--text)}
.monitoring-body a{color:var(--blue)}
button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
@media(min-width:1000px){.homebrain-layout{grid-template-columns:minmax(0,1fr) 200px;column-gap:32px;align-items:start}
.overview-rail{grid-column:2;grid-row:1/span 2;position:sticky;top:155px;border-left:1px solid var(--edge);padding-left:13px}
#summaryTiles{grid-template-columns:1fr;gap:10px}#summaryTiles .tile .big{font-size:24px}
.exchange-feed{grid-column:1;grid-row:1}.command-bar{max-width:calc(100% - 232px)}}
@media(max-width:520px){.wrap{padding:0 10px 30px}.hb-header h1{font-size:17px}
.command-form{padding:7px;gap:7px;border-radius:16px}
.command-mic{width:45px;height:45px}.command-submit{padding:12px 13px}
#query{font-size:16px}.command-help{font-size:11px}
#summaryTiles{gap:2px;padding:3px}#summaryTiles .tile{padding:7px 3px}
#summaryTiles .tile .big{font-size:18px}#summaryTiles .tile div:last-child{font-size:10px}
.exchange{padding:12px 13px}.exchange-actions button{flex:1 1 auto}
.overview-note{margin-bottom:10px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}

</style>
</head>
<body><div class="wrap" id="homebrainApp">
<header class="hb-header">
<h1><span id="title"></span><small id="version"></small></h1>
<div class="connection-host">
<button id="connectionPill" type="button" aria-expanded="false" aria-controls="connectionPanel">● Connecting…</button>
<div id="connectionPanel" class="connection-panel" hidden>
<strong>Connection details</strong>
<section class="card row status-card"><span class="pill" id="mcp">MCP unknown</span><span class="pill"><span class="muted">MCP tools</span><strong id="tools">—</strong></span><span class="pill" id="ollama">Ollama unknown</span><span class="pill"><span class="muted">Model</span><strong id="model">—</strong></span><span class="pill"><span class="muted">Last route</span><strong id="lastRoute">—</strong></span><span class="pill"><span class="muted">Response</span><strong id="lastTime">—</strong></span></section>
<p class="connection-meta">Hub: <span id="statusHub">—</span> · Devices inspected: <span id="statusDevices">—</span></p>
<button id="checkConnection" class="secondary" type="button">Check connection</button>
<div hidden><span id="dashActiveRooms">—</span><span id="dashActiveRoomNames"></span></div>
</div>
</div>
</header>
<section class="command-bar" id="commandBar" aria-label="Ask HomeBrain">
<form id="commandForm" class="command-form">
<button id="speak" type="button" class="command-mic" aria-label="Start speaking" title="Tap to listen; hold to speak">🎤</button>
<textarea id="query" rows="2" placeholder="Ask or command…" maxlength="12000" aria-label="Ask HomeBrain"></textarea>
<button id="ask" type="submit" class="command-submit" disabled>Ask</button>
</form>
<div class="command-help"><span id="voiceStatus" role="status">Press / to focus · Enter to send · Shift+Enter for a new line</span><span>Voice input may use a browser speech service.</span></div>
<div class="model-tier-picker">
<label for="modelTier">Model</label>
<select id="modelTier" aria-label="AI model for this question">
<option value="auto">Auto · hybrid routing (may charge)</option>
<option value="free">Free · Gemma (default)</option>
<option value="paid">Paid · DeepSeek Pro (Ollama)</option>
<option value="claude">Paid · Claude (Anthropic API)</option>
</select>
<button class="secondary clear-context" id="resetContext" type="button" title="Start without prior context">New topic</button>
</div>
<div class="model-tier-note" id="modelTierNote" role="status">Free is the default. Paid uses Ollama account credits, with no additional HomeBrain budget. Claude bills your Anthropic API account separately.</div>
<div class="answer-options"><label class="muted"><input id="readAnswers" type="checkbox" style="width:auto"> Read answers aloud automatically</label><button class="secondary browser-shortcut" id="openBrowser" type="button">🌐 Open in browser</button></div>
</section>
<div class="homebrain-layout">
<aside class="overview-rail" aria-label="Current home overview">
<section class="card grid top-stats" id="summaryTiles">
<button class="tile secondary" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div></button>
<button class="tile secondary" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div></button>
<button class="tile secondary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div></button>
<button class="tile secondary" data-q="How many Hubitat devices were inspected, and is the inventory complete?"><div class="big" id="dashDevices">—</div><div>Devices inspected</div></button>
</section>
<p class="overview-note" id="overviewNote">Read-only snapshot · inventory status pending · no device commands</p>
</aside>
<main class="exchange-feed" id="exchangeFeed" aria-label="Questions and answers" aria-live="polite">
<p class="feed-empty" id="feedEmpty">What should the house do? <span>Your newest answer will appear here.</span></p>
<article class="exchange" id="answer" role="status" hidden></article>
</main>
</div>
<details id="monitoringPanels" class="monitoring-panels">
<summary>Hub Diagnostics, system checks and historical evidence</summary>
<div class="monitoring-body">
<section class="card" id="systemHealthCard">
<div><div class="health-heading"><strong>System check</strong><span class="health-status-chip health-neutral" id="healthAuditStatus">Not checked</span></div><div class="muted" id="healthAuditMeta">Scheduled morning check loading…</div></div>
<div class="health-grid">
<div class="health-stat"><div class="big" id="healthAuditAttention">—</div><div class="muted">Need attention</div></div>
<div class="health-stat"><div class="big" id="healthAuditNew">—</div><div class="muted">New since last check</div></div>
<div class="health-stat"><div class="big" id="healthAuditResolved">—</div><div class="muted">Resolved</div></div>
<div class="health-stat"><div class="big" id="healthAuditDevices">—</div><div class="muted">Devices checked</div></div>
</div>
<div class="health-actions"><button id="runHealthAudit">🩺 Run system check now</button><button class="secondary" id="sendPushoverReport">📲 Send report to Pushover</button></div>
<details class="health-details" id="healthAuditDetails"><summary>View system check details</summary><div id="healthAuditDetailsBody" class="muted">No audit has run yet.</div></details>
</section>
<section class="card" id="hubDiagnosticsCard">
<div class="health-heading"><strong>🩺 Hub Diagnostics — external recorder</strong><span class="health-status-chip health-neutral" id="diagState">Loading</span></div>
<div class="muted" id="diagSummary">Checking HomeBrain's locally recorded Hubitat health…</div>
<div class="health-grid">
<div class="health-stat"><div class="big" id="diagOS">—</div><div class="muted">Free OS memory (live probe)</div></div>
<div class="health-stat"><div class="big" id="diagJava">—</div><div class="muted">Free Java (native 5m sample)</div></div>
<div class="health-stat"><div class="big" id="diagHeap">—</div><div class="muted">Allocated Java heap used</div></div>
<div class="health-stat"><div class="big" id="diagCpuPercent">—</div><div class="muted">5m CPU load equivalent (%)</div></div>
<div class="health-stat"><div class="big" id="diagLatency">—</div><div class="muted">Last probe response</div></div>
</div>
<details class="health-details" id="diagDetails"><summary>View memory history &amp; connection incidents</summary>
<div class="muted">External observations are not proof of a reboot cause. Java and CPU load values are native five-minute samples, not 30-second measurements.
<div class="journal-small" id="diagCpuMethod">CPU load equivalent = 5-minute load average ÷ logical processor count × 100; not measured CPU utilisation.</div></div>

<details class="health-details" id="diagTimelineDetails" open>
<summary><strong>Unified incident timeline</strong> · memory, CPU, connection gaps and recorded startups</summary>
<div class="journal-small" id="diagTimelineMeta" role="status">Expand Hub Diagnostics to load synchronized observations from local storage.</div>
<div class="diag-timeline-legend">
<span><span class="swatch" style="background:#60a5fa"></span>OS memory (external 30s probes)</span>
<span><span class="swatch" style="background:#4ade80"></span>CPU load equivalent (native ~5m)</span>
<span><span class="swatch" style="background:#f59e0b"></span>Confirmed startup</span>
<span><span class="swatch" style="background:#f87171"></span>Connectivity loss</span>
</div>
<div class="diag-timeline-actions"><label for="diagTimelineLayout">Memory + CPU layout <select id="diagTimelineLayout" aria-label="Memory and CPU chart layout"><option value="combined" selected>Combined · shared plot</option><option value="split">Separate · aligned panels</option></select></label></div>
<svg id="diagTimelineChart" viewBox="0 0 860 330" role="img" tabindex="0" aria-label="Synchronized Hubitat memory, CPU load, confirmed startups and connectivity incidents; hover or use arrow keys to inspect saved observations"></svg>
<div class="journal-small" id="diagTimelineReadout" aria-live="polite">Hover, touch or use arrow keys to inspect source timestamps. No values are estimated between samples.</div>
<div class="diag-timeline-actions">
<button type="button" class="secondary" id="diagTimelineRefresh">↻ Refresh timeline</button>
<button type="button" class="secondary" id="diagReviewSelected" disabled>Investigate selected time</button>
<button type="button" class="secondary" id="diagAiSelected" disabled>AI investigate selected time</button>
<button type="button" class="secondary" id="diagTimelineJournal">Inspect Historical Journal</button>
<a id="diagTimelineEvidence" href="#" target="_blank" rel="noopener noreferrer">View source records (JSON)</a>
</div>
<div class="journal-small">Time alignment is for investigation, not causal attribution. Memory and connectivity times are external recorder observations; CPU readings are native five-minute samples shown at collector receipt times. Confirmed startups use offset-aware Hubitat systemStart times. Missing readings remain unknown.</div>
<strong>Observed points and incidents</strong>
<ul class="journal-gaps" id="diagTimelineEvents"><li class="muted">No incident timeline loaded.</li></ul>
<details class="health-details" id="diagReviewDetails" hidden>
<summary><strong>Incident investigation — read-only evidence</strong></summary>
<div class="journal-small" id="diagReviewStatus" role="status">Select an observed point to inspect locally archived evidence.</div>
<div class="diag-review-controls">
<label>Each side of focus <select id="diagReviewMinutes">
<option value="5">5 minutes</option>
<option value="15" selected>15 minutes</option>
<option value="30">30 minutes</option>
<option value="60">60 minutes</option>
</select></label>
<button type="button" class="secondary" id="diagReviewReload">↻ Recheck archive</button>
<button type="button" class="secondary" id="diagReviewAskAi">Investigate with HomeBrain AI</button>
<button type="button" class="secondary" id="diagReviewCopy">Copy evidence summary</button>
<a id="diagReviewJson" target="_blank" rel="noopener noreferrer" href="#">Source JSON</a>
</div>
<div class="journal-small">The review uses saved HomeBrain SQLite readings and journal records only. Native CPU readings are at collector reception time, not a verified five-minute measurement instant. App-log bodies are deliberately excluded. Proximity is not proof of a cause.</div>
<div id="diagReviewStats" class="diag-review-stat"></div>
<strong>Resource readings and recorded hub events</strong>
<ul class="journal-gaps diag-review-list" id="diagReviewRecorder"><li>Nothing loaded yet.</li></ul>
<strong>Historical Journal device observations</strong>
<div class="journal-small" id="diagReviewJournalStatus"></div>
<ul class="journal-gaps diag-review-list" id="diagReviewJournal"><li>Nothing loaded yet.</li></ul>
<strong>App-log receipt counts (no message bodies)</strong>
<ul class="journal-gaps diag-review-list" id="diagReviewAppCounts"><li>Nothing loaded yet.</li></ul>
<strong>Journal collection gaps</strong>
<ul class="journal-gaps diag-review-list" id="diagReviewGaps"><li>Nothing loaded yet.</li></ul>
</details>

</details>
<div class="row" style="margin-top:8px">
<label>View <select id="diagMetric" style="width:auto;margin:0;padding:7px;background:#333;color:white;border:1px solid #555">
<option value="free_os_mb">Live Free OS memory (MB)</option><option value="java_free_mb">Native Free Java (MB)</option>
<option value="java_allocated_heap_used_pct">Allocated heap used (%)</option>
<option value="native_load_pct">5-minute CPU load equivalent (%)</option>
<option value="native_load5">5-minute CPU load average (raw)</option><option value="latency_ms">HTTP response time (ms)</option>
</select></label>
<label>Range <select id="diagHours" style="width:auto;margin:0;padding:7px;background:#333;color:white;border:1px solid #555">
<option value="1">1 hour</option><option value="6" selected>6 hours</option><option value="24">24 hours</option>
<option value="72">3 days</option><option value="168">7 days</option><option value="720">30 days</option>
</select></label>
<button type="button" class="secondary" id="diagRefresh" style="width:auto;margin:0;padding:7px 12px">↻ Refresh</button>
</div>
<div id="diagChartCaption" class="muted" style="margin:10px 0 4px">Expand to load locally stored observations.</div>
<div id="diagChartStats" class="journal-small" role="status">Minimum — · Maximum — · Latest —</div>
<svg id="diagChart" viewBox="0 0 860 320" role="img" aria-label="Hubitat measurements with dotted guides. Hover, touch or use arrow keys to inspect recorded values." tabindex="0"></svg>
<div class="diag-chart-legend journal-small" aria-hidden="true"><span><span class="swatch"></span>Observed readings</span><span><span class="swatch guide"></span>Selected point</span><span><span class="swatch startup"></span>Confirmed startup</span></div>
<div id="diagPointReadout" class="journal-small" aria-live="polite">Hover, touch or use the left/right arrow keys on the graph to inspect exact readings.</div>
<strong>Confirmed hub startups (Hubitat systemStart)</strong>
<ul class="journal-gaps" id="diagReboots"><li class="muted">No confirmed startup events loaded.</li></ul>
<div class="journal-small">Orange chart markers are actual Hubitat systemStart records. A startup does not reveal why the hub restarted; older events unavailable from the hub cannot be reconstructed.</div>
<strong>Connectivity incidents</strong>
<ul class="journal-gaps" id="diagIncidents"><li class="muted">No incident history loaded.</li></ul>
<div class="journal-small">Incident detection requires two failed probes. Lost connectivity does not prove that Hubitat rebooted. For errors and hub events, inspect the Historical Journal and Hubitat's Hub Events.</div>
</details>
</section>
<section class="card" id="journalCard">
<div class="health-heading"><strong>Historical Journal</strong><span class="health-status-chip health-neutral" id="journalHealth">Loading</span></div>
<div class="muted" id="journalMeta">Checking persistent evidence collection…</div>
<div class="journal-streams">
<span class="journal-stream">Events: <strong id="journalEventsStream">—</strong></span>
<span class="journal-stream">App logs: <strong id="journalLogsStream">—</strong></span>
</div>
<div class="journal-grid">
<div class="journal-stat"><div class="big" id="journalEventRows">—</div><div class="muted">Events saved</div></div>
<div class="journal-stat"><div class="big" id="journalLogRows">—</div><div class="muted">App logs saved</div></div>
<div class="journal-stat"><div class="big" id="journalBytes">—</div><div class="muted">Disk usage</div></div>
<div class="journal-stat"><div class="big" id="journalGapCount">—</div><div class="muted">Recorded gaps</div></div>
</div>
<div class="journal-small" id="journalCoverage">Journal records are partial evidence, not verified continuous history.</div>
<div class="journal-actions"><button class="secondary" id="journalRefresh" type="button">↻ Refresh journal</button><span class="muted" id="journalUpdated"></span></div>
<details class="health-details" id="journalDetails"><summary>Recent events and collection details</summary>
<div class="journal-small" id="journalRetention"></div>
<div class="journal-small" id="journalAppLogs"></div>
<div class="journal-small" id="journalFirstLast"></div>
<strong>Recent device observations</strong>
<ul class="journal-events" id="journalRecentEvents"><li class="journal-small">Expand to load recent events.</li></ul>
<strong>Connection gaps</strong>
<ul class="journal-gaps" id="journalRecentGaps"><li class="journal-small">No gap details loaded.</li></ul>
</details>

<details class="health-details" id="journalBrowser">
<summary>Browse historical records</summary>
<div class="journal-browser-controls">
<label>Device ID<input id="journalBrowseDevice" type="text" inputmode="numeric" placeholder="e.g. 7805" maxlength="12"></label>
<label>Day (local time)<input id="journalBrowseDay" type="date"></label>
<label>From<input id="journalBrowseStart" type="time" value="00:00"></label>
<label>To<input id="journalBrowseEnd" type="time" value="23:59"></label>
<label>Event type<select id="journalBrowseAttribute"><option value="">All recorded attributes</option><option value="switch">Switch</option><option value="command-on">ON command</option><option value="command-off">OFF command</option><option value="command-setLevel">Set level command</option><option value="motion">Motion</option><option value="presence">Presence</option><option value="occupancy">Occupancy</option><option value="pushed">Button pushed</option></select></label>
</div>
<div class="journal-actions"><button id="journalBrowseSearch" type="button">Search records</button><button class="secondary" id="journalBrowseCopy" type="button">Copy API URL</button><button class="secondary" id="journalBrowsePrev" type="button" disabled>Previous</button><button class="secondary" id="journalBrowseNext" type="button" disabled>Next</button></div>
<div class="journal-small" id="journalBrowseStatus" role="status">Search by an exact device ID and local day. Results are archived observations, not proof of uninterrupted recording.</div>
<div class="journal-browser-table-wrap"><table class="journal-browser-table"><thead><tr><th>Recorded time</th><th>Event</th><th>Value</th><th>Source</th><th>Timestamp basis</th></tr></thead><tbody id="journalBrowseRows"></tbody></table></div>
<div class="journal-small">Up to 50 records per page, oldest first. Connected streams, timestamps and an empty result do not prove complete coverage. App-log message bodies are not displayed here.</div>
</details>
</section>
<p class="muted">Powered by Ollama Online native function calling and Hubitat MCP.</p>
</div></details>
</div>
<button id="micFab" class="mic-fab" aria-label="Speak" hidden>🎤</button>
<script>
const TITLE=__TITLE__,VERSION=__VERSION__;
const newSessionId=()=>globalThis.crypto?.randomUUID?.()||`hmcp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
let sessionId=newSessionId();
// Retire legacy browser-saved transcripts on upgrade; context now lives only in this open page.
try{localStorage.removeItem('hmcp_chats_v1');sessionStorage.removeItem('hmcp_session_id');
  for(let i=sessionStorage.length-1;i>=0;i--){const key=sessionStorage.key(i);
    if(key&&key.startsWith('hmcp_history_'))sessionStorage.removeItem(key)}}catch(error){}
document.getElementById('title').textContent=TITLE;document.getElementById('version').textContent='v'+VERSION;
const query=document.getElementById('query'),ask=document.getElementById('ask');
const feed=document.getElementById('exchangeFeed');
let answer=document.getElementById('answer'),activeTrace=[],currentQuestion='';
function syncCommandBar(){
  query.style.height='auto';query.style.height=Math.min(132,Math.max(44,query.scrollHeight))+'px';
  const ready=!!query.value.trim();ask.disabled=!ready;ask.classList.toggle('ready',ready);
}
function beginExchange(question){
  const empty=document.getElementById('feedEmpty');if(empty)empty.remove();
  if(answer&&!answer.hidden){
    answer.classList.add('older');answer.removeAttribute('id');
    answer.querySelectorAll('.action-controls button').forEach(button=>button.disabled=true);
    answer=document.createElement('article');answer.className='exchange';answer.id='answer';
    answer.setAttribute('role','status');feed.prepend(answer);
  }
  answer.hidden=false;answer.dataset.question=question;answer.replaceChildren();
  const asked=document.createElement('p');asked.className='exchange-question';
  asked.append('You asked: ');
  const name=document.createElement('strong');name.textContent=question;asked.appendChild(name);
  answer.appendChild(asked);
  const trace=document.createElement('ol');trace.className='work-trace';trace.setAttribute('aria-label','Observed work');
  answer.appendChild(trace);activeTrace=[];currentQuestion=question;
  const body=document.createElement('div');body.className='exchange-body';
  body.textContent='Starting request…';answer.appendChild(body);
  return answer;
}
function recordTrace(stage,elapsed){
  const value=String(stage||'').trim();if(!value||value==='Waiting for request')return;
  if(activeTrace.length&&activeTrace[activeTrace.length-1].stage===value)return;
  activeTrace.push({stage:value,elapsed:typeof elapsed==='number'&&Number.isFinite(elapsed)?elapsed:null});
  const timeline=answer.querySelector('.work-trace');if(!timeline)return;
  const li=document.createElement('li');li.textContent=value;
  if(typeof elapsed==='number'&&Number.isFinite(elapsed)){
    const time=document.createElement('small');time.textContent='observed '+elapsed.toFixed(1)+'s';li.appendChild(time);
  }
  timeline.appendChild(li);
}

const modelTier=document.getElementById('modelTier'),modelTierNote=document.getElementById('modelTierNote');
function describeModelTier(){const mode=modelTier.value;modelTierNote.textContent=mode==='free'?'Free: use the configured default model; never upgrade this request to paid.':mode==='paid'?'Paid: DeepSeek Pro only. No Gemma fallback or HomeBrain budget; Ollama account credits apply.':mode==='claude'?'Paid: Claude via the Anthropic API. Anthropic bills separately; no Gemma or DeepSeek fallback.':'Auto: opt-in to existing hybrid routing (may use Ollama paid credits).';}
modelTier.value='free';modelTier.onchange=describeModelTier;describeModelTier();
query.value='';try{localStorage.removeItem('hmcp_last_query')}catch(error){}
const apiPath=path=>`${location.pathname.replace(/\/?$/,'/')}${path}`;
function healthClass(status){return status==='healthy'?'health-ok':status==='critical'?'health-critical':status==='attention'?'health-warn':'health-neutral'}
function healthTime(value){if(!value)return'never';const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString([], {dateStyle:'medium',timeStyle:'short'})}
function appendBrokenState(li,detail){const match=String(detail||'').match(/^(.*?)(\*?BROKEN\*?)(.*)$/i);if(!match){li.appendChild(document.createTextNode(detail));return}if(match[1])li.appendChild(document.createTextNode(match[1]));const state=document.createElement('span');state.className='health-state-critical';state.textContent='BROKEN';li.appendChild(state);if(match[3])li.appendChild(document.createTextNode(match[3]))}
function renderHealthIssue(li,item){const title=String(item&&item.title||'Issue'),detail=String(item&&item.detail||''),occurrences=item&&item.count>1?' · '+item.count+' occurrences':'';const deviceUnavailable='Device unavailable:',lowBattery='Low battery:',automationBroken='Automation broken:';if(title.toLowerCase().startsWith(automationBroken.toLowerCase())){li.appendChild(document.createTextNode(title));if(detail){li.appendChild(document.createTextNode(' — '));appendBrokenState(li,detail)}if(occurrences)li.appendChild(document.createTextNode(occurrences));return}let prefix='',target='',tone='';if(title.toLowerCase().startsWith(deviceUnavailable.toLowerCase())){prefix=deviceUnavailable;target=title.slice(deviceUnavailable.length).trim();tone='critical'}else if(title.toLowerCase().startsWith(lowBattery.toLowerCase())){prefix=lowBattery;target=title.slice(lowBattery.length).trim();tone='warning'}if(!target){li.textContent=title+(detail?' — '+detail:'')+occurrences;return}const label=document.createElement('span');label.textContent=prefix+' ';const name=document.createElement('span');name.className='health-target-'+tone;name.textContent=target;li.append(label,name);if(detail){const sep=document.createElement('span');sep.textContent=' — ';li.appendChild(sep);if(tone==='critical'){const state=document.createElement('span');state.className='health-state-critical';state.textContent=detail;li.appendChild(state)}else{const match=detail.match(/^([^ (]+)/);if(match){const state=document.createElement('span');state.className='health-state-warning';state.textContent=match[1];li.appendChild(state);const rest=document.createElement('span');rest.textContent=detail.slice(match[1].length);li.appendChild(rest)}else{li.appendChild(document.createTextNode(detail))}}}if(occurrences)li.appendChild(document.createTextNode(occurrences))}
function renderHealthAudit(payload){const audit=payload&&payload.latest?payload.latest:null;const schedule=payload&&payload.schedule?payload.schedule:{};const statusNode=document.getElementById('healthAuditStatus'),meta=document.getElementById('healthAuditMeta'),details=document.getElementById('healthAuditDetailsBody');statusNode.className='health-status-chip '+healthClass(audit&&audit.status);statusNode.textContent=audit&&audit.status?String(audit.status).replace(/^./,c=>c.toUpperCase()):'Not checked';document.getElementById('healthAuditAttention').textContent=audit&&audit.attention_count!==undefined?audit.attention_count:0;document.getElementById('healthAuditNew').textContent=audit&&audit.new_count!==undefined?audit.new_count:0;document.getElementById('healthAuditResolved').textContent=audit&&audit.resolved_count!==undefined?audit.resolved_count:0;document.getElementById('healthAuditDevices').textContent=audit&&audit.sections&&audit.sections.devices&&audit.sections.devices.total!==undefined?audit.sections.devices.total:'—';let scheduleText=schedule.enabled?('Daily '+(schedule.time||'')+(schedule.next_run?' · next '+healthTime(schedule.next_run):'')):'Morning check disabled';if(schedule.last_notification_error)scheduleText+=' · Pushover delivery failed';meta.textContent=audit?('Last checked '+healthTime(audit.checked_at)+' · '+scheduleText):scheduleText;details.textContent='';if(!audit){details.textContent='No stored system check yet. Use “Run system check now” or wait for the scheduled morning audit.';return}const issues=Array.isArray(audit.issues)?audit.issues:[];const current=document.createElement('div');const heading=document.createElement('strong');heading.textContent=issues.length?('Findings ('+issues.length+')'):'No current findings';current.appendChild(heading);if(issues.length){const list=document.createElement('ul');list.className='health-list';issues.forEach(item=>{const li=document.createElement('li');renderHealthIssue(li,item);list.appendChild(li)});current.appendChild(list)}details.appendChild(current);const newIssues=Array.isArray(audit.new_issues)?audit.new_issues:[];if(newIssues.length){const h=document.createElement('p');h.className='health-new';h.textContent='New since previous check ('+newIssues.length+')';details.appendChild(h)}const resolved=Array.isArray(audit.resolved_issues)?audit.resolved_issues:[];if(resolved.length){const h=document.createElement('p');h.className='health-resolved';h.textContent='Resolved since previous check: '+resolved.map(item=>item.title||'issue').join(', ');details.appendChild(h)}}
function renderHealthAuditV2(payload){
const audit=payload&&payload.latest?payload.latest:null,schedule=payload&&payload.schedule?payload.schedule:{};
const statusNode=document.getElementById('healthAuditStatus'),meta=document.getElementById('healthAuditMeta'),details=document.getElementById('healthAuditDetailsBody');
statusNode.className='health-status-chip '+healthClass(audit&&audit.status);statusNode.textContent=audit&&audit.status?String(audit.status).replace(/^./,c=>c.toUpperCase()):'Not checked';
document.getElementById('healthAuditAttention').textContent=audit&&audit.attention_count!==undefined?audit.attention_count:0;
document.getElementById('healthAuditNew').textContent=audit&&audit.new_count!==undefined?audit.new_count:0;
document.getElementById('healthAuditResolved').textContent=audit&&audit.resolved_count!==undefined?audit.resolved_count:0;
document.getElementById('healthAuditDevices').textContent=audit&&audit.sections&&audit.sections.devices&&audit.sections.devices.total!==undefined?audit.sections.devices.total:'—';
let scheduleText=schedule.enabled?('Daily '+(schedule.time||'')+(schedule.next_run?' · next '+healthTime(schedule.next_run):'')):'Morning check disabled';
if(schedule.last_notification_error)scheduleText+=' · Pushover delivery failed';
meta.textContent=audit?('Last checked '+healthTime(audit.checked_at)+' · '+scheduleText):scheduleText;details.textContent='';
if(!audit){details.textContent='No stored system check yet. Use “Run system check now” or wait for the scheduled morning audit.';return}
const hierarchy=audit.health_hierarchy||audit.sections&&audit.sections.summary||{};
const overview=document.createElement('div');overview.className='health-domain-grid';
['hub','devices','automations','logs'].forEach(domain=>{const item=hierarchy[domain];if(!item)return;const card=document.createElement('div');card.className='health-domain '+healthClass(item.status);const title=document.createElement('strong');title.textContent=(item.icon||'')+' '+(item.label||domain);const count=document.createElement('span');count.textContent=item.attention_count?item.attention_count+' need attention':'Healthy';card.append(title,count);overview.appendChild(card)});
if(overview.children.length)details.appendChild(overview);
const deviceSection=audit.sections&&audit.sections.devices;if(deviceSection){const activity=document.createElement('p');const pending=deviceSection.stale_candidate_count?' · '+deviceSection.stale_candidate_count+' awaiting stale confirmation':'';activity.textContent='Device activity: '+(deviceSection.offline_count||0)+' explicitly offline · '+(deviceSection.suspicious_stale_count||0)+' suspiciously stale · '+(deviceSection.long_term_stale_count||0)+' long-term stale'+pending+' · '+(deviceSection.passive_quiet_count||0)+' passive/quiet · '+(deviceSection.never_reported_count||0)+' never reported';details.appendChild(activity)}
if(audit.change_tracking_state==='baseline-reset'){const note=document.createElement('p');note.className='health-neutral';note.textContent='Change tracking baseline reset after upgrade; new/resolved comparisons resume on the next check.';details.appendChild(note)}
const issues=Array.isArray(audit.issues)?audit.issues:[],labels={hub:'Hub',devices:'Devices',automations:'Automations',logs:'Logs'};
['hub','devices','automations','logs'].forEach(domain=>{const rows=issues.filter(item=>(item.domain||'hub')===domain);if(!rows.length)return;const section=document.createElement('div');section.className='health-section';const heading=document.createElement('strong');heading.textContent=labels[domain]+' ('+rows.length+')';const list=document.createElement('ul');list.className='health-list';rows.forEach(item=>{const li=document.createElement('li');renderHealthIssue(li,item);list.appendChild(li)});section.append(heading,list);details.appendChild(section)});
if(!issues.length){const empty=document.createElement('strong');empty.textContent='No current findings';details.appendChild(empty)}
const newIssues=Array.isArray(audit.new_issues)?audit.new_issues:[];if(newIssues.length){const node=document.createElement('p');node.className='health-new';node.textContent='New since previous check ('+newIssues.length+')';details.appendChild(node)}
const resolved=Array.isArray(audit.resolved_issues)?audit.resolved_issues:[];if(resolved.length){const node=document.createElement('p');node.className='health-resolved';node.textContent='Resolved since previous check: '+resolved.map(item=>item.title||'issue').join(', ');details.appendChild(node)}
}
async function loadHealthAudit(){try{renderHealthAuditV2(await jsonResponse(await fetch(apiPath('api/health-audit'))))}catch(error){console.warn('Health audit unavailable',error);document.getElementById('healthAuditMeta').textContent='System check unavailable: '+error.message}}
function journalTime(value){if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?'—':date.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})}
function journalSize(bytes){if(typeof bytes!=='number'||bytes<0)return '—';return bytes<1024?bytes+' B':bytes<1048576?(bytes/1024).toFixed(1)+' KB':(bytes/1048576).toFixed(2)+' MB'}
function renderJournal(payload){
const data=payload&&typeof payload==='object'?payload:{},enabled=!!data.enabled,started=!!data.started,connected=data.connected||{},eventsOK=!!connected.events,logsRequired=!!data.capture_logs,logsOK=!logsRequired||!!connected.logs,hasError=!!data.error||!!data.storage_unavailable,operational=enabled&&started&&eventsOK&&logsOK&&!hasError;
const health=document.getElementById('journalHealth');health.className='health-status-chip '+(hasError?'health-critical':!enabled?'health-neutral':operational?'health-ok':'health-warn');health.textContent=hasError?'Attention':!enabled?'Disabled':!started?'Not started':operational?'Connected':'Reconnecting';
const states=(id,state)=>{const n=document.getElementById(id);n.className=state==='Connected'?'health-ok':state==='Disabled'?'health-neutral':'health-warn';n.textContent=state};
states('journalEventsStream',!enabled?'Disabled':eventsOK?'Connected':'Disconnected');
states('journalLogsStream',!enabled||!logsRequired?'Disabled':connected.logs?'Connected':'Disconnected');
document.getElementById('journalEventRows').textContent=data.event_rows??'—';document.getElementById('journalLogRows').textContent=data.app_log_rows??'—';document.getElementById('journalBytes').textContent=journalSize(data.db_bytes);document.getElementById('journalGapCount').textContent=data.gaps??'—';
const base=hasError?(data.error||'Journal storage unavailable'):!enabled?'Enable in the add-on Configuration tab.':!started?'Journal has not started.':operational?'Collecting selected live Hubitat observations.':'Collector is reconnecting. Capture may have gaps.';
document.getElementById('journalMeta').textContent=base;
document.getElementById('journalCoverage').textContent='Latest saved event: '+journalTime(data.last_persisted_device_event)+' · Dropped this run: '+(data.dropped_this_run??'—')+' · Open gaps: '+(data.open_gaps??'—')+'. An empty history does not prove inactivity.';
document.getElementById('journalRetention').textContent='Retained up to '+(data.retention_days??'—')+' days / '+(data.max_rows??'—')+' rows · Rows stored: '+(data.rows??'—')+' · Queue: '+(data.queued??'—')+'.';
document.getElementById('journalFirstLast').textContent='Oldest retained reception: '+journalTime(data.first_received)+' · Newest: '+journalTime(data.last_retained||data.last_persisted_device_event)+'.';
const ids=Array.isArray(data.tracked_app_ids)?data.tracked_app_ids:[],counts=data.captured_app_log_counts||{},appText=!logsRequired?'App-log capture disabled.':data.capture_all_app_logs?'All apps · '+(counts['*']??data.app_log_rows??0)+' stored · '+(data.log_retention_hours??48)+'h retention':ids.length?ids.map(id=>'App '+id+': '+(counts[id]??0)+' stored').join(' · '):'No app IDs selected.';
document.getElementById('journalAppLogs').textContent=appText+(logsRequired?' (Zero rows may simply mean no log messages were emitted.)':'');
const gapList=document.getElementById('journalRecentGaps');gapList.replaceChildren();const gapRows=Array.isArray(data.recent_gaps)?data.recent_gaps:[];if(!gapRows.length){const li=document.createElement('li');li.textContent='No recorded gaps.';gapList.append(li)}else gapRows.forEach(row=>{const li=document.createElement('li');const ongoing=row.ended_at?' → '+journalTime(row.ended_at):' → ongoing';li.textContent=(row.stream||'stream')+': '+journalTime(row.started_at)+ongoing+' · '+(row.reason||'unspecified');gapList.append(li)});
document.getElementById('journalUpdated').textContent='Checked '+new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
}
async function loadJournalRecent(){const list=document.getElementById('journalRecentEvents');if(!document.getElementById('journalDetails').open)return;try{const response=await fetch(apiPath('api/evidence-journal/recent?limit=12'));if(!response.ok){const error=await jsonResponse(response);throw new Error(error.detail||'Not available')}const data=await jsonResponse(response),rows=Array.isArray(data.events)?data.events:[];list.replaceChildren();if(!rows.length){const li=document.createElement('li');li.textContent='No captured device events yet. Empty archive does not prove inactivity.';list.append(li);return}rows.forEach(row=>{const li=document.createElement('li'),name=document.createElement('strong'),detail=document.createElement('div');name.textContent=(row.display_name||'Device '+(row.device_id||'?'))+' · '+(row.attribute||'?')+' '+(row.value||'');detail.className='journal-small';detail.textContent=journalTime(row.observed_at)+' · '+(row.timestamp_basis==='source'?'Source timestamp':'Collector received')+' · ID '+(row.device_id||'?');li.append(name,detail);list.append(li)})}catch(error){list.replaceChildren();const li=document.createElement('li');li.textContent='Recent events unavailable: '+error.message;list.append(li)}}
async function loadJournal(){try{const response=await fetch(apiPath('api/evidence-journal/status'));if(!response.ok)throw new Error('HTTP '+response.status);renderJournal(await jsonResponse(response))}catch(error){const chip=document.getElementById('journalHealth');chip.className='health-status-chip health-critical';chip.textContent='Unavailable';document.getElementById('journalMeta').textContent='Cannot retrieve journal status: '+error.message}}
function pill(id,ok,text){const node=document.getElementById(id);node.textContent=text;node.className='pill '+(ok?'ok':'error')}
async function jsonResponse(response){const raw=await response.text();try{return JSON.parse(raw)}catch(error){throw new Error(`HTTP ${response.status}: ${raw||'empty response'}`)}}
let activeSpeech=null,nativeSpeechActive=false,nativeSpeechTimer=null,nativeStopPromise=null;const preferNativeTTS=/Android/i.test(navigator.userAgent)&&(/\bwv\b/i.test(navigator.userAgent)||/Home Assistant/i.test(navigator.userAgent));
function browserTargetUrl(){const candidates=[];try{if(window.top&&window.top!==window&&window.top.location&&window.top.location.href)candidates.push(window.top.location.href)}catch(error){}if(document.referrer)candidates.push(document.referrer);candidates.push(location.href);for(const value of candidates){try{const url=new URL(value,location.href);if(url.protocol!=='http:'&&url.protocol!=='https:')continue;url.searchParams.delete('external_auth');url.hash='';if(!url.pathname.includes('/api/hassio_ingress/'))return url.toString()}catch(error){}}try{const fallback=new URL(location.href);fallback.searchParams.delete('external_auth');fallback.hash='';return fallback.toString()}catch(error){return location.href}}
function openHomeBrainInBrowser(){const target=browserTargetUrl();if(/Android/i.test(navigator.userAgent)&&preferNativeTTS){try{const url=new URL(target);const scheme=url.protocol.slice(0,-1);const withoutScheme=url.toString().replace(/^[a-z]+:\/\//i,'').replace(/#.*$/,'');location.href='intent://'+withoutScheme+'#Intent;scheme='+scheme+';action=android.intent.action.VIEW;end';return}catch(error){console.warn('Android browser intent unavailable',error)}}window.open(target,'_blank','noopener,noreferrer')}
const openBrowser=document.getElementById('openBrowser');if(openBrowser){if(preferNativeTTS)openBrowser.classList.add('visible');openBrowser.onclick=openHomeBrainInBrowser}
function resetAudioButtons(){document.querySelectorAll('.audio-button').forEach(button=>{button.textContent='🔊 Read answer';button.title=''})}
async function stopNativeAudio(){if(!nativeSpeechActive)return;nativeSpeechActive=false;if(nativeSpeechTimer){clearTimeout(nativeSpeechTimer);nativeSpeechTimer=null}try{await fetch(apiPath('api/tts/stop'),{method:'POST'})}catch(error){console.warn('Home Assistant TTS stop unavailable',error)}resetAudioButtons()}
function stopAudio(){if('speechSynthesis'in globalThis)speechSynthesis.cancel();activeSpeech=null;if(nativeSpeechActive)nativeStopPromise=stopNativeAudio();else resetAudioButtons()}
async function speakViaHomeAssistant(spoken,button=null){if(nativeStopPromise){try{await nativeStopPromise}finally{nativeStopPromise=null}}const response=await fetch(apiPath('api/tts'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:spoken})});const data=await jsonResponse(response);if(!response.ok||!data.success)throw new Error(data.detail||'Home Assistant TTS is unavailable');nativeSpeechActive=true;if(button){button.textContent='■ Stop phone audio';button.title='Home Assistant companion-app TTS'}const estimatedMs=Math.min(30000,Math.max(3000,spoken.length*55));nativeSpeechTimer=setTimeout(()=>{nativeSpeechActive=false;nativeSpeechTimer=null;resetAudioButtons()},estimatedMs);return true}
async function speakAnswer(value,button=null){const spoken=speechText(value);if(!spoken)return false;stopAudio();let browserStarted=false,fallbackStarted=false;const fallback=async()=>{if(fallbackStarted||browserStarted)return false;fallbackStarted=true;activeSpeech=null;try{return await speakViaHomeAssistant(spoken,button)}catch(error){console.warn('Speech playback unavailable',error);if(button){const reason=String(error&&error.message||'TTS unavailable').replace(/^Home Assistant TTS delivery failed:\s*/i,'').trim();button.textContent='⚠ '+(reason.length>52?reason.slice(0,49)+'…':reason);button.title=reason;setTimeout(()=>{if(!activeSpeech&&!nativeSpeechActive)resetAudioButtons()},5000)}return false}};if(preferNativeTTS)return fallback();if(!('speechSynthesis'in globalThis)||!('SpeechSynthesisUtterance'in globalThis))return fallback();const utterance=new SpeechSynthesisUtterance(spoken);utterance.lang='en-GB';utterance.rate=.95;utterance.pitch=1;const voices=speechSynthesis.getVoices();utterance.voice=voices.find(voice=>voice.lang?.toLowerCase().startsWith('en-gb')&&voice.localService)||voices.find(voice=>voice.lang?.toLowerCase().startsWith('en'))||null;activeSpeech=utterance;utterance.onstart=()=>{browserStarted=true;if(button)button.textContent='■ Stop audio'};utterance.onend=()=>{if(activeSpeech===utterance){activeSpeech=null;resetAudioButtons()}};utterance.onerror=()=>{if(activeSpeech===utterance)activeSpeech=null;if(!browserStarted)void fallback();else resetAudioButtons()};speechSynthesis.speak(utterance);setTimeout(()=>{if(activeSpeech===utterance&&!browserStarted){speechSynthesis.cancel();activeSpeech=null;void fallback()}},1500);return true}
let readAnswers=localStorage.getItem('hmcp_read_answers')==='true';document.getElementById('readAnswers').checked=readAnswers;document.getElementById('readAnswers').onchange=event=>{readAnswers=event.target.checked;localStorage.setItem('hmcp_read_answers',String(readAnswers));if(!readAnswers)stopAudio()};
function legacyCopy(value){const area=document.createElement('textarea');area.value=value;area.setAttribute('readonly','');area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.focus();area.select();area.setSelectionRange(0,area.value.length);let ok=false;try{ok=Boolean(document.execCommand&&document.execCommand('copy'))}catch(error){ok=false}area.remove();return ok}
async function copyText(value,button,label){let ok=legacyCopy(value);if(!ok&&globalThis.isSecureContext&&navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(value);ok=true}catch(error){ok=false}}button.textContent=ok?'Copied':'Copy blocked — select text';button.className=`copy-button ${ok?'copy-ok':'copy-fail'}`;setTimeout(()=>{button.textContent=label;button.className='secondary copy-button'+(label==='Copy technical'?' technical-copy':'')},1800)}
function normalizeAnswerMarkup(value){return String(value??'').replace(/\$\s*\\rightarrow\s*\$/g,'→').replace(/\$\s*\\leftarrow\s*\$/g,'←').replace(/\$\s*\\to\s*\$/g,'→')}
function appendInline(parent,value){normalizeAnswerMarkup(value).split(/(\*\*[^*]+\*\*|\(Paused\)|\*BROKEN\*)/gi).filter(Boolean).forEach(part=>{if(part.startsWith('**')&&part.endsWith('**')){const strong=document.createElement('strong');strong.textContent=part.slice(2,-2);parent.appendChild(strong)}else if(/^\(Paused\)$/i.test(part)||/^\*BROKEN\*$/i.test(part)){const warning=document.createElement('span');warning.className='inline-critical';warning.textContent=/paused/i.test(part)?'(Paused)':'BROKEN';parent.appendChild(warning)}else parent.appendChild(document.createTextNode(part.replace(/`([^`]+)`/g,'$1')))})}
function statusName(value){const match=String(value).match(/^\[(ACTIVE|DISABLED|PAUSED|BROKEN|UNKNOWN)\]\s*/i);return match?match[1].toLowerCase():null}
function appendStatusLine(parent,value){const status=statusName(value);let text=String(value);if(status){text=text.replace(/^\[(?:ACTIVE|DISABLED|PAUSED|BROKEN|UNKNOWN)\]\s*/i,'');const label=document.createElement('span');label.className='status-label status-'+status;label.textContent=status.toUpperCase();parent.appendChild(label)}appendInline(parent,text)}
function headingStatus(value){const normalized=String(value).replace(/:$/,'').trim().toLowerCase();return ['active','disabled','paused','broken','unknown'].find(status=>normalized===status||normalized===status+' rules'||normalized===status+' apps')||null}
function markdownTableCells(value){const text=String(value||'').trim();if(!text.startsWith('|')||!text.endsWith('|'))return null;return text.slice(1,-1).split('|').map(cell=>cell.trim())}
function isMarkdownTableDivider(value,count){const cells=markdownTableCells(value);return !!cells&&cells.length===count&&cells.every(cell=>/^:?-{3,}:?$/.test(cell))}
function renderMarkdownTable(lines,start,headers){const wrap=document.createElement('div');wrap.className='answer-table-wrap';wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scrollable results table');wrap.tabIndex=0;const table=document.createElement('table');table.className='answer-markdown-table';const thead=document.createElement('thead'),heading=document.createElement('tr');headers.forEach(value=>{const th=document.createElement('th');th.scope='col';appendInline(th,value);heading.appendChild(th)});thead.appendChild(heading);table.appendChild(thead);const body=document.createElement('tbody');let i=start+2;while(i<lines.length){const cells=markdownTableCells(lines[i]);if(!cells||cells.length!==headers.length)break;const row=document.createElement('tr');cells.forEach(value=>{const td=document.createElement('td');appendInline(td,value);row.appendChild(td)});body.appendChild(row);i++}table.appendChild(body);wrap.appendChild(table);return {element:wrap,nextIndex:i}}
function renderMessage(value){const root=document.createElement('div');root.className='answer-text';let list=null;const lines=String(value).replace(/\r/g,'').split('\n');for(let i=0;i<lines.length;i++){const line=lines[i].trim();if(!line){list=null;continue}const cells=markdownTableCells(line);if(cells&&cells.length>=2&&i+1<lines.length&&isMarkdownTableDivider(lines[i+1],cells.length)){const rendered=renderMarkdownTable(lines,i,cells);root.appendChild(rendered.element);i=rendered.nextIndex-1;list=null;continue}const bullet=line.match(/^[-*]\s+(.+)$/),numbered=line.match(/^\d+[.)]\s+(.+)$/);if(bullet||numbered){const type=numbered?'ol':'ul';if(!list||list.tagName.toLowerCase()!==type){list=document.createElement(type);root.appendChild(list)}const item=document.createElement('li');appendStatusLine(item,(bullet||numbered)[1]);list.appendChild(item);continue}list=null;if(/^([-*_]\s*){3,}$/.test(line)){root.appendChild(document.createElement('hr'));continue}const heading=line.match(/^#{1,6}\s+(.+)$/);const node=document.createElement(heading?'h3':'p');const headingText=heading?heading[1]:line;const state=headingStatus(headingText);if(state)node.classList.add('heading-'+state);appendStatusLine(node,headingText);root.appendChild(node)}return root}
const AUTOMATION_STATUSES=['active','disabled','paused','broken','unknown'];
function cleanAutomationName(value){return String(value||'').replace(/\s*\(Paused\)\s*/gi,' ').replace(/\s*\*BROKEN\*\s*/gi,' ').replace(/\s{2,}/g,' ').trim()}
function renderAutomationItems(data){const root=document.createElement('div');root.className='automation-view';const items=(Array.isArray(data.automation_items)?data.automation_items:[]).filter(item=>AUTOMATION_STATUSES.includes(String(item.status||'').toLowerCase()));const toolbar=document.createElement('div');toolbar.className='automation-toolbar';const search=document.createElement('input');search.type='search';search.placeholder='Search apps and rules…';search.setAttribute('aria-label','Search automation items');const expand=document.createElement('button');expand.className='secondary';expand.textContent='Expand all';const collapse=document.createElement('button');collapse.className='secondary';collapse.textContent='Collapse all';toolbar.append(search,expand,collapse);root.appendChild(toolbar);const filters=document.createElement('div');filters.className='automation-filters';let selected='all';['all',...AUTOMATION_STATUSES].forEach(status=>{const button=document.createElement('button');button.className='automation-filter'+(status==='all'?' selected':'');button.dataset.status=status;button.textContent=status==='all'?'All':status[0].toUpperCase()+status.slice(1);button.onclick=()=>{selected=status;filters.querySelectorAll('button').forEach(node=>node.classList.toggle('selected',node===button));apply()};filters.appendChild(button)});root.appendChild(filters);const sections=new Map();AUTOMATION_STATUSES.forEach(status=>{const matching=items.filter(item=>String(item.status).toLowerCase()===status);if(!matching.length)return;const details=document.createElement('details');details.className=`automation-section automation-section-${status}`;details.dataset.status=status;details.open=['paused','broken','unknown'].includes(status);const summary=document.createElement('summary');summary.textContent=`${status[0].toUpperCase()+status.slice(1)} (${matching.length})`;const list=document.createElement('ul');matching.sort((a,b)=>String(a.name).localeCompare(String(b.name))).forEach(item=>{const row=document.createElement('li');row.dataset.search=`${item.name||''} ${item.type||''}`.toLowerCase();const label=document.createElement('span');label.className=`status-label status-${status}`;label.textContent=status.toUpperCase();const name=document.createElement('span');name.textContent=cleanAutomationName(item.name);const kind=document.createElement('span');kind.className='automation-kind';kind.textContent=item.type==='rule'?'Rule Machine':'App';row.append(label,name,kind);list.appendChild(row)});details.append(summary,list);root.appendChild(details);sections.set(status,details)});const empty=document.createElement('div');empty.className='automation-empty';empty.textContent='No automation items match this filter.';empty.hidden=true;root.appendChild(empty);function apply(){const term=search.value.trim().toLowerCase();let visibleSections=0;sections.forEach((details,status)=>{let visibleRows=0;details.querySelectorAll('li').forEach(row=>{const show=(!term||row.dataset.search.includes(term))&&(selected==='all'||selected===status);row.hidden=!show;if(show)visibleRows+=1});details.hidden=visibleRows===0;if(visibleRows){visibleSections+=1;details.querySelector('summary').textContent=`${status[0].toUpperCase()+status.slice(1)} (${visibleRows})`}});empty.hidden=visibleSections!==0}search.oninput=apply;expand.onclick=()=>sections.forEach(details=>{if(!details.hidden)details.open=true});collapse.onclick=()=>sections.forEach(details=>details.open=false);return root}
function speechText(value){return normalizeAnswerMarkup(value).replace(/```[\s\S]*?```/g,' ').replace(/\[(ACTIVE|DISABLED|PAUSED|BROKEN|UNKNOWN)\]/gi,'$1').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/\s*\((?:IDs?|device IDs?)\s*:\s*[^)]+\)/gi,'').replace(/\b(?:IDs?|device IDs?)\s*[:#]\s*[\d,\s]+/gi,'').replace(/([a-z])([A-Z])/g,'$1 $2').replace(/\bRTT\b/gi,'response time').replace(/\bCPU\b/g,'C P U').replace(/&/g,' and ').replace(/\s+\/\s+/g,' or ').replace(/→/g,' to ').replace(/←/g,' from ').replace(/(\d+(?:\.\d+)?)\s*%/g,'$1 percent').replace(/:\s*\n/g,'.\n').replace(/^\s*#{1,6}\s*/gm,'').replace(/^\s*[-*+]\s+/gm,'').replace(/>/g,' over ').replace(/=/g,' ').replace(/(\d+(?:\.\d+)?)h\b/gi,'$1 hours').replace(/[*_`]/g,'').replace(/\n+/g,'. ').replace(/\s+/g,' ').replace(/\s+\./g,'.').replace(/\.{2,}/g,'.').trim()}
// No chat tabs, saved transcripts or browser-persistent conversation history.
// Keep only recent in-page context for natural follow-up questions.
// Request ownership must exist independently of the retired saved-chat UI.
// Both Ask and New topic use these variables to cancel superseded calls safely.
let activeRequest=null,requestSequence=0;
let suggestedAction=null,conversationHistory=[];
function resetConversation(){
  if(activeRequest){activeRequest.abort();activeRequest=null;requestSequence++}
  stopAudio();suggestedAction=null;conversationHistory=[];sessionId=newSessionId();
  query.value='';syncCommandBar();
  feed.replaceChildren();
  answer=document.createElement('article');answer.className='exchange';answer.id='answer';answer.hidden=true;
  answer.setAttribute('role','status');feed.appendChild(answer);
  const empty=document.createElement('p');empty.className='feed-empty';empty.id='feedEmpty';
  empty.textContent='What should the house do? ';const sub=document.createElement('span');
  sub.textContent='Your newest answer will appear here.';empty.appendChild(sub);feed.prepend(empty);
  activeTrace=[];currentQuestion='';
  document.getElementById('lastRoute').textContent='—';
  document.getElementById('lastTime').textContent='—';query.focus();
}
document.getElementById('resetContext').onclick=resetConversation;

function firmwareUpdateAvailable(data,rawMessage){if(data?.update_available===true)return true;const evidence=Array.isArray(data?.evidence)?data.evidence:[];if(evidence.some(item=>item?.update_available===true||item?.data?.update_available===true||item?.result?.update_available===true))return true;return /\bfirmware update is available\b/i.test(rawMessage)||/\bhub firmware\s+\S+\s+is installed and\s+\S+\s+is available\b/i.test(rawMessage)}
function choicePrompt(question,choice){const original=String(question||'').trim();const directAction=original.match(/^\s*(?:please\s+)?(turn\s+on|turn\s+off|toggle)\b/i)?.[1]||original.match(/^\s*(?:can|could|would|will)\s+you\s+(?:please\s+)?(turn\s+on|turn\s+off|toggle)\b/i)?.[1]||'';if(directAction)return `${directAction} ${choice}`;const attribute=original.match(/\b(temperature|humidity|battery|power)\b/i)?.[1]||'';if(attribute)return `What is the ${choice} ${attribute}?`;return original?`${original} Device clarification: use exactly ${choice}.`:choice}
function showAnswer(data){answer.replaceChildren();const meta=document.createElement('div');meta.className='answer-meta';const outcome=data.outcome_presentation;if(outcome&&['positive','warning','neutral','critical'].includes(outcome.tone)&&typeof outcome.label==='string'&&outcome.label){const outcomeBadge=document.createElement('span');outcomeBadge.className=`badge outcome-badge outcome-${outcome.tone}`;outcomeBadge.textContent=outcome.label;meta.appendChild(outcomeBadge)}[data.route,data.model_tier_requested&&data.model_tier_requested!=='auto'?'Selected '+data.model_tier_requested:null,data.model,data.elapsed_ms===undefined?null:`${(data.elapsed_ms/1000).toFixed(1)}s`].filter(Boolean).forEach(value=>{const badge=document.createElement('span');badge.className='badge';badge.textContent=value;meta.appendChild(badge)});if(meta.children.length)answer.appendChild(meta);if(data.model_usage){const parts=[];const names=data.model_usage.models||{};for(const [name,n] of Object.entries(names)){if(n>0){const short=/deepseek/i.test(name)?'DeepSeek Pro':/claude/i.test(name)?'Claude':/gemma/i.test(name)?'Gemma':name;parts.push(short+': '+n)}}if(parts.length){const usage=document.createElement('span');usage.className='badge';usage.textContent=parts.join(' · ');meta.appendChild(usage);if(!meta.isConnected)answer.appendChild(meta)}}const rawMessage=data.message||data.detail||'No response';const text=renderMessage(rawMessage);answer.appendChild(text);if(data.route==='automation-status'&&Array.isArray(data.automation_items)&&data.automation_items.length)answer.appendChild(renderAutomationItems(data));if(Array.isArray(data.choices)){const originalQuestion=query.value.trim();data.choices.forEach(choice=>{const option=document.createElement('button');option.className='confirm';option.textContent=choice;option.onclick=()=>submit(choicePrompt(originalQuestion,choice));answer.appendChild(option)})}suggestedAction=firmwareUpdateAvailable(data,rawMessage)?'firmware-update':null;if(suggestedAction==='firmware-update'){const install=document.createElement('button');install.className='confirm';install.textContent='Update hub firmware';install.onclick=()=>submit('Install the available Hubitat firmware update');answer.appendChild(install)}if(data.confirmation_required===true){const confirm=document.createElement('button');confirm.className='confirm';confirm.textContent='Confirm action';confirm.onclick=()=>submit('confirm');answer.appendChild(confirm)}const audioButton=document.createElement('button');audioButton.className='secondary copy-button audio-button';audioButton.textContent='🔊 Read answer';audioButton.onclick=()=>{if(activeSpeech||nativeSpeechActive)stopAudio();else void speakAnswer(rawMessage,audioButton)};answer.appendChild(audioButton);const copy=document.createElement('button');copy.className='secondary copy-button';copy.textContent='Copy answer';copy.onclick=()=>copyText(rawMessage,copy,'Copy answer');answer.appendChild(copy);const details=document.createElement('details');details.className='technical';const summary=document.createElement('summary');summary.textContent='Technical details';const technical=JSON.stringify(data,null,2);const technicalCopy=document.createElement('button');technicalCopy.className='secondary copy-button technical-copy';technicalCopy.textContent='Copy technical';technicalCopy.onclick=event=>{event.preventDefault();copyText(technical,technicalCopy,'Copy technical')};const pre=document.createElement('pre');pre.textContent=technical;details.append(summary,technicalCopy,pre);answer.appendChild(details);document.getElementById('lastRoute').textContent=data.route||'—';document.getElementById('lastTime').textContent=data.elapsed_ms===undefined?'—':`${(data.elapsed_ms/1000).toFixed(1)}s`;if(readAnswers&&speechText(rawMessage).length<1500)void speakAnswer(rawMessage,audioButton)}
async function status(){try{const data=await jsonResponse(await fetch(apiPath('api/status')));pill('mcp',data.mcp?.online,data.mcp?.online?'MCP online':`MCP offline · ${data.mcp?.error||'unavailable'}`);pill('ollama',data.ollama?.configured,data.ollama?.configured?'Ollama ready':'Ollama API key required');const paidOption=modelTier.querySelector('option[value="paid"]');if(paidOption)paidOption.disabled=data.paid_routing?.enabled===false;const claudeOption=modelTier.querySelector('option[value="claude"]');if(claudeOption)claudeOption.disabled=data.claude?.configured!==true;if((modelTier.value==='paid'&&paidOption?.disabled)||(modelTier.value==='claude'&&claudeOption?.disabled))modelTier.value='free';describeModelTier();document.getElementById('tools').textContent=data.mcp?.tools??'—';document.getElementById('model').textContent=data.ollama?.model||'—'}catch(error){pill('mcp',false,'Status error · '+error.message)}try{const dash=await jsonResponse(await fetch(apiPath('api/dashboard')));document.getElementById('dashLights').textContent=dash.lights_on??'—';document.getElementById('dashMotion').textContent=dash.motion_active??'—';document.getElementById('dashBatteries').textContent=dash.low_batteries??'—';const active=dash.active_rooms||[];const loaded=[dash.lights_on,dash.motion_active,dash.low_batteries].some(value=>value!=null);document.getElementById('dashActiveRooms').textContent=loaded?active.length:'—';document.getElementById('dashActiveRoomNames').textContent=loaded?(active.length?active.map(room=>room.name).join(', '):'No motion or lights on'):'Loading live states…'}catch(error){console.warn('Dashboard unavailable',error)}loadHealthAudit();loadJournal()}
const MAX_CHAT_PROMPT_CHARS=12000;
function askApiErrorMessage(response,data,length){
  if(response.status===422&&Array.isArray(data?.detail)){
    const error=data.detail.find(item=>Array.isArray(item?.loc)&&
      item.loc.some(field=>field==='prompt'||field==='query')&&
      item.type==='string_too_long');
    if(error){
      const maximum=Number(error.ctx?.max_length)||MAX_CHAT_PROMPT_CHARS;
      return 'Question exceeds the '+maximum.toLocaleString()+'-character limit ('+
        length.toLocaleString()+' characters). Shorten the question and retry.';
    }
    return 'Request validation failed (HTTP 422). Check the question and selected model.';
  }
  return typeof data?.detail==='string'?data.detail:'HTTP '+response.status;
}
async function submit(text){
  const incidentAI=text&&typeof text==='object'?text.incidentAI||null:null;
  text=(incidentAI?text.text:text||query.value).trim();if(!text)return;
  if(text.length>MAX_CHAT_PROMPT_CHARS){
    query.value=text;
    showAnswer({success:false,route:'validation-error',
      message:'Question exceeds the '+MAX_CHAT_PROMPT_CHARS.toLocaleString()+
        '-character limit ('+text.length.toLocaleString()+
        ' characters). Shorten the question and retry; nothing was submitted.'});
    return;
  }
  const normalized=text.toLowerCase().replace(/[.!]/g,'').trim();
  if(suggestedAction==='firmware-update'&&['yes','yes please','proceed','do it'].includes(normalized))text='Install the available Hubitat firmware update';
  suggestedAction=null;stopAudio();query.value=text;
  if(activeRequest)activeRequest.abort();
  const controller=new AbortController();activeRequest=controller;
  const sequence=++requestSequence,requestId=newSessionId(),requestSessionId=sessionId;
  const selectedTier=modelTier.value;
  const history=conversationHistory.slice(-8);
  answer.classList.add('busy');answer.textContent='Starting request… Ask another question to replace this request.';
  const progressTimer=setInterval(async()=>{
    if(sequence!==requestSequence||controller.signal.aborted)return;
    try{
      const response=await fetch(apiPath('api/request-progress')+'?session_id='+encodeURIComponent(requestSessionId)+'&request_id='+encodeURIComponent(requestId),{signal:controller.signal});
      if(!response.ok)return;
      const progress=await response.json();
      if(sequence===requestSequence&&activeRequest===controller&&!progress.completed&&progress.stage&&progress.stage!=='Waiting for request')
        answer.textContent=progress.stage+' · '+(progress.elapsed_seconds||0).toFixed(0)+'s elapsed';
    }catch(error){}
  },1500);
  try{
    // Preserve the original Ask request contract and network-error policy.
    // The alternative incident endpoint is invoked only by an explicit click.
    const response=await (async()=>{
      const networkFailure=error=>{
        if(error?.name==='AbortError')throw error;
        // The backend may already have submitted a write
        // before its HTTP response was lost. Never automatically retry.
        const failure=new Error(String(error?.message||'Network connection lost'));
        failure.name='HomeBrainNetworkError';
        throw failure;
      };
      if(incidentAI){
        return await fetch(apiPath('api/hub-diagnostics/investigate'),{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({
            at:incidentAI.at,window_minutes:incidentAI.window_minutes,
            session_id:requestSessionId,request_id:requestId,model_tier:selectedTier,
          }),signal:controller.signal,
        }).catch(networkFailure);
      }
      const response=await fetch(apiPath('api/ask'),{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({query:text,history,session_id:requestSessionId,request_id:requestId,model_tier:selectedTier}),
        signal:controller.signal,
      }).catch(networkFailure);
      return response;
    })();
    const data=await jsonResponse(response);if(!response.ok)throw new Error(askApiErrorMessage(response,data,text.length));
    if(sequence===requestSequence&&requestSessionId===sessionId){
      const reply=String(data.message||data.detail||'');
      conversationHistory.push({role:'user',content:text},{role:'assistant',content:reply});
      conversationHistory=conversationHistory.slice(-8);
      showAnswer(data);
    }
  }catch(error){
    if(error.name!=='AbortError'&&sequence===requestSequence&&requestSessionId===sessionId){
      if(error.name==='HomeBrainNetworkError'){
        // This is a classification of the user's requested action, not a
        // claim about what the disconnected backend actually completed.
        // Only strict no-write investigations take this less alarming path.
        // Ambiguous or potentially mutating prompts retain the existing
        // write-outcome-unknown warning; never retry them automatically.
        const strictReadOnly = /\bread[\s-]*only\b/i.test(text)
          && /\b(?:do\s+not|don't|without)\s+(?:modify|change|edit|write|mutate|update|delete|create|disable|enable|control|turn|set)\b/i.test(text);
        if(strictReadOnly){
          showAnswer({
            success:false,route:'network-outcome-unknown',
            status_verification:'read-outcome-unknown',
            message:'Connection to HomeBrain was lost before the read-only answer arrived. '+
              'The investigation may have completed on the backend, but its result '+
              'was not received. No Hubitat write was requested. Check HomeBrain '+
              'add-on logs using Request ID: '+requestId+
              '. Once connectivity is restored, a new read-only investigation '+
              'may be submitted; this does not establish any historical cause. '+
              'Browser error: '+String(error.message||'connection lost').slice(0,160)
          });
        }else{
          showAnswer({
            success:false,route:'network-outcome-unknown',
            status_verification:'write-outcome-unknown',
          message:'Connection to HomeBrain was lost before the answer arrived. '+
            'The result of any requested Hubitat write is UNKNOWN: it may '+
            'have completed, failed or been cancelled. Do NOT submit the '+
            'same rule or device command again yet. First open Hubitat '+
            'directly and check the exact Rule Machine rule name and current '+
            'state; inspect HomeBrain add-on logs if needed. Request ID: '+
            requestId+'. Browser error: '+String(error.message||'connection lost').slice(0,160)
        });
        }
      }else{
        showAnswer({success:false,route:'error',message:'Request failed: '+error.message});
      }
    }
  }finally{
    clearInterval(progressTimer);
    if(sequence===requestSequence&&requestSessionId===sessionId){
      activeRequest=null;answer.classList.remove('busy');status();
    }
  }
}
ask.onclick=()=>submit();query.onkeydown=event=>{if(event.key==='Enter')submit()};document.querySelectorAll('[data-q]').forEach(button=>button.onclick=()=>submit(button.dataset.q));
document.getElementById('runHealthAudit').onclick=async()=>{const button=document.getElementById('runHealthAudit');button.disabled=true;button.textContent='🩺 Checking…';try{const data=await jsonResponse(await fetch(apiPath('api/health-audit/run'),{method:'POST'}));renderHealthAuditV2(data);document.getElementById('healthAuditDetails').open=true}catch(error){document.getElementById('healthAuditMeta').textContent='System check failed: '+error.message}finally{button.disabled=false;button.textContent='🩺 Run system check now'}};
document.getElementById('sendPushoverReport').onclick=async()=>{const button=document.getElementById('sendPushoverReport'),meta=document.getElementById('healthAuditMeta');button.disabled=true;button.textContent='📲 Sending report…';try{const response=await fetch(apiPath('api/pushover/report'),{method:'POST'}),data=await jsonResponse(response);if(!response.ok||!data.success)throw new Error(data.detail||'Pushover rejected the report');meta.textContent=data.message||'Latest System Check report sent to Pushover.';button.textContent='✅ Report sent'}catch(error){meta.textContent='Pushover report failed: '+error.message;button.textContent='❌ Send failed'}finally{setTimeout(()=>{button.disabled=false;button.textContent='📲 Send report to Pushover'},1800)}};
let activeRecognition=null;function startVoice(){stopAudio();if(activeRecognition){activeRecognition.stop();return}const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){answer.textContent='Speech recognition is unavailable in this browser.';return}const recognition=new Recognition();activeRecognition=recognition;recognition.lang='en-GB';const fab=document.getElementById('micFab');fab.classList.add('listening');fab.textContent='■';recognition.onresult=event=>submit(event.results[0][0].transcript);recognition.onerror=event=>{answer.textContent='Speech recognition error: '+event.error};recognition.onend=()=>{activeRecognition=null;fab.classList.remove('listening');fab.textContent='🎤'};recognition.start()}
document.getElementById('speak').onclick=startVoice;document.getElementById('micFab').onclick=startVoice;

let journalBrowseOffset=0;
function journalBrowseParameters(){
  const id=document.getElementById('journalBrowseDevice').value.trim();
  const day=document.getElementById('journalBrowseDay').value;
  const from=document.getElementById('journalBrowseStart').value;
  const to=document.getElementById('journalBrowseEnd').value;
  if(!/^\d{1,12}$/.test(id)||!/^\d{4}-\d{2}-\d{2}$/.test(day)
      ||!/^\d{2}:\d{2}$/.test(from)||!/^\d{2}:\d{2}$/.test(to)){
    throw new Error('Enter a numeric device ID, date and valid From/To times.');
  }
  // Clock inputs are interpreted in the browser's local timezone.
  const begin=new Date(day+'T'+from+':00');
  const end=new Date(day+'T'+to+':00');
  if(Number.isNaN(begin.getTime())||Number.isNaN(end.getTime())||end<begin){
    throw new Error('The end time must not precede the start time.');
  }
  // An inclusive minute should include event milliseconds at 07:30:59.
  end.setMinutes(end.getMinutes()+1);
  end.setMilliseconds(end.getMilliseconds()-1);
  const params=new URLSearchParams({
    device_id:id,since:begin.toISOString(),until:end.toISOString(),
    limit:'50',offset:String(journalBrowseOffset)
  });
  const attribute=document.getElementById('journalBrowseAttribute').value;
  if(attribute)params.set('attribute',attribute);
  return params;
}
async function browseJournal(reset=false){
  const status=document.getElementById('journalBrowseStatus');
  const body=document.getElementById('journalBrowseRows');
  if(reset)journalBrowseOffset=0;
  let params;
  try{params=journalBrowseParameters()}catch(error){status.textContent=error.message;return}
  const previous=document.getElementById('journalBrowsePrev'),next=document.getElementById('journalBrowseNext'),search=document.getElementById('journalBrowseSearch');
  previous.disabled=next.disabled=search.disabled=true;status.textContent='Reading archived records…';
  try{
    const response=await fetch(apiPath('api/evidence-journal/events?'+params.toString()));
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error(data.detail||'Journal query unavailable (HTTP '+response.status+')');
    const records=Array.isArray(data.events)?data.events:[];
    body.replaceChildren();
    for(const record of records){
      if(record.stream!=='events')continue;
      const tr=document.createElement('tr');
      for(const val of [
        journalTime(record.observed_at),
        String(record.attribute||'—'),
        String(record.value||'—'),
        String(record.source||'—'),
        record.timestamp_basis==='source'?'Source event time':'Collector reception'
      ]){const td=document.createElement('td');td.textContent=val;tr.append(td)}
      body.append(tr);
    }
    const hasMore=!!data.has_more;
    previous.disabled=journalBrowseOffset===0;
    next.disabled=!hasMore;
    const gapCount=Array.isArray(data.gaps)?data.gaps.length:0;
    status.textContent='Records '+(records.length?journalBrowseOffset+1:0)+'–'+(journalBrowseOffset+records.length)
      +' · '+(hasMore?'More pages available':'No further matching records')
      +' · '+gapCount+' recorded gap(s) overlap this window. Historical coverage is never verified as complete.';
    if(!records.length)status.textContent+=' No records does not mean no activity.';
  }catch(error){body.replaceChildren();status.textContent='Query failed: '+error.message;previous.disabled=next.disabled=true}
  finally{search.disabled=false}
}
const journalToday=new Date();document.getElementById('journalBrowseDay').value=[journalToday.getFullYear(),String(journalToday.getMonth()+1).padStart(2,'0'),String(journalToday.getDate()).padStart(2,'0')].join('-');
document.getElementById('journalBrowseSearch').onclick=()=>void browseJournal(true);
document.getElementById('journalBrowsePrev').onclick=()=>{journalBrowseOffset=Math.max(0,journalBrowseOffset-50);void browseJournal()};
document.getElementById('journalBrowseNext').onclick=()=>{journalBrowseOffset+=50;void browseJournal()};
document.getElementById('journalBrowseCopy').onclick=async()=>{
  const button=document.getElementById('journalBrowseCopy');
  const status=document.getElementById('journalBrowseStatus');
  try{
    const params=journalBrowseParameters();
    const url=new URL(apiPath('api/evidence-journal/events?'+params.toString()),location.href);
    // Do not invent a hostname or strip a Home Assistant ingress prefix.
    await copyText(url.href,button,'Copy API URL');
  }catch(error){status.textContent='Cannot build API URL: '+error.message}
};

document.getElementById('journalDetails').addEventListener('toggle',event=>{if(event.target.open)void loadJournalRecent()});
document.getElementById('journalRefresh').onclick=async()=>{const b=document.getElementById('journalRefresh');b.disabled=true;try{await loadJournal();await loadJournalRecent()}finally{b.disabled=false}};

// Unified timeline reads only saved external diagnostics; no additional Hubitat requests.
// Presentation-only axis helpers: ticks and grid lines never imply sampled readings.
function diagNiceChartScale(low,high,targetIntervals){
 const desired=Math.max(0.000001,(high-low)/Math.max(1,targetIntervals));
 const power=Math.pow(10,Math.floor(Math.log10(desired)));
 const factor=[1,2,2.5,5,10].find(value=>value*power>=desired)||10;
 const step=factor*power;
 const min=Math.max(0,Math.floor(low/step+1e-9)*step);
 const max=Math.max(min+step,Math.ceil(high/step-1e-9)*step);
 return {min,max,step,intervals:Math.round((max-min)/step)};
}
function diagChartYGrid(layer,left,right,top,bottom,scale,metric,color){
 for(let i=0;i<=scale.intervals;i++){
  const value=scale.min+scale.step*i;
  const y=bottom-i/scale.intervals*(bottom-top);
  layer.append(diagChartSvgNode('line',{x1:left,x2:right,y1:y,y2:y,
   stroke:'#53637a','stroke-width':0.85,'stroke-opacity':0.78,'stroke-dasharray':'2 5'}));
  layer.append(diagChartSvgNode('text',{x:left-8,y:y+4,fill:color,
   'text-anchor':'end','font-size':11},diagMetricValue(value,metric)));
 }
}
function diagChartYGridRight(layer,right,top,bottom,scale,metric,color){
 // Separate scale on the right; tick labels are not readings.
 for(let i=0;i<=scale.intervals;i++){
  const value=scale.min+scale.step*i,y=bottom-i/scale.intervals*(bottom-top);
  layer.append(diagChartSvgNode('line',{x1:right,x2:right+5,y1:y,y2:y,stroke:color,'stroke-opacity':0.7}));
  layer.append(diagChartSvgNode('text',{x:right+8,y:y+4,fill:color,'text-anchor':'start','font-size':11},
   diagMetricValue(value,metric)));
 }
}
function diagChartTimeGrid(svg,layer,first,last,left,right,top,bottom,labelY){
 // Count labels using rendered pixels, not SVG viewBox units; avoid crowding on phones.
 const renderedWidth=svg.getBoundingClientRect().width||right-left;
 const sameDay=new Date(first).toDateString()===new Date(last).toDateString();
 const intervals=Math.max(2,Math.min(12,Math.floor(renderedWidth/(sameDay?68:112))));
 for(let i=0;i<=intervals;i++){
  const stamp=first+(last-first)*i/intervals,x=left+(right-left)*i/intervals;
  const date=new Date(stamp);
  const label=sameDay?
   date.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false}):
   date.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false});
  layer.append(diagChartSvgNode('line',{x1:x,x2:x,y1:top,y2:bottom,
   stroke:'#394758','stroke-width':0.8,'stroke-opacity':0.85,'stroke-dasharray':'2 5'}));
  layer.append(diagChartSvgNode('text',{x,y:labelY,fill:'#b4c1d3','font-size':11,
   'text-anchor':i===0?'start':i===intervals?'end':'middle'},label));
 }
}
const timelinePlot={left:75,right:825,memTop:30,memBottom:142,cpuTop:188,cpuBottom:292,width:860};
let timelineRows={memory:[],cpu:[]},timelineFocusTimes=[],timelineActiveTime=null;
let timelineData=null,timelineRequestSeq=0,timelineLastRead=0;
function timelineStamp(value){const stamp=Date.parse(value);return Number.isFinite(stamp)?stamp:null}
function timelineRange(data){const first=timelineStamp(data.range_start),last=timelineStamp(data.range_end);
 return first!==null&&last!==null&&last>first?[first,last]:null}
function timelineX(t,first,last){return timelinePlot.left+(t-first)/(last-first)*(timelinePlot.right-timelinePlot.left)}
function timelineMetricPoints(data,key,kind){
 const metric=data.metrics&&data.metrics[key]||{},raw=Array.isArray(metric.samples)?metric.samples:[];
 const seen=new Set();
 return raw.filter(row=>{
  const t=row&&timelineStamp(row.recorded_at),v=row&&row[key];
  if(t===null||typeof v!=='number'||!Number.isFinite(v)||!row.reachable)return false;
  if(kind==='native'){const label=String(row.native_sample_label||'');if(!label||seen.has(label))return false;seen.add(label)}
  return true;
 }).sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at));
}
function timelineNear(rows,t){
 if(!rows.length)return null;
 let a=0,b=rows.length-1;
 while(a<b){const m=Math.floor((a+b)/2);if(Date.parse(rows[m].recorded_at)<t)a=m+1;else b=m}
 return a&&Math.abs(Date.parse(rows[a-1].recorded_at)-t)<Math.abs(Date.parse(rows[a].recorded_at)-t)?rows[a-1]:rows[a];
}
function timelineSelectAt(t){
 if(!timelineData)return;
 const range=timelineRange(timelineData);if(!range||!Number.isFinite(t))return;
 const [first,last]=range;
 const x=timelineX(Math.max(first,Math.min(last,t)),first,last);
 const cross=document.getElementById('diagTimelineCursor');
 if(cross){cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.setAttribute('visibility','visible')}
 const parts=['Selected '+diagDate(new Date(t).toISOString())];
 const selections=[['memory','free_os_mb','OS memory','external probe'],
                   ['cpu','native_load_pct','5m CPU load equivalent','native report at collector receipt']];
 for(const [group,key,label,basis] of selections){
  const row=timelineNear(timelineRows[group],t);
  const dot=document.getElementById('diagTimeline'+(group==='memory'?'MemoryDot':'CpuDot'));
  const guide=document.getElementById('diagTimeline'+(group==='memory'?'MemoryGuide':'CpuGuide'));
  const near=row&&Math.abs(timelineX(Date.parse(row.recorded_at),first,last)-x)<=18;
  if(dot)dot.setAttribute('visibility',near?'visible':'hidden');
  if(guide)guide.setAttribute('visibility',near?'visible':'hidden');
  if(near){
   const ygroup=group==='memory'?'memY':'cpuY';
   const px=timelineX(Date.parse(row.recorded_at),first,last),py=timelineData[ygroup](row[key]);
   if(dot){dot.setAttribute('cx',px);dot.setAttribute('cy',py);}
   if(guide){guide.setAttribute('x2',px);guide.setAttribute('y1',py);guide.setAttribute('y2',py);}
   parts.push(label+' '+diagMetricValue(row[key],key)+' at '+diagDate(row.recorded_at)+
      ' ('+basis+(group==='cpu'?', native label '+String(row.native_sample_label||'unavailable'):'')+')');
  }else parts.push(label+': no nearby displayed reading (not zero)');
 }
 document.getElementById('diagTimelineReadout').textContent=parts.join(' · ')+
   ' · These observations do not establish a cause.';
 timelineActiveTime=t;
 document.getElementById('diagReviewSelected').disabled=false;
 document.getElementById('diagAiSelected').disabled=false;
}
function drawIncidentTimeline(data){
 const svg=document.getElementById('diagTimelineChart');svg.replaceChildren();
 timelineData=null;timelineRows={memory:[],cpu:[]};timelineFocusTimes=[];
 document.getElementById('diagReviewSelected').disabled=true;
 document.getElementById('diagAiSelected').disabled=true;
 const r=timelineRange(data),eventsNode=document.getElementById('diagTimelineEvents');
 eventsNode.replaceChildren();
 if(!r){
  svg.append(diagChartSvgNode('text',{x:75,y:110,fill:'#cbd5e1','font-size':16},'No recorded interval available'));
  document.getElementById('diagTimelineReadout').textContent='No timeline data recorded yet. Unknown periods are not zero.';
  return;
 }
 const [first,last]=r,span=last-first;
 const combined=document.getElementById('diagTimelineLayout').value==='combined';
 const mem=timelineMetricPoints(data,'free_os_mb','external');
 const cpu=timelineMetricPoints(data,'native_load_pct','native');
 const memMeta=data.metrics&&data.metrics.free_os_mb||{},cpuMeta=data.metrics&&data.metrics.native_load_pct||{};
 timelineRows={memory:mem,cpu:cpu};
 const minMem=mem.length?mem.reduce((a,b)=>b.free_os_mb<a.free_os_mb?b:a):null;
 const maxCpu=cpu.length?cpu.reduce((a,b)=>b.native_load_pct>a.native_load_pct?b:a):null;
 document.getElementById('diagTimelineMeta').textContent=
  String(memMeta.observed_metric_points??mem.length)+' OS memory observations · '+
  String(cpuMeta.observed_metric_points??cpu.length)+' distinct 5m CPU readings · '+
  (Array.isArray(data.reboots)?data.reboots.length:0)+' confirmed startup records · '+
  (Array.isArray(data.incidents)?data.incidents.length:0)+' recorded connectivity episodes'+
  ((memMeta.downsampled||cpuMeta.downsampled)?' · Display reduced using actual minimum/maximum and gap boundaries':'')+
  ' · Partial historical coverage; time proximity is not proof of cause.';
 const memoryLow=Math.max(0,(minMem?minMem.free_os_mb:0)-(mem.length?Math.max(20,(Math.max(...mem.map(p=>p.free_os_mb))-minMem.free_os_mb)*0.12):20));
 const memoryHigh=mem.length?Math.max(...mem.map(p=>p.free_os_mb))+30:100;
 const cpuHigh=Math.max(10,maxCpu?maxCpu.native_load_pct*1.15:10);
 const memScale=diagNiceChartScale(memoryLow,memoryHigh,combined?6:8);
 const cpuScale=diagNiceChartScale(0,cpuHigh,combined?6:8);
 const memTop=combined?30:timelinePlot.memTop,memBottom=combined?timelinePlot.cpuBottom:timelinePlot.memBottom;
 const cpuTop=combined?30:timelinePlot.cpuTop,cpuBottom=timelinePlot.cpuBottom;
 const memY=value=>memBottom-(value-memScale.min)/(memScale.max-memScale.min)*(memBottom-memTop);
 const cpuY=value=>cpuBottom-(value-cpuScale.min)/(cpuScale.max-cpuScale.min)*(cpuBottom-cpuTop);
 // Store only the two measured y transforms, never fabricated sample values.
 // The helper is discarded on each refresh before new data becomes visible.
 const graphData={...data,memY,cpuY};timelineData=graphData;
 diagChartTimeGrid(svg,svg,first,last,timelinePlot.left,timelinePlot.right,
  memTop,timelinePlot.cpuBottom,319);
 diagChartYGrid(svg,timelinePlot.left,timelinePlot.right,
  memTop,memBottom,memScale,'free_os_mb','#93c5fd');
 if(combined){
  diagChartYGridRight(svg,timelinePlot.right,cpuTop,cpuBottom,cpuScale,'native_load_pct','#86efac');
  svg.append(diagChartSvgNode('text',{x:timelinePlot.left,y:15,fill:'#cbd5e1','font-size':12},
   'OS memory (left · MB) + 5m CPU load equivalent (right · %)'));
 }else{
  diagChartYGrid(svg,timelinePlot.left,timelinePlot.right,
   cpuTop,cpuBottom,cpuScale,'native_load_pct','#86efac');
  svg.append(diagChartSvgNode('text',{x:timelinePlot.left,y:15,fill:'#93c5fd','font-size':13},
   'OS memory · MB (external probe; independent scale)'));
  svg.append(diagChartSvgNode('text',{x:timelinePlot.left,y:174,fill:'#86efac','font-size':13},
   '5m CPU load equivalent · % (native source; independent scale)'));
 }
 const incidents=(Array.isArray(data.incidents)?data.incidents:[]).filter(e=>e.kind==='hub-unreachable');
 for(const incident of incidents){
  const start=timelineStamp(incident.started_at),end=incident.recovered_at?timelineStamp(incident.recovered_at):last;
  if(start===null||end===null||end<first||start>last)continue;
  const left=timelineX(Math.max(first,start),first,last),right=timelineX(Math.min(last,end),first,last);
  const shade=diagChartSvgNode('rect',{x:left,y:20,width:Math.max(1.5,right-left),height:timelinePlot.cpuBottom-20,
    fill:'#ef4444','fill-opacity':0.11,stroke:'#ef4444','stroke-opacity':0.5,'stroke-width':0.75});
  shade.append(diagChartSvgNode('title',{},'External connectivity loss: '+diagDate(incident.started_at)+
    ' · '+(incident.recovered_at?'recovered '+diagDate(incident.recovered_at):'no recovery recorded')+
    ' · not proof of a reboot'));
  svg.append(shade);
 }
 const drawSeries=(rows,key,kind,color,fn,meta)=>{
  let path='',prev=null,segment=null;
  for(const row of rows){
   const t=Date.parse(row.recorded_at);
   const currSeg=Number.isInteger(row.diag_segment)?row.diag_segment:null;
   const gap=prev!==null&&((currSeg!==null&&segment!==null&&currSeg!==segment)||
      (!meta.downsampled&&t-prev>(kind==='native'?900000:Math.max(120000,(Number(data.probe_seconds)||30)*3000))));
   path+=(path&&!gap?' L':' M')+timelineX(t,first,last).toFixed(2)+' '+fn(row[key]).toFixed(2);
   prev=t;segment=currSeg;
  }
  if(path)svg.append(diagChartSvgNode('path',{d:path.trim(),fill:'none',stroke:color,
    'stroke-width':2.1,'stroke-linejoin':'round','stroke-linecap':'round'}));
  if(rows.length<=55)for(const row of rows){
   const dot=diagChartSvgNode('circle',{cx:timelineX(Date.parse(row.recorded_at),first,last),
    cy:fn(row[key]),r:2.4,fill:color});
   dot.append(diagChartSvgNode('title',{},diagDate(row.recorded_at)+' · '+diagMetricValue(row[key],key)+
     (kind==='native'?' · native label '+String(row.native_sample_label||'unknown'):' · external probe')));
   svg.append(dot);
  }
 };
 drawSeries(mem,'free_os_mb','external','#60a5fa',memY,memMeta);
 drawSeries(cpu,'native_load_pct','native','#4ade80',cpuY,cpuMeta);
 const events=[];
 for(const rec of (Array.isArray(data.reboots)?data.reboots:[])){
  const t=timelineStamp(rec.occurred_at);if(t===null||t<first||t>last)continue;
  const x=timelineX(t,first,last);
  const marker=diagChartSvgNode('line',{x1:x,x2:x,y1:20,y2:timelinePlot.cpuBottom,
     stroke:'#f59e0b','stroke-width':1.8,'stroke-dasharray':'4 4'});
  marker.append(diagChartSvgNode('title',{},'Confirmed Hubitat systemStart at '+diagDate(rec.occurred_at)+
    (rec.firmware?' · firmware '+rec.firmware:'')+' · cause unverified'));
  svg.append(marker);
  events.push({t,kind:'Confirmed startup',detail:'Hub Events systemStart'+
    (rec.firmware?' · firmware '+rec.firmware:'')+' · cause not established'});
 }
 for(const inc of incidents){
  const start=timelineStamp(inc.started_at),recovered=timelineStamp(inc.recovered_at);
  if(start!==null&&start>=first&&start<=last)events.push({t:start,kind:'Connectivity loss detected',
     detail:'External recorder · two failed probes · not a confirmed reboot'});
  if(recovered!==null&&recovered>=first&&recovered<=last)events.push({t:recovered,kind:'Connectivity recovered',
     detail:'External recorder · successful probe · cause not established'});
 }
 if(minMem)events.push({t:Date.parse(minMem.recorded_at),kind:'Lowest observed OS memory',
   detail:diagMetricValue(minMem.free_os_mb,'free_os_mb')+' · external probe (not a diagnosis)'});
 if(maxCpu)events.push({t:Date.parse(maxCpu.recorded_at),kind:'Highest observed 5m CPU load',
   detail:diagMetricValue(maxCpu.native_load_pct,'native_load_pct')+' · native source '+String(maxCpu.native_sample_label||'unknown')+
      ' · derived load, not measured CPU utilisation'});
 for(const [row,key,fn,color] of [[minMem,'free_os_mb',memY,'#60a5fa'],[maxCpu,'native_load_pct',cpuY,'#4ade80']]){
  if(!row)continue;
  const dot=diagChartSvgNode('circle',{cx:timelineX(Date.parse(row.recorded_at),first,last),
     cy:fn(row[key]),r:4.6,stroke:'#101114','stroke-width':1.6,fill:color});
  dot.append(diagChartSvgNode('title',{},diagDate(row.recorded_at)+' · real observed extremum '+diagMetricValue(row[key],key)));
  svg.append(dot);
 }
 svg.append(diagChartSvgNode('line',{id:'diagTimelineMemoryGuide',x1:timelinePlot.left,x2:timelinePlot.left,y1:0,y2:0,
   stroke:'#93c5fd','stroke-width':1.2,'stroke-dasharray':'2 5',visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('line',{id:'diagTimelineCpuGuide',x1:timelinePlot.left,x2:timelinePlot.left,y1:0,y2:0,
   stroke:'#86efac','stroke-width':1.2,'stroke-dasharray':'2 5',visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('line',{id:'diagTimelineCursor',x1:0,x2:0,y1:20,y2:timelinePlot.cpuBottom,
   stroke:'#e2e8f0','stroke-width':1.4,'stroke-dasharray':'2 4',visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('circle',{id:'diagTimelineMemoryDot',cx:0,cy:0,r:5,fill:'#60a5fa',stroke:'#fff','stroke-width':1,
   visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('circle',{id:'diagTimelineCpuDot',cx:0,cy:0,r:5,fill:'#4ade80',stroke:'#fff','stroke-width':1,
   visibility:'hidden','pointer-events':'none'}));
 events.sort((a,b)=>b.t-a.t);
 const visible=events.slice(0,35);
 if(!visible.length){const li=document.createElement('li');li.textContent='No observed readings or confirmed incidents in this range. This does not establish uninterrupted uptime.';eventsNode.append(li)}
 for(const evt of visible){
  const li=document.createElement('li'),body=document.createElement('span'),strong=document.createElement('strong');
  body.className='timeline-evidence';strong.textContent=diagDate(new Date(evt.t).toISOString())+' · '+evt.kind;
  body.append(strong,document.createTextNode(' — '+evt.detail));
  const button=document.createElement('button');button.className='secondary';button.type='button';
  button.textContent='Inspect time';button.onclick=()=>{timelineSelectAt(evt.t);document.getElementById('diagTimelineChart').focus()};
  const investigate=document.createElement('button');investigate.type='button';investigate.className='secondary';
  investigate.textContent='Investigate';investigate.onclick=()=>{timelineSelectAt(evt.t);inspectIncidentAt(evt.t)};
  const aiButton=document.createElement('button');aiButton.type='button';aiButton.className='secondary';
  aiButton.textContent='AI investigate';aiButton.onclick=()=>void askAiIncident(evt.t);
  li.append(body,button,investigate,aiButton);eventsNode.append(li);
 }
 if(events.length>visible.length){const li=document.createElement('li');li.textContent=
  'Showing '+visible.length+' of '+events.length+' observed points. View local source JSON for the bounded full set.';
  eventsNode.append(li)}
 timelineFocusTimes=[...new Set([...mem,...cpu].map(p=>Date.parse(p.recorded_at)).concat(events.map(e=>e.t)))].filter(Number.isFinite).sort((a,b)=>a-b);
 document.getElementById('diagTimelineReadout').textContent=
  'Hover, touch or use arrow keys to inspect exact observed timestamps. Empty intervals are unknown, not zero.';
 timelineActiveTime=null;
}
function timelinePickPointer(event){
 if(!timelineData)return;
 const rect=document.getElementById('diagTimelineChart').getBoundingClientRect();
 if(!rect.width)return;
 const x=(event.clientX-rect.left)*timelinePlot.width/rect.width;
 if(x<timelinePlot.left||x>timelinePlot.right)return;
 const [first,last]=timelineRange(timelineData);
 timelineSelectAt(first+(x-timelinePlot.left)/(timelinePlot.right-timelinePlot.left)*(last-first));
}
document.getElementById('diagTimelineChart').addEventListener('pointermove',e=>{if(e.pointerType!=='touch')timelinePickPointer(e)});
document.getElementById('diagTimelineChart').addEventListener('pointerdown',timelinePickPointer);
document.getElementById('diagTimelineLayout').addEventListener('change',()=>{
 if(timelineData)drawIncidentTimeline(timelineData);
});
document.getElementById('diagTimelineChart').addEventListener('keydown',e=>{
 if((e.key==='ArrowLeft'||e.key==='ArrowRight')&&timelineFocusTimes.length){
  e.preventDefault();
  let i=timelineFocusTimes.findIndex(t=>t>= (timelineActiveTime===null?Infinity:timelineActiveTime));
  if(i<0)i=timelineFocusTimes.length-1;
  i=Math.max(0,Math.min(timelineFocusTimes.length-1,i+(e.key==='ArrowLeft'?-1:1)));
  timelineSelectAt(timelineFocusTimes[i]);
 }
});
async function loadIncidentTimeline(){
 if(!document.getElementById('diagDetails').open||!document.getElementById('diagTimelineDetails').open)return;
 const current=++timelineRequestSeq,hours=document.getElementById('diagHours').value;
 const button=document.getElementById('diagTimelineRefresh');button.disabled=true;
 document.getElementById('diagTimelineEvidence').href=apiPath('api/hub-diagnostics/timeline?hours='+encodeURIComponent(hours));
 try{
  const response=await fetch(apiPath('api/hub-diagnostics/timeline?hours='+encodeURIComponent(hours)));
  if(!response.ok)throw Error('HTTP '+response.status);
  const data=await jsonResponse(response);
  if(current!==timelineRequestSeq||hours!==document.getElementById('diagHours').value)return;
  timelineLastRead=Date.now();drawIncidentTimeline(data);
 }catch(error){
  if(current===timelineRequestSeq){
   timelineData=null;document.getElementById('diagTimelineChart').replaceChildren();
   document.getElementById('diagTimelineMeta').textContent='Incident timeline unavailable: '+error.message;
   document.getElementById('diagTimelineReadout').textContent='No observed values were loaded; do not infer zero.';
  }
 }finally{if(current===timelineRequestSeq)button.disabled=false}
}
document.getElementById('diagTimelineDetails').addEventListener('toggle',e=>{if(e.target.open)void loadIncidentTimeline()});
document.getElementById('diagTimelineRefresh').addEventListener('click',()=>void loadIncidentTimeline());
document.getElementById('diagTimelineJournal').addEventListener('click',()=>{
 const journal=document.getElementById('journalDetails');journal.open=true;
 document.getElementById('journalCard').scrollIntoView({behavior:'smooth',block:'start'});
});


let incidentReviewFocus=null,incidentReviewSeq=0,incidentReviewText='';
function reviewList(id,lines,empty){
 const list=document.getElementById(id);list.replaceChildren();
 if(!lines.length){const li=document.createElement('li');li.textContent=empty;list.append(li);return}
 for(const line of lines){const li=document.createElement('li');li.textContent=String(line);list.append(li)}
}
function reviewMetricText(value,unit){
 return typeof value==='number'&&Number.isFinite(value)?
   new Intl.NumberFormat('en-GB',{maximumFractionDigits:1}).format(value)+' '+unit:'unknown';
}
function reviewRender(data){
 const rec=data.recorder||{},j=data.journal||{},lines=[];
 const format=e=>e&&e.recorded_at?diagDate(e.recorded_at):'not recorded';
 const eventLines=[];
 eventLines.push('Focus: '+diagDate(data.focus_at)+' · '+data.window_minutes_each_side+
   ' minutes on each side · interval '+diagDate(data.window_start)+' to '+diagDate(data.window_end));
 eventLines.push('Recorder coverage: '+String(rec.status||'unavailable')+' · '+
   String(rec.sample_count??0)+' retained probes ('+String(rec.reachable_samples??0)+
   ' successful, '+String(rec.failed_samples??0)+' failed)'+
   (rec.samples_truncated?' · response capped at '+rec.sample_limit+' rows':''));
 for(const [key,title,unit] of [
  ['memory_min','Lowest observed free OS memory','MB'],
  ['cpu_load_max','Highest observed native 5m load equivalent','%'],
  ['java_free_min','Lowest observed native Java free memory','MB']]){
  const item=rec[key];
  eventLines.push(title+': '+(item?reviewMetricText(item.value,unit)+' at '+
    format(item)+(item.native_sample_label?' · source '+item.native_sample_label:''):
    'not observed in this window (not zero)'));
 }
 for(const [key,label] of [['last_success_before','Last successful external probe at/before focus'],
                           ['first_success_after','First successful external probe at/after focus']]){
  const item=rec[key];eventLines.push(label+': '+(item?format(item)+' · free OS '+
    reviewMetricText(item.free_os_mb,'MB')+' · latency '+reviewMetricText(item.latency_ms,'ms'):
    'not recorded in this window'));
 }
 const occurrences=[];
 for(const e of Array.isArray(rec.startups)?rec.startups:[]){
  occurrences.push({time:e.occurred_at,text:'CONFIRMED STARTUP · systemStart'+
    (e.firmware?' · firmware '+e.firmware:'')+' · cause unverified'});
 }
 for(const e of Array.isArray(rec.incidents)?rec.incidents:[]){
  occurrences.push({time:e.started_at,text:'CONNECTIVITY LOSS · external probe failures · not proof of reboot'});
  if(e.recovered_at)occurrences.push({time:e.recovered_at,text:'CONNECTIVITY RECOVERED · external successful probe'});
 }
 for(const [key,title,unit] of [
  ['memory_min','OS MEMORY MINIMUM','MB'],
  ['cpu_load_max','NATIVE 5M LOAD MAXIMUM','%']]){
  const item=rec[key];if(item)occurrences.push({time:item.recorded_at,text:title+' · '+reviewMetricText(item.value,unit)});
 }
 occurrences.sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
 reviewList('diagReviewRecorder',occurrences.map(e=>diagDate(e.time)+' — '+e.text),
   'No saved startup, connectivity incident or observed extreme in this interval; absence is not proof of uninterrupted operation.');
 const events=Array.isArray(j.events)?j.events:[],groups=Array.isArray(j.app_log_apps)?j.app_log_apps:[],
       gaps=Array.isArray(j.gaps)?j.gaps:[];
 const journalSummary='Journal: '+String(j.status||'unavailable')+
   ' · '+String(j.event_count??0)+' retained device events'+
   ' · '+String(j.app_log_count??0)+' retained app-log receipts'+
   ' · '+String(gaps.length)+' listed collection gaps'+
   (j.events_truncated?' · event preview capped at '+String(j.event_limit||40):'')+
   (j.app_log_apps_truncated?' · app list capped':'')+
   (j.gaps_truncated?' · gap list capped':'')+
   ' · incomplete coverage; empty results do not prove inactivity.';
 document.getElementById('diagReviewJournalStatus').textContent=journalSummary;
 reviewList('diagReviewJournal',events.map(e=>diagDate(e.observed_at)+' · '+
   String(e.display_name||'Device '+(e.device_id||'?'))+' (ID '+String(e.device_id||'?')+')'+
   ' · '+String(e.attribute||'event')+' = '+String(e.value??'')+
   ' · '+String(e.timestamp_basis==='source'?'source-timed':'collector received')+
   ' · '+String(e.source||'Hubitat journal')),
   'No matching retained device observations. This does not establish device inactivity.');
 reviewList('diagReviewAppCounts',groups.map(e=>'App '+String(e.app_id||'?')+
   ' · '+String(e.count??0)+' stored log receipts · '+diagDate(e.first_received)+
   ' to '+diagDate(e.last_received)),
   j.capture_logs===false?'App-log capture disabled or not configured.':
    'No retained app-log receipts in this interval (or log retention already expired).');
 reviewList('diagReviewGaps',gaps.map(e=>String(e.stream||'stream')+' · '+
   diagDate(e.started_at)+' to '+(e.ended_at?diagDate(e.ended_at):'not recovered')+
   ' · '+String(e.reason||'unspecified')),
   'No journal gaps recorded in this interval; recording completeness is unverified.');
 document.getElementById('diagReviewStats').textContent=
  eventLines.join(' · ')+' · '+journalSummary;
 document.getElementById('diagReviewStatus').textContent=
  'Read-only archive received · all causal conclusions UNVERIFIED · no live Hubitat calls or automation changes.';
 incidentReviewText=[...eventLines,...occurrences.map(e=>diagDate(e.time)+' — '+e.text),
   journalSummary,'Journal device observations (preview):',
   ...events.map(e=>diagDate(e.observed_at)+' · '+String(e.display_name||e.device_id)+
     ' '+String(e.attribute||'')+'='+String(e.value??'')+' ('+String(e.timestamp_basis||'unknown')+')'),
   'App log receipts (no message contents):',
   ...groups.map(e=>'App '+String(e.app_id||'?')+': '+String(e.count??0)),
   'Journal connection gaps:',...gaps.map(e=>String(e.stream||'stream')+
     ' '+String(e.started_at||'')+' → '+String(e.ended_at||'open')),
   'Root cause: UNVERIFIED. Retention, source clocks and stream gaps limit inference.'
 ].join('\n');
}
async function loadIncidentReview(){
 if(!incidentReviewFocus)return;
 const current=++incidentReviewSeq,mins=document.getElementById('diagReviewMinutes').value;
 const query='api/hub-diagnostics/incident?at='+encodeURIComponent(incidentReviewFocus)+
       '&window_minutes='+encodeURIComponent(mins);
 document.getElementById('diagReviewJson').href=apiPath(query);
 const reload=document.getElementById('diagReviewReload'),status=document.getElementById('diagReviewStatus');
 reload.disabled=true;status.textContent='Reading bounded local evidence…';
 try{
  const response=await fetch(apiPath(query),{cache:'no-store'});
  const result=await jsonResponse(response);
  if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'HTTP '+response.status);
  if(current!==incidentReviewSeq||mins!==document.getElementById('diagReviewMinutes').value)return;
  reviewRender(result);
 }catch(error){
  if(current===incidentReviewSeq){
   incidentReviewText='';
   status.textContent='Incident review unavailable: '+error.message+
      '. No conclusions can be drawn from unavailable evidence.';
   document.getElementById('diagReviewStats').textContent='';
   for(const id of ['diagReviewRecorder','diagReviewJournal','diagReviewAppCounts','diagReviewGaps']){
    reviewList(id,[],'Evidence unavailable (not an empty history).');
   }
  }
 }finally{if(current===incidentReviewSeq)reload.disabled=false}
}
function inspectIncidentAt(timestamp){
 if(!Number.isFinite(timestamp))return;
 incidentReviewFocus=new Date(timestamp).toISOString();
 const review=document.getElementById('diagReviewDetails');
 review.hidden=false;review.open=true;
 void loadIncidentReview();
 review.scrollIntoView({behavior:'smooth',block:'nearest'});
}
document.getElementById('diagReviewSelected').addEventListener('click',()=>{
 if(timelineActiveTime!==null)inspectIncidentAt(timelineActiveTime);
});
document.getElementById('diagReviewReload').addEventListener('click',()=>void loadIncidentReview());
document.getElementById('diagReviewMinutes').addEventListener('change',()=>void loadIncidentReview());
// Incidents are explicit user-initiated analyses, not automatic background work.
async function askAiIncident(timestamp){
 if(!Number.isFinite(timestamp))return;
 const when=new Date(timestamp).toISOString();
 const chosenMinutes=Number(document.getElementById('diagReviewMinutes').value)||15;
 const prompt='Investigate the Hubitat resource/startup incident centered on '+when+
  '. Use verified local recorder and Historical Journal evidence, compare with read-only Hub Events, app logs and performance history, and explain competing causes without assuming correlation proves causation. Do not change anything.';
 document.getElementById('query').scrollIntoView({behavior:'smooth',block:'center'});
 await submit({text:prompt,incidentAI:{at:when,window_minutes:chosenMinutes}});
}
document.getElementById('diagAiSelected').addEventListener('click',()=>{
 if(timelineActiveTime!==null)void askAiIncident(timelineActiveTime);
});
document.getElementById('diagReviewAskAi').addEventListener('click',()=>{
 if(incidentReviewFocus)void askAiIncident(Date.parse(incidentReviewFocus));
});
document.getElementById('diagReviewCopy').addEventListener('click',()=>{
 const button=document.getElementById('diagReviewCopy');
 if(incidentReviewText)void copyText(incidentReviewText,button,'Copy evidence summary');
});

const diagUnit={free_os_mb:'MB',java_free_mb:'MB',java_allocated_heap_used_pct:'%',native_load_pct:'%',native_load5:'load',latency_ms:'ms'};
let diagHistoryRows=[],diagIncidents=[],diagReboots=[],diagHistoryMeta={};
function diagDate(value){if(!value)return 'unavailable';const d=new Date(value);return isNaN(d.getTime())?String(value).slice(0,40):d.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false})}
function diagNumber(value,unit){return typeof value==='number' && Number.isFinite(value)?value.toFixed(unit==='%'?1:unit==='load'?2:0)+' '+unit:'—'}
function renderDiagnosticsStatus(data){
const state=document.getElementById('diagState'),row=data.last||{},status=data.status||'unknown';
state.textContent=status;state.className='health-status-chip '+(status==='online'?'health-ok':status==='disabled'?'health-neutral':'health-critical');
document.getElementById('diagOS').textContent=diagNumber(row.free_os_mb,'MB');
document.getElementById('diagJava').textContent=diagNumber(row.java_free_mb,'MB');
document.getElementById('diagHeap').textContent=diagNumber(row.java_allocated_heap_used_pct,'%');
document.getElementById('diagCpuPercent').textContent=diagNumber(row.native_load_pct,'%');
document.getElementById('diagCpuMethod').textContent='CPU load equivalent = 5-minute load average ÷ '+
 (Number(data.cpu_cores)||4)+' logical processors × 100; not measured CPU utilisation (can exceed 100% under heavy load).';
document.getElementById('diagLatency').textContent=diagNumber(row.latency_ms,'ms');
const details=status==='disabled'?'Enable external diagnostics in the add-on configuration.':(data.error||'');
const age=row.recorded_at?'Last probe '+diagDate(row.recorded_at):'No saved probe yet';
const source=row.native_sample_label?' · Java source '+row.native_sample_label:' · Java source not yet recorded';
document.getElementById('diagSummary').textContent=age+source+' · '+(data.consecutive_failures||0)+' consecutive failures. '+details;
}
const diagPlot={left:72,right:822,top:29,bottom:280,width:860,height:320};
let diagPlottedPoints=[],diagActivePoint=0;
function diagMetricValue(value,metric){
 if(!Number.isFinite(value))return '—';
 const digits=metric==='native_load5'?2:1;
 const unit=diagUnit[metric]||'';
 const formatted=new Intl.NumberFormat('en-GB',{maximumFractionDigits:digits}).format(value);
 return formatted+(unit?' '+unit:'');
}
function diagChartSvgNode(tag,attributes,textValue){
 const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
 for(const [k,v] of Object.entries(attributes||{}))node.setAttribute(k,String(v));
 if(textValue!==undefined)node.textContent=String(textValue);
 return node;
}
function diagSelectPoint(index){
 if(!diagPlottedPoints.length)return;
 diagActivePoint=Math.max(0,Math.min(diagPlottedPoints.length-1,index));
 const point=diagPlottedPoints[diagActivePoint],row=point.row,metric=document.getElementById('diagMetric').value;
 const sourceNote=(metric.startsWith('java_')||metric==='native_load5'||metric==='native_load_pct')?
   (' · native source '+String(row.native_sample_label||'unknown')):' · external probe';
 const label=document.getElementById('diagMetric').selectedOptions[0].textContent;
 const recorded=diagDate(row.recorded_at),value=diagMetricValue(row[metric],metric);
 document.getElementById('diagPointReadout').textContent=recorded+' — '+label+': '+value+sourceNote;
 const marker=document.getElementById('diagChartMarker'),cross=document.getElementById('diagChartCrosshair');
 const horizontal=document.getElementById('diagChartHorizontal');
 if(marker&&cross){
  marker.setAttribute('cx',point.x);marker.setAttribute('cy',point.y);
  marker.setAttribute('visibility','visible');
  cross.setAttribute('x1',point.x);cross.setAttribute('x2',point.x);
  cross.setAttribute('visibility','visible');
 }
 if(horizontal){
  horizontal.setAttribute('x2',point.x);
  horizontal.setAttribute('y1',point.y);horizontal.setAttribute('y2',point.y);
  horizontal.setAttribute('visibility','visible');
 }
 const tip=document.getElementById('diagTooltip'),tipTime=document.getElementById('diagTipTime'),
       tipValue=document.getElementById('diagTipValue');
 if(tip&&tipTime&&tipValue){
  const tipWidth=195,tipHeight=50;
  const tipX=point.x+tipWidth+14<=diagPlot.right?point.x+14:point.x-tipWidth-14;
  const tipY=Math.max(diagPlot.top+4,Math.min(diagPlot.bottom-tipHeight-4,point.y-tipHeight-13));
  tip.setAttribute('transform','translate('+tipX.toFixed(1)+','+tipY.toFixed(1)+')');
  tip.setAttribute('visibility','visible');
  tipTime.textContent=recorded;
  tipValue.textContent=value;
 }
}
function drawDiagRebootMarkers(svg,first,last){
 if(!Number.isFinite(first)||!Number.isFinite(last)||last<=first)return;
 let previousX=-100;
 for(const event of diagReboots.slice(0,120)){
  const when=Date.parse(event.occurred_at);
  if(!Number.isFinite(when)||when<first||when>last)continue;
  const x=diagPlot.left+(when-first)/(last-first)*(diagPlot.right-diagPlot.left);
  const line=diagChartSvgNode('line',{x1:x,x2:x,y1:diagPlot.top,y2:diagPlot.bottom,
      stroke:'#f59e0b','stroke-width':1.5,'stroke-dasharray':'3 4',
      'aria-label':'Hub startup '+diagDate(event.occurred_at)});
  line.append(diagChartSvgNode('title',{},'Hubitat systemStart · '+diagDate(event.occurred_at)+
      (event.firmware?' · firmware '+event.firmware:'')+
      ' · restart cause not established'));
  svg.append(line);
  if(x-previousX>62){
   const label=diagChartSvgNode('text',{x:Math.min(x+3,diagPlot.right-43),
       y:diagPlot.top+12,fill:'#fbbf24','font-size':11},'Reboot');
   label.append(diagChartSvgNode('title',{},'Confirmed systemStart · '+diagDate(event.occurred_at)));
   svg.append(label);previousX=x;
  }
 }
}
function drawDiagnosticsChart(){
 const svg=document.getElementById('diagChart'),metric=document.getElementById('diagMetric').value;
 const nativeMetric=metric.startsWith('java_')||metric==='native_load5'||metric==='native_load_pct';
 svg.replaceChildren();
 let points=diagHistoryRows.filter(row=>row && typeof row[metric]==='number' &&
    Number.isFinite(row[metric]) && Number.isFinite(Date.parse(row.recorded_at)) &&
    (!['free_os_mb','latency_ms'].includes(metric)||row.reachable));
 if(nativeMetric){
  const seen=new Set();
  points=points.filter(row=>{const key=row.native_sample_label;if(!key||seen.has(key))return false;seen.add(key);return true});
 }
 points.sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at));
 const summaryCount=diagHistoryMeta.observed_metric_points??points.length;
 const sourceCount=diagHistoryMeta.source_sample_count??diagHistoryRows.length;
 document.getElementById('diagChartCaption').textContent=diagHistoryMeta.downsampled?
   'Displaying '+points.length+' preserved real '+(nativeMetric?'native':'external')+
   ' readings from '+summaryCount+' observed points ('+sourceCount+' source probes) · Includes actual min/max and segment boundaries · No interpolated data':
   points.length+' observed '+(nativeMetric?'native source':'external probe')+
   ' points · '+(sourceCount-points.length)+' other/unknown/duplicate samples · No interpolation across missing intervals';
 const stats=document.getElementById('diagChartStats'),detail=document.getElementById('diagPointReadout');
 diagPlottedPoints=[];
 if(!points.length){
  stats.textContent='Minimum — · Maximum — · Latest —';
  detail.textContent='No actual readings for this metric yet. A blank period is not zero.';
  svg.append(diagChartSvgNode('text',{x:diagPlot.left,y:114,fill:'#a1a1aa','font-size':15},
    'No recorded values in the selected period'));
  drawDiagRebootMarkers(svg,Date.parse(diagHistoryMeta.range_start),
                             Date.parse(diagHistoryMeta.range_end));
  return;
 }
 const values=points.map(p=>p[metric]);
 const rawMin=Math.min(...values),rawMax=Math.max(...values);
 stats.textContent='Minimum: '+diagMetricValue(rawMin,metric)+' · Maximum: '+
   diagMetricValue(rawMax,metric)+' · Latest: '+diagMetricValue(points[points.length-1][metric],metric)+
   ' ('+diagDate(points[points.length-1].recorded_at)+')';
 const padding=Math.max(metric==='native_load5'?0.1:metric==='java_allocated_heap_used_pct'?0.5:1,
                        (rawMax-rawMin)*0.15);
 const pixelWidth=svg.getBoundingClientRect().width||diagPlot.width;
 const scale=diagNiceChartScale(Math.max(0,rawMin-padding),rawMax+padding,pixelWidth<480?6:9);
 const min=scale.min,max=scale.max,span=max-min;
 const timestamps=diagHistoryRows.map(x=>Date.parse(x.recorded_at)).filter(Number.isFinite);
 const rStart=Date.parse(diagHistoryMeta.range_start),rEnd=Date.parse(diagHistoryMeta.range_end);
 const first=Number.isFinite(rStart)?rStart:Math.min(...timestamps);
 const last=Number.isFinite(rEnd)?rEnd:Math.max(...timestamps);
 const duration=Math.max(1,last-first);
 const xCoord=row=>diagPlot.left+(Date.parse(row.recorded_at)-first)/duration*(diagPlot.right-diagPlot.left);
 const yCoord=row=>diagPlot.bottom-(row[metric]-min)/span*(diagPlot.bottom-diagPlot.top);
 const group=diagChartSvgNode('g',{'aria-hidden':'true'});
 const metricLabel=document.getElementById('diagMetric').selectedOptions[0].textContent;
 group.append(diagChartSvgNode('text',{x:diagPlot.left,y:15,fill:'#cbd5e1','font-size':12},metricLabel));
 diagChartYGrid(group,diagPlot.left,diagPlot.right,diagPlot.top,diagPlot.bottom,
  scale,metric,'#b4c1d3');
 diagChartTimeGrid(svg,group,first,last,diagPlot.left,diagPlot.right,
  diagPlot.top,diagPlot.bottom,309);
 svg.append(group);
 drawDiagRebootMarkers(svg,first,last);
 let path='',previous=null,previousSegment=null;
 for(const row of points){
  const x=xCoord(row),y=yCoord(row),t=Date.parse(row.recorded_at);
  const breakGap=previous!==null&&(
    (Number.isInteger(row.diag_segment)&&Number.isInteger(previousSegment)&&
       row.diag_segment!==previousSegment)||
    (!diagHistoryMeta.downsampled&&t-previous>(nativeMetric?900000:120000)));
  path+=(path&&!breakGap?' L':' M')+x.toFixed(2)+' '+y.toFixed(2);
  diagPlottedPoints.push({row,x,y});previous=t;previousSegment=row.diag_segment;
 }
 svg.append(diagChartSvgNode('path',{d:path.trim(),fill:'none',stroke:'#60a5fa',
   'stroke-width':2.2,'stroke-linejoin':'round','stroke-linecap':'round'}));
 // Mark actual extrema even when there are too many readings for point dots.
 for(const value of [...new Set([rawMin,rawMax])]){
  const p=diagPlottedPoints.find(x=>x.row[metric]===value);
  if(!p)continue;
  const dot=diagChartSvgNode('circle',{cx:p.x,cy:p.y,r:4.3,fill:'#60a5fa',
   stroke:'#f8fafc','stroke-width':1.2});
  dot.append(diagChartSvgNode('title',{},diagDate(p.row.recorded_at)+
   ' · observed '+(value===rawMin?'minimum':'maximum')+' '+diagMetricValue(value,metric)));
  svg.append(dot);
 }
 // On short windows expose individual actual samples, not fabricated in-between values.
 if(points.length<=80){
  for(const p of diagPlottedPoints){
   const circle=diagChartSvgNode('circle',{cx:p.x,cy:p.y,r:2.8,fill:'#93c5fd'});
   circle.append(diagChartSvgNode('title',{},diagDate(p.row.recorded_at)+
     ' — '+diagMetricValue(p.row[metric],metric)));
   svg.append(circle);
  }
 }
 svg.append(diagChartSvgNode('line',{id:'diagChartHorizontal',x1:diagPlot.left,x2:diagPlot.left,y1:0,y2:0,
   stroke:'#cbd5e1','stroke-width':1.2,'stroke-dasharray':'2 5',visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('line',{id:'diagChartCrosshair',x1:0,x2:0,
   y1:diagPlot.top,y2:diagPlot.bottom,stroke:'#e2e8f0','stroke-width':1.4,
   'stroke-dasharray':'2 5',visibility:'hidden','pointer-events':'none'}));
 svg.append(diagChartSvgNode('circle',{id:'diagChartMarker',cx:0,cy:0,r:5.5,
   stroke:'#101114','stroke-width':2,fill:'#fbbf24',visibility:'hidden','pointer-events':'none'}));
 const tooltip=diagChartSvgNode('g',{id:'diagTooltip',visibility:'hidden','pointer-events':'none'});
 tooltip.append(diagChartSvgNode('rect',{x:0,y:0,width:195,height:50,rx:7,fill:'#17263a',stroke:'#64748b'}));
 tooltip.append(diagChartSvgNode('text',{id:'diagTipTime',x:9,y:16,fill:'#e2e8f0','font-size':11}));
 tooltip.append(diagChartSvgNode('text',{id:'diagTipValue',x:9,y:33,fill:'#f8fafc','font-size':15,'font-weight':'bold'}));
 svg.append(tooltip);
 diagSelectPoint(diagPlottedPoints.length-1);
}
function diagSelectNearPointer(event){
 if(!diagPlottedPoints.length)return;
 const svg=document.getElementById('diagChart'),box=svg.getBoundingClientRect();
 if(!box.width)return;
 const x=(event.clientX-box.left)*diagPlot.width/box.width;
 if(x<diagPlot.left-24||x>diagPlot.right+24)return;
 // Binary search keeps interaction cheap even on 30-day min/max summaries.
 let low=0,high=diagPlottedPoints.length-1;
 while(low<high){const middle=Math.floor((low+high)/2);
  if(diagPlottedPoints[middle].x<x)low=middle+1;else high=middle}
 const idx=low>0&&Math.abs(diagPlottedPoints[low-1].x-x)<Math.abs(diagPlottedPoints[low].x-x)?low-1:low;
 if(Math.abs(diagPlottedPoints[idx].x-x)>24){
  document.getElementById('diagPointReadout').textContent='No observed sample near this time. Blank intervals are unknown, not zero.';
  for(const id of ['diagTooltip','diagChartMarker','diagChartCrosshair','diagChartHorizontal']){
   const item=document.getElementById(id);if(item)item.setAttribute('visibility','hidden');
  }
  return;
 }
 diagSelectPoint(idx);
}
document.getElementById('diagChart').addEventListener('pointermove',event=>{
 if(event.pointerType!=='touch')diagSelectNearPointer(event);
});
document.getElementById('diagChart').addEventListener('pointerdown',diagSelectNearPointer);
document.getElementById('diagChart').addEventListener('keydown',event=>{
 if(event.key==='ArrowLeft'||event.key==='ArrowRight'){
  event.preventDefault();
  diagSelectPoint(diagActivePoint+(event.key==='ArrowLeft'?-1:1));
 }
});
async function loadDiagnosticsStatus(){try{const r=await fetch(apiPath('api/hub-diagnostics/status'));if(!r.ok)throw Error('HTTP '+r.status);renderDiagnosticsStatus(await jsonResponse(r))}catch(e){document.getElementById('diagState').textContent='Unavailable';document.getElementById('diagSummary').textContent='HomeBrain diagnostic API unavailable: '+e.message}}
async function loadDiagnosticsHistory(){
 if(!document.getElementById('diagDetails').open)return;
 const button=document.getElementById('diagRefresh');
 button.disabled=true;
 try{
  const hours=document.getElementById('diagHours').value;
  const metric=document.getElementById('diagMetric').value;
  const url='api/hub-diagnostics/history?hours='+encodeURIComponent(hours)+
            '&metric='+encodeURIComponent(metric);
  const response=await fetch(apiPath(url));
  if(!response.ok)throw Error('HTTP '+response.status);
  const data=await jsonResponse(response);
  diagHistoryRows=Array.isArray(data.samples)?data.samples:[];
  diagIncidents=Array.isArray(data.incidents)?data.incidents:[];
  diagReboots=Array.isArray(data.reboots)?data.reboots:[];
  diagHistoryMeta=data;
  drawDiagnosticsChart();
  const reboots=document.getElementById('diagReboots');
  reboots.replaceChildren();
  if(!diagReboots.length){
   const li=document.createElement('li');
   li.textContent='No confirmed systemStart events available in this range (absence does not prove no reboot).';
   reboots.append(li);
  }
  for(const event of diagReboots.slice().reverse()){
   const li=document.createElement('li');
   li.textContent='Hub startup recorded '+diagDate(event.occurred_at)+
     (event.firmware?' · firmware '+event.firmware:'')+' · systemStart (cause not established)';
   reboots.append(li);
  }
  const list=document.getElementById('diagIncidents');
  list.replaceChildren();
  if(!diagIncidents.length){
   const li=document.createElement('li');
   li.textContent='No connectivity incidents recorded in this period.';
   list.append(li);
  }
  for(const incident of diagIncidents){
   const li=document.createElement('li');
   li.textContent=diagDate(incident.started_at)+' — '+
    (incident.recovered_at?'recovered '+diagDate(incident.recovered_at):'recovery not yet recorded')+
    ' · external connectivity loss (not a confirmed reboot)';
   list.append(li);
  }
 }catch(error){
  document.getElementById('diagChartCaption').textContent=
    'Recorded history unavailable: '+error.message;
 }finally{
  button.disabled=false;
 }
}
document.getElementById('diagDetails').addEventListener('toggle',e=>{
 if(e.target.open){void loadDiagnosticsHistory();void loadIncidentTimeline()}
});
document.getElementById('diagMetric').addEventListener('change',()=>void loadDiagnosticsHistory());
document.getElementById('diagHours').addEventListener('change',()=>{
 void loadDiagnosticsHistory();void loadIncidentTimeline();
});
document.getElementById('diagRefresh').addEventListener('click',()=>{
 void loadDiagnosticsStatus();void loadDiagnosticsHistory();void loadIncidentTimeline();
});
loadDiagnosticsStatus();
setInterval(()=>{void loadDiagnosticsStatus();if(document.getElementById('diagDetails').open)void loadDiagnosticsHistory()},60000);
setInterval(()=>{
 if(document.getElementById('diagDetails').open&&document.getElementById('diagTimelineDetails').open&&
    Date.now()-timelineLastRead>=300000)void loadIncidentTimeline();
},300000);

status();setInterval(status,30000);
</script></body></html>"""
        .replace("__SAFE_TITLE__", safe_title)
        .replace("__TITLE__", title_json)
        .replace("__VERSION__", version_json)
    )


__all__ = ["render_page"]
