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
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,sans-serif}.wrap{max-width:960px;margin:auto;padding:16px}h1{font-size:30px;margin:4px 0 10px}.card{background:var(--card);border-radius:14px;padding:12px;margin:8px 0}.row,.grid{display:flex;gap:8px;flex-wrap:wrap}.pill{padding:8px 12px;border-radius:999px;background:#3a3a3d;font-size:13px}.pill.ok{background:var(--green)}.pill.error{background:var(--red)}.pill strong{margin-left:4px}.status-card{padding:8px 10px;gap:6px;margin:8px 0}.status-card .pill{padding:5px 8px;font-size:11px;line-height:1.15}.status-card .pill strong{margin-left:3px;font-size:11px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.tile{background:var(--tile);border-radius:12px;padding:10px;min-width:0}.big{font-size:20px;font-weight:700;overflow-wrap:anywhere;word-break:break-word}.top-stats{grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:7px}.top-stats .tile{margin:0;padding:7px 5px;min-height:66px;font-size:12px;line-height:1.15}.top-stats .big{font-size:19px}.top-stats .muted{font-size:10px;line-height:1.15;margin-top:2px}.quick-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;padding:7px}.quick-grid button,.quick-grid .quick-link{margin:0;min-height:42px;padding:7px 5px;border-radius:10px;font-size:11px;line-height:1.15}.quick-link{display:flex;align-items:center;justify-content:center;background:#333;color:#fff;text-decoration:none;text-align:center}.muted{color:var(--muted);font-size:13px}input,button{width:100%;border:0;border-radius:12px;padding:14px;margin:7px 0;font:inherit}input{background:#fff;color:#111}button{background:var(--blue);color:#fff;cursor:pointer}.query-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:7px 0}.query-actions button{margin:0}.answer-options{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin:6px 0}.answer-options label{margin:0}.browser-shortcut{display:none;width:auto;margin:0;padding:8px 10px;font-size:12px}.browser-shortcut.visible{display:inline-block}.secondary{background:#333}.confirm{background:var(--green)}.answer{background:#000;border-radius:12px;padding:14px;min-height:52px;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}.answer-meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.badge{background:#243044;border-radius:999px;padding:4px 8px;font-size:12px}.outcome-badge{font-weight:700}.outcome-positive{background:#14532d;color:#bbf7d0}.outcome-warning{background:#78350f;color:#fde68a}.outcome-neutral{background:#3f3f46;color:#e4e4e7}.outcome-critical{background:#7f1d1d;color:#fecaca}.answer-text{white-space:pre-wrap}.technical{margin-top:12px;color:var(--muted)}.technical summary{cursor:pointer}.technical pre{white-space:pre-wrap;overflow:auto;max-height:260px;background:#111;padding:10px;border-radius:8px}.busy{opacity:.65}
.clear-context{width:auto;margin:0;padding:6px 10px;border-radius:9px;font-size:12px;white-space:nowrap}
.model-tier-picker{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:7px 0 3px}
.model-tier-picker label{font-size:12px;color:var(--muted)}
.model-tier-picker select{width:auto;max-width:100%;background:#303033;color:#fff;border:1px solid #56565c;border-radius:9px;padding:8px 10px;font-size:13px}
.model-tier-note{font-size:11px;color:var(--muted);line-height:1.4}
@media(max-width:520px){.model-tier-picker select{flex:1;min-width:185px}}
.answer-text p{margin:0 0 10px}.answer-text p:last-child{margin-bottom:0}.answer-text h2,.answer-text h3{margin:14px 0 6px;font-size:18px}.answer-text ul,.answer-text ol{margin:6px 0 10px;padding-left:24px}.answer-text li{margin:5px 0}.status-label{display:inline-block;border-radius:999px;padding:2px 8px;margin-right:7px;font-size:11px;font-weight:700;letter-spacing:.03em;vertical-align:1px}.status-active{background:#14532d;color:#bbf7d0}.status-disabled{background:#3f3f46;color:#e4e4e7}.status-paused{background:#78350f;color:#fde68a}.status-broken{background:#7f1d1d;color:#fecaca}.status-unknown{background:#1e3a8a;color:#bfdbfe}.inline-critical{color:#f87171;font-weight:700}.heading-active{color:#4ade80}.heading-disabled{color:#a1a1aa}.heading-paused{color:#fbbf24}.heading-broken{color:#f87171}.heading-unknown{color:#60a5fa}
.health-heading{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.health-status-chip{display:inline-block;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:700}.health-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}.health-stat{background:#111;border-radius:10px;padding:10px}.health-ok{color:#4ade80}.health-warn{color:#fbbf24}.health-critical{color:#f87171}.health-neutral{color:#a1a1aa}.health-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.health-actions button{width:auto;margin:0}.health-details{margin-top:10px}.health-details summary{cursor:pointer}.health-domain-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:8px 0 12px}.health-domain{background:#111;border-radius:9px;padding:8px}.health-domain strong{display:block}.health-section{margin-top:10px}.health-list{margin:6px 0 0;padding-left:22px}.health-list li{margin:5px 0;color:#e5e7eb}.health-target-critical,.health-state-critical{color:#f87171;font-weight:600}.health-target-warning,.health-state-warning{color:#fbbf24;font-weight:600}.health-new{font-weight:700}.health-resolved{color:#4ade80}\n.automation-view{white-space:normal}.automation-summary{margin:0 0 10px}.automation-toolbar{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.automation-toolbar input{flex:1 1 220px;margin:0;padding:10px}.automation-toolbar button{width:auto;margin:0;padding:9px 11px;font-size:12px}.automation-filters{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 12px}.automation-filter{width:auto;margin:0;padding:7px 10px;background:#27272a;font-size:12px}.automation-filter.selected{background:var(--blue)}.automation-section{border:1px solid #29292d;border-radius:10px;margin:8px 0;background:#111}.automation-section summary{cursor:pointer;padding:11px 12px;font-weight:700;list-style-position:inside}.automation-section ul{margin:0;padding:0 12px 10px 34px}.automation-section li{margin:6px 0}.automation-section[hidden]{display:none}.automation-kind{color:var(--muted);font-size:11px;margin-left:6px}.automation-empty{color:var(--muted);padding:8px 0}.automation-section-active summary{color:#4ade80}.automation-section-disabled summary{color:#a1a1aa}.automation-section-paused summary{color:#f87171}.automation-section-broken summary{color:#f87171}.automation-section-unknown summary{color:#60a5fa}
.mic-fab{position:fixed;right:18px;bottom:18px;z-index:10;width:64px;height:64px;margin:0;border-radius:50%;font-size:27px;background:var(--green);box-shadow:0 10px 30px rgba(0,0,0,.5)}.mic-fab.listening{background:#dc2626}.copy-button{width:auto;display:block;margin:10px 0 0 auto;padding:7px 10px;font-size:12px}.technical-copy{margin-top:7px}.copy-ok{background:var(--green)}.copy-fail{background:var(--red)}
@media(max-width:520px){.wrap{padding:8px 8px 82px}h1{font-size:23px;margin:2px 0 7px}.card{border-radius:10px;padding:8px;margin:6px 0}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.top-stats{grid-template-columns:repeat(4,minmax(0,1fr));padding:5px;gap:4px}.top-stats .tile{min-height:54px;padding:5px 3px;font-size:10px}.top-stats .big{font-size:17px}.top-stats .muted{display:none}.quick-grid{grid-template-columns:repeat(3,minmax(0,1fr));padding:5px;gap:4px}.quick-grid button,.quick-grid .quick-link{min-height:38px;padding:5px 3px;font-size:10px}.health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.health-stat{padding:7px}.mic-fab{right:12px;bottom:12px;width:58px;height:58px;font-size:23px}.automation-toolbar input{flex-basis:100%}}
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

.benchmark-controls{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:center;margin-top:10px}
.benchmark-controls select{min-width:0;width:100%;background:#303033;color:#fff;border:1px solid #52525b;border-radius:9px;padding:10px}
.benchmark-controls button{width:auto;margin:0;padding:10px 13px}
.benchmark-consent{display:flex;align-items:flex-start;gap:8px;margin-top:10px;font-size:13px;line-height:1.5}
.benchmark-consent input{width:auto;margin:3px 0;flex:none}
.benchmark-report{white-space:normal;font-size:13px;line-height:1.55;margin-top:10px}
.benchmark-report p{margin:7px 0}
.benchmark-check{padding:7px 0;border-bottom:1px solid #37373b}
.benchmark-check:last-child{border-bottom:0}
@media(max-width:520px){.benchmark-controls{grid-template-columns:1fr}.benchmark-controls button{width:100%}}

.stage5-note{margin:8px 0;font-size:12px;color:var(--muted);line-height:1.45}
.stage5-choices{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin:8px 0}
.stage5-choices select{width:100%;min-width:0;background:#303033;border:1px solid #56565c;color:#fff;border-radius:9px;padding:11px}
.stage5-choices button{width:auto;margin:0;padding:10px 12px}
.stage5-review{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}
.stage5-review label{font-size:12px;color:var(--muted)}
.stage5-review select{width:auto;background:#303033;color:#fff;border:1px solid #56565c;padding:6px;border-radius:7px;margin:0 4px}
@media(max-width:520px){.stage5-choices{grid-template-columns:1fr}.stage5-choices button{width:100%}}
</style>
</head>
<body><main class="wrap">
<h1>🏠 <span id="title"></span> <small id="version"></small></h1>
<section class="card grid top-stats" id="summaryTiles">
<button class="tile secondary" data-q="Which rooms are active?"><div class="big" id="dashActiveRooms">—</div><div>Active rooms</div><div class="muted" id="dashActiveRoomNames">Motion or lights on</div></button>
<button class="tile secondary" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div><div class="muted">Tap for live details</div></button>
<button class="tile secondary" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div><div class="muted">Live Hubitat states</div></button>
<button class="tile secondary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div><div class="muted">At or below 20%</div></button>
</section>
<section class="card quick-grid" id="shortcuts">
<button class="secondary" data-q="What's happening at home?">🏠 What's happening?</button>
<button class="secondary" data-q="List every automation app and Rule Machine rule with its current active, disabled, paused, broken, or unknown status">⚙️ Rules</button>
<button class="secondary" data-q="Check the hub health status">🧠 Hub health</button>
<button class="secondary" data-q="Is there a firmware update available for the hub?">🛠️ Firmware</button>
<button class="secondary" id="refresh">🧰 Refresh MCP</button>
<a class="quick-link" href="http://192.168.1.239/hub2/createFullLocalBackup" target="_blank" rel="noopener noreferrer">💾 Local backup</a>
</section>
<section class="card">
<input id="query" placeholder="Ask your Hubitat…" autocomplete="off">
<div class="model-tier-picker">
<label for="modelTier">AI model</label>
<select id="modelTier" aria-label="AI model for this question">
<option value="auto">Auto · hybrid routing (may charge)</option>
<option value="free">Free · Gemma (default)</option>
<option value="paid">Paid · DeepSeek Pro (Ollama)</option>
<option value="claude">Paid · Claude (Anthropic API)</option>
</select>
<button class="secondary clear-context" id="resetContext" type="button" title="Start without prior context">New topic</button>
</div>
<div class="model-tier-note" id="modelTierNote" role="status">Free is the default. Paid uses Ollama account credits, with no additional HomeBrain budget. Claude bills your Anthropic API account separately.</div>
<div class="query-actions"><button id="ask">Ask</button><button class="secondary" id="speak">🎤 Speak</button></div>
<div class="answer-options"><label class="muted"><input id="readAnswers" type="checkbox" style="width:auto"> Read answers aloud</label><button class="secondary browser-shortcut" id="openBrowser" type="button">🌐 Open in browser</button></div>
<div class="answer" id="answer" role="status" aria-live="polite">Ready for a question.</div>
</section>
<section class="card row status-card"><span class="pill" id="mcp">MCP unknown</span><span class="pill"><span class="muted">MCP tools</span><strong id="tools">—</strong></span><span class="pill" id="ollama">Ollama unknown</span><span class="pill"><span class="muted">Model</span><strong id="model">—</strong></span><span class="pill"><span class="muted">Last route</span><strong id="lastRoute">—</strong></span><span class="pill"><span class="muted">Response</span><strong id="lastTime">—</strong></span></section>
<details class="card" id="cloudBenchmarkCard">
<summary><strong>🧪 Ollama Cloud benchmark</strong> <span class="muted">Uses your current account</span></summary>
<p class="muted" id="cloudBenchmarkAvailability">Checking the configured cloud model…</p>
<p class="muted">Four fictional smart-home investigations. No live hub or device reads. Each test makes one cloud request and may consume your account allowance. Evidence-check scores do not certify the generated explanation.</p>
<label class="muted" for="cloudBenchmarkCase">Choose a fictional scenario</label>
<div class="benchmark-controls">
<select id="cloudBenchmarkCase" aria-label="Cloud benchmark scenario">
<option value="lighting">Lighting command and cause</option>
<option value="heating">Heating and physical operation</option>
<option value="ventilation">Fan and humidity attribution</option>
<option value="history">Missing contact history</option>
</select>
<button id="runCloudBenchmark" type="button" disabled>Run one cloud test</button>
</div>
<label class="benchmark-consent"><input id="cloudBenchmarkConsent" type="checkbox">I authorise one synthetic Ollama Cloud request using my existing account allowance.</label>
<div class="benchmark-report" id="cloudBenchmarkResult" role="status" aria-live="polite">No benchmark run this session.</div>
</details>
<details class="card" id="stage5Card">
<summary><strong>🧠 Stage 5 · Independent AI investigation</strong> <span class="muted">Experimental, current cloud account</span></summary>
<p id="stage5Availability" class="muted">Checking cloud availability…</p>
<p class="stage5-note">Gemma chooses which fictional evidence to inspect, then writes its own answer. No suggested conclusions or live-device access. Each run can use <strong>two</strong> Ollama Cloud requests. Scores check source choices and declared citations, <strong>not the full prose</strong>.</p>
<label class="muted" for="stage5Scenario">Select a fictional incident</label>
<div class="stage5-choices">
<select id="stage5Scenario" aria-label="Independent investigation scenario">
<option value="lighting">Light switched on unexpectedly</option>
<option value="heating">Heating despite warm room</option>
<option value="ventilation">Fan boost unexpectedly on</option>
<option value="connectivity">Mesh plug reported offline</option>
</select>
<button type="button" id="runStage5" disabled>Run independent investigation</button>
</div>
<label class="benchmark-consent"><input id="stage5Consent" type="checkbox">I authorise up to two synthetic Ollama Cloud requests using my existing account allowance.</label>
<div id="stage5Report" class="benchmark-report" role="status" aria-live="polite">No independent investigation has run in this session.</div>
</details>
<details class="card" id="stage6Card">
<summary><strong>🔍 Stage 6 · Conflicting evidence</strong> <span class="muted">Adaptive AI investigation</span></summary>
<p class="muted" id="stage6Availability">Checking configured cloud model…</p>
<button type="button" id="checkCloudConnection" class="secondary">Check cloud connection (no AI request)</button>
<p class="stage5-note" id="cloudConnectionResult" role="status" aria-live="polite">The Ready indicator checks configuration only, not provider authorisation. A connection check sends one account-status request, without model inference or credit usage.</p>
<p class="stage5-note">Gemma decides which fictional records to inspect, one at a time, and when to stop. Cases include misleading clocks, competing app commands and stale MQTT data. This can use <strong>up to four cloud requests</strong>. No hub or device access. Declared citations are checked, but <strong>not every implication of its prose</strong>.</p>
<label class="muted" for="stage6Scenario">Choose a harder fictional investigation</label>
<div class="stage5-choices">
<select id="stage6Scenario" aria-label="Stage 6 scenario">
<option value="clock_conflict">Delayed OFF report versus device time</option>
<option value="competing_commands">Two apps issue competing commands</option>
<option value="stale_connectivity">Mesh plug: connected broker, offline device</option>
</select>
<button type="button" id="runStage6" disabled>Run adaptive investigation</button>
</div>
<label class="benchmark-consent"><input type="checkbox" id="stage6Consent">I authorise up to four synthetic Ollama Cloud requests using my current allowance.</label>
<div id="stage6Report" class="benchmark-report" role="status" aria-live="polite">No Stage 6 investigation has run this session.</div>
</details>
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
<section class="card" id="oneTimeCleanupCard">
<div><div class="health-heading"><strong>One-time rule cleanup</strong><span class="health-status-chip health-neutral" id="cleanupStatus">Loading</span></div><div class="muted" id="cleanupMeta">Loading cleanup scheduler…</div></div>
<div class="health-grid">
<div class="health-stat"><div class="big" id="cleanupNextRun">—</div><div class="muted">Next run</div></div>
<div class="health-stat"><div class="big" id="cleanupLastRun">—</div><div class="muted">Last run</div></div>
<div class="health-stat"><div class="big" id="cleanupDeleted">—</div><div class="muted">Last deleted</div></div>
<div class="health-stat"><div class="big" id="cleanupFailed">—</div><div class="muted">Last failed</div></div>
</div>
<div class="health-actions"><button id="runOneTimeCleanup">🧹 Run cleanup now</button></div>
<details class="health-details" id="cleanupDetails"><summary>View cleanup details</summary><div id="cleanupDetailsBody" class="muted">No cleanup has run yet.</div></details>
</section>
<p class="muted">Powered by Ollama Online native function calling and Hubitat MCP.</p>
</main>
<button id="micFab" class="mic-fab" aria-label="Speak">🎤</button>
<script>
const TITLE=__TITLE__,VERSION=__VERSION__;
const newSessionId=()=>globalThis.crypto?.randomUUID?.()||`hmcp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
let sessionId=newSessionId();
// Retire legacy browser-saved transcripts on upgrade; context now lives only in this open page.
try{localStorage.removeItem('hmcp_chats_v1');sessionStorage.removeItem('hmcp_session_id');
  for(let i=sessionStorage.length-1;i>=0;i--){const key=sessionStorage.key(i);
    if(key&&key.startsWith('hmcp_history_'))sessionStorage.removeItem(key)}}catch(error){}
document.getElementById('title').textContent=TITLE;document.getElementById('version').textContent='v'+VERSION;
const query=document.getElementById('query'),ask=document.getElementById('ask'),answer=document.getElementById('answer');
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
function renderOneTimeCleanup(payload){const schedule=payload&&payload.schedule?payload.schedule:{};const result=schedule.last_result||payload&&payload.result||null;const statusNode=document.getElementById('cleanupStatus'),meta=document.getElementById('cleanupMeta'),details=document.getElementById('cleanupDetailsBody');const enabled=!!schedule.enabled,running=!!schedule.running,hasError=!!schedule.last_error;statusNode.className='health-status-chip '+(hasError?'health-critical':enabled?'health-ok':'health-neutral');statusNode.textContent=running?'Running':hasError?'Error':enabled?'Enabled':'Disabled';document.getElementById('cleanupNextRun').textContent=schedule.next_run?healthTime(schedule.next_run):'—';document.getElementById('cleanupLastRun').textContent=schedule.last_run?healthTime(schedule.last_run):'—';document.getElementById('cleanupDeleted').textContent=result&&result.deleted_count!==undefined?result.deleted_count:'—';document.getElementById('cleanupFailed').textContent=result&&result.failed_count!==undefined?result.failed_count:'—';let line=enabled?('Daily '+(schedule.time||'')):'Automatic cleanup disabled';if(schedule.next_run)line+=' · next '+healthTime(schedule.next_run);if(schedule.last_trigger)line+=' · last '+schedule.last_trigger;if(schedule.last_error)line+=' · '+schedule.last_error;meta.textContent=line;details.textContent='';if(!result){details.textContent='No cleanup has run yet. Use “Run cleanup now” to test the guarded cleanup path.';return}const summary=document.createElement('p');summary.textContent=`Checked ${result.scanned??0} rules · eligible ${result.eligible??0} · deleted ${result.deleted_count??0} · failed ${result.failed_count??0}`;details.appendChild(summary);const deleted=Array.isArray(result.deleted)?result.deleted:[];if(deleted.length){const h=document.createElement('strong');h.textContent='Deleted';const list=document.createElement('ul');list.className='health-list';deleted.forEach(item=>{const li=document.createElement('li');li.textContent=`${item.name||'One-time rule'} (appId ${item.appId||'?'})`;list.appendChild(li)});details.append(h,list)}const failed=Array.isArray(result.failed)?result.failed:[];if(failed.length){const h=document.createElement('strong');h.textContent='Failed';const list=document.createElement('ul');list.className='health-list';failed.forEach(item=>{const li=document.createElement('li');li.textContent=`${item.name||'One-time rule'} (appId ${item.appId||'?'}) — ${item.error||'failed'}`;list.appendChild(li)});details.append(h,list)}if(result.list_error){const error=document.createElement('p');error.className='health-critical';error.textContent=result.list_error;details.appendChild(error)}}
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
async function loadOneTimeCleanup(){try{renderOneTimeCleanup(await jsonResponse(await fetch(apiPath('api/one-time-rule-cleanup'))))}catch(error){console.warn('One-time cleanup status unavailable',error);document.getElementById('cleanupMeta').textContent='Cleanup status unavailable: '+error.message}}
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
  query.value='';answer.classList.remove('busy');answer.textContent='Ready for a new topic.';
  document.getElementById('lastRoute').textContent='—';
  document.getElementById('lastTime').textContent='—';query.focus();
}
document.getElementById('resetContext').onclick=resetConversation;

function firmwareUpdateAvailable(data,rawMessage){if(data?.update_available===true)return true;const evidence=Array.isArray(data?.evidence)?data.evidence:[];if(evidence.some(item=>item?.update_available===true||item?.data?.update_available===true||item?.result?.update_available===true))return true;return /\bfirmware update is available\b/i.test(rawMessage)||/\bhub firmware\s+\S+\s+is installed and\s+\S+\s+is available\b/i.test(rawMessage)}
function choicePrompt(question,choice){const original=String(question||'').trim();const directAction=original.match(/^\s*(?:please\s+)?(turn\s+on|turn\s+off|toggle)\b/i)?.[1]||original.match(/^\s*(?:can|could|would|will)\s+you\s+(?:please\s+)?(turn\s+on|turn\s+off|toggle)\b/i)?.[1]||'';if(directAction)return `${directAction} ${choice}`;const attribute=original.match(/\b(temperature|humidity|battery|power)\b/i)?.[1]||'';if(attribute)return `What is the ${choice} ${attribute}?`;return original?`${original} Device clarification: use exactly ${choice}.`:choice}
function showAnswer(data){answer.replaceChildren();const meta=document.createElement('div');meta.className='answer-meta';const outcome=data.outcome_presentation;if(outcome&&['positive','warning','neutral','critical'].includes(outcome.tone)&&typeof outcome.label==='string'&&outcome.label){const outcomeBadge=document.createElement('span');outcomeBadge.className=`badge outcome-badge outcome-${outcome.tone}`;outcomeBadge.textContent=outcome.label;meta.appendChild(outcomeBadge)}[data.route,data.model_tier_requested&&data.model_tier_requested!=='auto'?'Selected '+data.model_tier_requested:null,data.model,data.elapsed_ms===undefined?null:`${(data.elapsed_ms/1000).toFixed(1)}s`].filter(Boolean).forEach(value=>{const badge=document.createElement('span');badge.className='badge';badge.textContent=value;meta.appendChild(badge)});if(meta.children.length)answer.appendChild(meta);if(data.model_usage){const parts=[];const names=data.model_usage.models||{};for(const [name,n] of Object.entries(names)){if(n>0){const short=/deepseek/i.test(name)?'DeepSeek Pro':/claude/i.test(name)?'Claude':/gemma/i.test(name)?'Gemma':name;parts.push(short+': '+n)}}if(parts.length){const usage=document.createElement('span');usage.className='badge';usage.textContent=parts.join(' · ');meta.appendChild(usage);if(!meta.isConnected)answer.appendChild(meta)}}const rawMessage=data.message||data.detail||'No response';const text=renderMessage(rawMessage);answer.appendChild(text);if(data.route==='automation-status'&&Array.isArray(data.automation_items)&&data.automation_items.length)answer.appendChild(renderAutomationItems(data));if(Array.isArray(data.choices)){const originalQuestion=query.value.trim();data.choices.forEach(choice=>{const option=document.createElement('button');option.className='confirm';option.textContent=choice;option.onclick=()=>submit(choicePrompt(originalQuestion,choice));answer.appendChild(option)})}suggestedAction=firmwareUpdateAvailable(data,rawMessage)?'firmware-update':null;if(suggestedAction==='firmware-update'){const install=document.createElement('button');install.className='confirm';install.textContent='Update hub firmware';install.onclick=()=>submit('Install the available Hubitat firmware update');answer.appendChild(install)}if(data.confirmation_required===true){const confirm=document.createElement('button');confirm.className='confirm';confirm.textContent='Confirm action';confirm.onclick=()=>submit('confirm');answer.appendChild(confirm)}const audioButton=document.createElement('button');audioButton.className='secondary copy-button audio-button';audioButton.textContent='🔊 Read answer';audioButton.onclick=()=>{if(activeSpeech||nativeSpeechActive)stopAudio();else void speakAnswer(rawMessage,audioButton)};answer.appendChild(audioButton);const copy=document.createElement('button');copy.className='secondary copy-button';copy.textContent='Copy answer';copy.onclick=()=>copyText(rawMessage,copy,'Copy answer');answer.appendChild(copy);const details=document.createElement('details');details.className='technical';const summary=document.createElement('summary');summary.textContent='Technical details';const technical=JSON.stringify(data,null,2);const technicalCopy=document.createElement('button');technicalCopy.className='secondary copy-button technical-copy';technicalCopy.textContent='Copy technical';technicalCopy.onclick=event=>{event.preventDefault();copyText(technical,technicalCopy,'Copy technical')};const pre=document.createElement('pre');pre.textContent=technical;details.append(summary,technicalCopy,pre);answer.appendChild(details);document.getElementById('lastRoute').textContent=data.route||'—';document.getElementById('lastTime').textContent=data.elapsed_ms===undefined?'—':`${(data.elapsed_ms/1000).toFixed(1)}s`;if(readAnswers&&speechText(rawMessage).length<1500)void speakAnswer(rawMessage,audioButton)}
async function status(){try{const data=await jsonResponse(await fetch(apiPath('api/status')));pill('mcp',data.mcp?.online,data.mcp?.online?'MCP online':`MCP offline · ${data.mcp?.error||'unavailable'}`);pill('ollama',data.ollama?.configured,data.ollama?.configured?'Ollama ready':'Ollama API key required');const paidOption=modelTier.querySelector('option[value="paid"]');if(paidOption)paidOption.disabled=data.paid_routing?.enabled===false;const claudeOption=modelTier.querySelector('option[value="claude"]');if(claudeOption)claudeOption.disabled=data.claude?.configured!==true;if((modelTier.value==='paid'&&paidOption?.disabled)||(modelTier.value==='claude'&&claudeOption?.disabled))modelTier.value='free';describeModelTier();document.getElementById('tools').textContent=data.mcp?.tools??'—';document.getElementById('model').textContent=data.ollama?.model||'—'}catch(error){pill('mcp',false,'Status error · '+error.message)}try{const dash=await jsonResponse(await fetch(apiPath('api/dashboard')));document.getElementById('dashLights').textContent=dash.lights_on??'—';document.getElementById('dashMotion').textContent=dash.motion_active??'—';document.getElementById('dashBatteries').textContent=dash.low_batteries??'—';const active=dash.active_rooms||[];const loaded=[dash.lights_on,dash.motion_active,dash.low_batteries].some(value=>value!=null);document.getElementById('dashActiveRooms').textContent=loaded?active.length:'—';document.getElementById('dashActiveRoomNames').textContent=loaded?(active.length?active.map(room=>room.name).join(', '):'No motion or lights on'):'Loading live states…'}catch(error){console.warn('Dashboard unavailable',error)}loadHealthAudit();loadOneTimeCleanup();loadJournal()}
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
  text=(text||query.value).trim();if(!text)return;
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
    const response=await fetch(apiPath('api/ask'),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query:text,history,session_id:requestSessionId,request_id:requestId,model_tier:selectedTier}),
      signal:controller.signal,
    }).catch(error=>{
      if(error?.name==='AbortError')throw error;
      // A network/ingress disconnect is NOT evidence that a Hubitat
      // mutation failed. The backend may already have submitted a write
      // before its HTTP response was lost. Never automatically retry.
      const failure=new Error(String(error?.message||'Network connection lost'));
      failure.name='HomeBrainNetworkError';
      throw failure;
    });
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
document.getElementById('refresh').onclick=async()=>{try{const data=await jsonResponse(await fetch(apiPath('api/refresh'),{method:'POST'}));answer.textContent=`MCP tools refreshed: ${data.tools}.`;status()}catch(error){answer.textContent='Refresh failed: '+error.message}};
document.getElementById('runHealthAudit').onclick=async()=>{const button=document.getElementById('runHealthAudit');button.disabled=true;button.textContent='🩺 Checking…';try{const data=await jsonResponse(await fetch(apiPath('api/health-audit/run'),{method:'POST'}));renderHealthAuditV2(data);document.getElementById('healthAuditDetails').open=true}catch(error){document.getElementById('healthAuditMeta').textContent='System check failed: '+error.message}finally{button.disabled=false;button.textContent='🩺 Run system check now'}};
document.getElementById('runOneTimeCleanup').onclick=async()=>{if(!window.confirm('Delete expired HomeBrain one-time rules now? Future and ordinary rules are excluded.'))return;const button=document.getElementById('runOneTimeCleanup');button.disabled=true;button.textContent='🧹 Cleaning…';try{const response=await fetch(apiPath('api/one-time-rule-cleanup/run'),{method:'POST'}),data=await jsonResponse(response);renderOneTimeCleanup(data);document.getElementById('cleanupDetails').open=true;if(!response.ok||!data.success)throw new Error(data.result?.list_error||data.detail||'Cleanup did not complete')}catch(error){document.getElementById('cleanupMeta').textContent='Cleanup failed: '+error.message}finally{button.disabled=false;button.textContent='🧹 Run cleanup now'}};
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
async function loadCloudBenchmarkStatus(){
  const note=document.getElementById('cloudBenchmarkAvailability');
  try{
    const response=await fetch(apiPath('api/cloud-benchmark/status'));
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error('Benchmark status unavailable');
    const model=data.model||'not configured';
    note.textContent=data.available?'Ready · Ollama Cloud model: '+model+' · Existing primary account.':(data.reason||'Cloud model unavailable.');
    document.getElementById('runCloudBenchmark').dataset.available=data.available?'yes':'no';
  }catch(_error){
    note.textContent='Benchmark status unavailable.';
    document.getElementById('runCloudBenchmark').dataset.available='no';
  }
  updateCloudBenchmarkButton();
}
function updateCloudBenchmarkButton(){
  const run=document.getElementById('runCloudBenchmark');
  run.disabled=run.dataset.available!=='yes'||!document.getElementById('cloudBenchmarkConsent').checked||run.dataset.running==='yes';
}
document.getElementById('cloudBenchmarkConsent').onchange=updateCloudBenchmarkButton;
document.getElementById('runCloudBenchmark').onclick=async()=>{
  const button=document.getElementById('runCloudBenchmark');
  const view=document.getElementById('cloudBenchmarkResult');
  if(button.disabled||!document.getElementById('cloudBenchmarkConsent').checked)return;
  button.dataset.running='yes';updateCloudBenchmarkButton();
  view.textContent='Testing your configured cloud model using fictional evidence…';
  try{
    const response=await fetch(apiPath('api/cloud-benchmark/run'),{
      method:'POST',headers:{'Content-Type':'application/json','X-HomeBrain-Benchmark':'confirmed'},
      body:JSON.stringify({case_id:document.getElementById('cloudBenchmarkCase').value,confirm_cloud_allowance:true})
    });
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Cloud test failed (HTTP '+response.status+')');
    view.replaceChildren();
    const heading=document.createElement('strong');
    heading.textContent=data.title+' · '+data.checks_correct+'/'+data.checks_total+' evidence checks correct · '+(data.elapsed_ms/1000).toFixed(1)+'s';
    view.append(heading);
    const info=document.createElement('p');
    info.textContent='Model: '+data.model+' · Unsupported conclusions wrongly accepted: '+data.unsupported_conclusions_wrongly_accepted+'/'+data.unsupported_conclusions_total+'.';
    view.append(info);
    const natural=document.createElement('p');
    natural.textContent='AI explanation (not independently fact-checked): '+data.explanation;
    view.append(natural);
    const rows=document.createElement('details');rows.className='technical';
    const summary=document.createElement('summary');summary.textContent='View independent synthetic claim checks';rows.append(summary);
    for(const check of data.evidence_checks||[]){
      const item=document.createElement('div');item.className='benchmark-check';
      item.textContent=(check.correct?'✓ ':'✕ ')+check.statement+' · AI: '+check.model_verdict.replace('_',' ')+' · Expected: '+check.expected_verdict.replace('_',' ');
      rows.append(item);
    }
    view.append(rows);
    const limit=document.createElement('p');limit.className='muted';
    limit.textContent='This scores predefined synthetic evidence classifications only. It does not prove prose accuracy, investigation completeness, or readiness to replace HomeBrain answers. No devices were touched.';
    view.append(limit);
  }catch(error){view.textContent='Cloud benchmark unavailable: '+error.message}
  finally{
    document.getElementById('cloudBenchmarkConsent').checked=false;
    button.dataset.running='no';updateCloudBenchmarkButton();
  }
};
loadCloudBenchmarkStatus();

function stage5RefreshButton(){
  const b=document.getElementById('runStage5');
  b.disabled=b.dataset.available!=='yes'||b.dataset.running==='yes'||!document.getElementById('stage5Consent').checked;
}
async function loadStage5Status(){
  const b=document.getElementById('runStage5'),out=document.getElementById('stage5Availability');
  try{
    const response=await fetch(apiPath('api/stage5-benchmark/status'));
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error('Unavailable');
    b.dataset.available=data.available?'yes':'no';
    out.textContent=data.available?'Ready · '+data.model+' · existing primary account':(data.reason||'Not available');
  }catch(_error){b.dataset.available='no';out.textContent='Cloud status could not be checked.'}
  stage5RefreshButton();
}
document.getElementById('stage5Consent').onchange=stage5RefreshButton;
document.getElementById('runStage5').onclick=async()=>{
  const b=document.getElementById('runStage5'),out=document.getElementById('stage5Report');
  if(b.disabled||!document.getElementById('stage5Consent').checked)return;
  b.dataset.running='yes';stage5RefreshButton();out.textContent='Gemma is choosing fictional evidence and writing its own conclusion…';
  try{
    const response=await fetch(apiPath('api/stage5-benchmark/run'),{
      method:'POST',
      headers:{'Content-Type':'application/json','X-HomeBrain-Benchmark':'confirmed'},
      body:JSON.stringify({case_id:document.getElementById('stage5Scenario').value,confirm_cloud_allowance:true})
    });
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Independent benchmark failed (HTTP '+response.status+')');
    out.replaceChildren();
    const heading=document.createElement('strong');
    heading.textContent=data.title+' · '+(data.elapsed_ms/1000).toFixed(1)+'s · '+data.cloud_requests_attempted+' cloud requests';
    out.append(heading);
    const explanation=document.createElement('p');
    explanation.textContent='AI explanation (not independently verified): '+data.answer;out.append(explanation);
    const review=document.createElement('p');review.textContent=
      'Relevant source discovery: '+data.relevant_source_recall+
      ' · Irrelevant sources selected: '+data.irrelevant_source_selections+
      ' · Expected factual findings supported: '+data.required_finding_coverage+
      ' · Unsupported cited findings: '+data.unsupported_cited_findings+
      ' (high-risk: '+data.high_risk_unsupported_findings+').';
    out.append(review);
    const details=document.createElement('details');
    const summary=document.createElement('summary');summary.textContent='Source decisions and cited finding checks';details.append(summary);
    for(const choice of data.source_choices||[]){
      const row=document.createElement('p');
      row.textContent=(choice.expected_relevance?'✓ Relevant: ':'✕ Not in reference: ')+choice.source_id;
      details.append(row);
    }
    for(const claim of data.findings||[]){
      const row=document.createElement('p');
      row.textContent=(claim.host_source_proven?'✓ Source-backed: ':'✕ Unsupported citation: ')+claim.kind.replace(/_/g,' ')+' · '+claim.source_ids.join(', ');
      details.append(row);
    }
    if(data.uncovered_expected_finding_types?.length){
      const row=document.createElement('p');
      row.textContent='Expected finding types not established in cited output: '+data.uncovered_expected_finding_types.join(', ');
      details.append(row);
    }
    out.append(details);
    const limits=document.createElement('p');limits.textContent='Uncertainties: '+(data.limitations||[]).join(' · ');out.append(limits);
    const note=document.createElement('p');note.className='stage5-note';
    note.textContent='Stage 5 is a synthetic source-selection and typed-citation pilot. It cannot certify that the natural-language answer is complete, true or Claude-equivalent. No devices were touched.';
    out.append(note);
    const human=document.createElement('div');human.className='stage5-review';
    const heading2=document.createElement('span');heading2.textContent='Optional personal review (not sent or saved):';human.append(heading2);
    for(const kind of ['Clarity','Usefulness']){
      const label=document.createElement('label');label.textContent=kind+' ';
      const select=document.createElement('select');select.setAttribute('aria-label',kind+' score');
      for(const [value,name] of [['','Not rated'],['1','1 Poor'],['2','2'],['3','3'],['4','4'],['5','5 Excellent']]){
        const option=document.createElement('option');option.value=value;option.textContent=name;select.append(option);
      }
      label.append(select);human.append(label);
    }
    out.append(human);
  }catch(error){out.textContent='Independent benchmark unavailable: '+error.message}
  finally{
    document.getElementById('stage5Consent').checked=false;
    b.dataset.running='no';stage5RefreshButton();
  }
};
loadStage5Status();

function stage6RefreshButton(){
  const b=document.getElementById('runStage6');
  b.disabled=b.dataset.available!=='yes'||b.dataset.running==='yes'||!document.getElementById('stage6Consent').checked;
}
async function loadStage6Status(){
  const b=document.getElementById('runStage6'),note=document.getElementById('stage6Availability');
  try{
    const r=await fetch(apiPath('api/stage6-benchmark/status'));
    const data=await jsonResponse(r);
    if(!r.ok)throw new Error('Unavailable');
    b.dataset.available=data.available?'yes':'no';
    note.textContent=data.available?'Configured (not yet authenticated) · '+data.model+' · existing cloud account':(data.reason||'Cloud unavailable');
  }catch(_error){b.dataset.available='no';note.textContent='Cloud status unavailable.'}
  stage6RefreshButton();
}
document.getElementById('stage6Consent').onchange=stage6RefreshButton;
document.getElementById('runStage6').onclick=async()=>{
  const b=document.getElementById('runStage6'),out=document.getElementById('stage6Report');
  if(b.disabled||!document.getElementById('stage6Consent').checked)return;
  b.dataset.running='yes';stage6RefreshButton();
  out.textContent='Gemma is inspecting fictional sources, reconsidering missing evidence and preparing an explanation…';
  try{
    const response=await fetch(apiPath('api/stage6-benchmark/run'),{
      method:'POST',
      headers:{'Content-Type':'application/json','X-HomeBrain-Benchmark':'confirmed'},
      body:JSON.stringify({case_id:document.getElementById('stage6Scenario').value,confirm_cloud_allowance:true})
    });
    const data=await jsonResponse(response);
    if(!response.ok && data.partial_investigation){
      const partial=data.partial_investigation;
      out.replaceChildren();
      const heading=document.createElement('strong');
      heading.textContent='Final explanation rejected — source investigation preserved';
      out.append(heading);
      const reason=document.createElement('p');
      reason.textContent=(typeof data.detail==='string'?data.detail:'Stage 6 final answer failed validation.')+
        ' Validation category: '+(data.validation_category||'unclassified')+'.';
      out.append(reason);
      const selection=document.createElement('p');
      selection.textContent='Previously selected fictional sources: '+
        ((partial.selected_source_ids||[]).join(', ')||'none')+
        ' · Reference-relevant: '+partial.relevant_reference_sources_selected+
        '/'+partial.relevant_reference_sources_available+
        ' · Irrelevant: '+partial.irrelevant_sources_selected+
        ' · Cloud attempts: '+partial.attempted_cloud_requests+'.';
      out.append(selection);
      const quality=document.createElement('p');
      quality.textContent='Planning review complete: '+(partial.planning_contract_complete?'yes':'no')+
        ' · Model-ranking inconsistencies: '+partial.model_ranking_consistency_failures+
        ' · Planning issues: '+((partial.planning_contract_issue_codes||[]).join(', ')||'none recorded')+'.';
      out.append(quality);
      const disclaimer=document.createElement('p');disclaimer.className='stage5-note';
      disclaimer.textContent='No final AI explanation was published or fact-checked. These are only synthetic source-selection results from completed steps. No cloud retry or live device access occurred.';
      out.append(disclaimer);
      return;
    }
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Cloud test failed (HTTP '+response.status+')');
    out.replaceChildren();
    const heading=document.createElement('strong');
    heading.textContent=data.title+' · '+(data.elapsed_ms/1000).toFixed(1)+'s · '+data.cloud_requests_attempted+' cloud requests';
    out.append(heading);
    const answer=document.createElement('p');answer.textContent='Model-authored explanation (not fully fact-checked): '+data.answer;out.append(answer);
    const metrics=document.createElement('p');metrics.textContent=
      'Relevant sources examined: '+data.relevant_source_recall+
      ' · Irrelevant sources: '+data.irrelevant_sources_selected+
      ' · Expected finding-type coverage: '+data.expected_finding_type_coverage+
      ' · Source-type mismatches: '+data.source_type_mismatches+
      ' · Other unsupported source types: '+data.unmatched_source_types_other+
      ' (high risk: '+data.high_risk_unsupported_sentences+')'+
      ' · Cited source-value atoms: '+data.source_value_atoms_verified+
      ' matched / '+data.source_value_atoms_mismatched+' mismatched.';out.append(metrics);
    const stop=document.createElement('p');stop.textContent=
      'Gemma examined '+data.requested_source_reads+' additional records; stopped: '+
      data.stop_reason.replace(/_/g,' ')+(data.premature_stop_missing_relevant_sources?' · Some reference-relevant evidence was not inspected.':'')+
      (data.model_stop_justification?' · Model reason: '+data.model_stop_justification:'');
    out.append(stop);
    const coverage=document.createElement('p');
    coverage.textContent='Evidence-value review: '+
      (data.stop_source_value_review_complete?
       'Model evaluated every unread source against the original question.':
       'Legacy/incomplete source-value ledger; stopping quality NOT established.')+
      ' Open questions after the last plan: '+(data.stop_unresolved_questions||[]).length+
      '. Source gain rankings and question status are model-authored, not independently proven.';
    out.append(coverage);
    const planQuality=document.createElement('p');
    planQuality.textContent=data.planning_contract_complete?
      'Planning contract: complete and structurally consistent.':
      'Planning contract: incomplete or unaudited; do not interpret source decisions as fully reviewed. '+(data.planning_contract_issues||[]).join(', ');
    out.append(planQuality);
    const questionQuality=document.createElement('p');
    questionQuality.textContent='Question/value audit: '+
      (data.model_question_value_audit?'Complete model-authored question-linked source appraisal.':
       'Incomplete or legacy question-linked appraisal; not certified.')+
      ' Inconsistent source-rank choices: '+data.model_ranking_consistency_failures+
      '. Ranking accuracy is assessed separately by host-held source relevance.';
    out.append(questionQuality);
    const sourceLedger=document.createElement('details');
    const sourceLedgerTitle=document.createElement('summary');
    sourceLedgerTitle.textContent='Unanswered questions and per-source value assessments';
    sourceLedger.append(sourceLedgerTitle);
    for(const review of data.source_value_review||[]){
      const step=document.createElement('p');
      step.textContent='Decision '+review.step+' · '+review.action+
        ' · '+(review.source_value_coverage_complete?'Every unread title assessed':'Incomplete/legacy source-value audit')+
        (review.planning_contract_issues?.length?' · Audit issues: '+review.planning_contract_issues.join(', '):'');
      sourceLedger.append(step);
      const questionReview=review.question_value_review||{};
      for(const question of questionReview.model_questions||[]){
        const q=document.createElement('p');
        q.textContent=question.id+' · '+question.status+' · '+question.question;sourceLedger.append(q);
      }
      if(!questionReview.model_questions?.length){
        for(const question of review.open_questions||[]){
          const q=document.createElement('p');q.textContent='Open question: '+question;sourceLedger.append(q);
        }
      }
      if(questionReview.model_ranking_consistent===false){
        const risk=document.createElement('p');
        risk.textContent='Model selected a source that its own information-gain ranking placed below another unread source.';
        sourceLedger.append(risk);
      }
      for(const item of review.model_assessed_sources||[]){
        const row=document.createElement('p');
        row.textContent=(item.information_gain?
          'Model gain '+item.information_gain+' for '+(item.question_ids||[]).join(', ')+': ':
          (item.could_change_answer?'Potentially useful: ':'Assessed low value: '))+
          item.source_id+' · '+item.reason;
        sourceLedger.append(row);
      }
    }
    out.append(sourceLedger);
    const details=document.createElement('details');
    const summary=document.createElement('summary');summary.textContent='Read sequence and sentence-level source checks';details.append(summary);
    for(const item of data.selected_sources||[]){
      const line=document.createElement('p');
      line.textContent=(item.relevant_reference_source?'✓ Relevant: ':'✕ Reference-irrelevant: ')+item.id;
      details.append(line);
    }
    for(const sent of data.sentence_citation_checks||[]){
      const line=document.createElement('p');
      const verdict=sent.typed_source_supported?'✓ Source type matches: ':
        sent.source_type_mismatch?'△ Source label mismatch (not a proven false fact): ':
        '✕ Citation type unsupported: ';
      const atoms=(sent.atomic_source_value_checks||[]).map(a=>
        (a.exact_source_value_match?'✓ ':'✕ ')+a.record_id+'.'+a.field).join(' · ');
      line.textContent=verdict+sent.kind.replace(/_/g,' ')+
        ' ['+sent.evidence_ids.join(', ')+'] · '+sent.text+
        (atoms?' · Exact source-value checks: '+atoms:' · No source-value atoms checked');
      details.append(line);
    }
    if(data.missing_expected_finding_types?.length){
      const missing=document.createElement('p');
      missing.textContent='Reference finding types missing: '+data.missing_expected_finding_types.join(', ');details.append(missing);
    }
    out.append(details);
    const uncertainty=document.createElement('p');
    uncertainty.textContent='Uncertainties: '+(data.uncertainties||[]).join(' · ');out.append(uncertainty);
    const next=document.createElement('p');
    next.textContent='AI-suggested next evidence (not verified): '+data.recommended_next_evidence;out.append(next);
    const warning=document.createElement('p');warning.className='stage5-note';
    warning.textContent='A mismatched source type is not automatically a false fact. Exact atom checks compare model-supplied field/value assertions with cited records; they do NOT verify all wording or hidden implications. The model may still omit important evidence. Independent human review is needed; this cannot enable the production publisher.';
    out.append(warning);
    // Stage 7: independent, *manual* full-prose review, never model-certified.
    // All source records are constructed fiction and the full corpus is
    // revealed only AFTER the model has chosen sources and authored its answer.
    const reviewPacket=data.independent_review_packet;
    if(reviewPacket?.schema==='homebrain-stage7-review.v1'){
      const panel=document.createElement('details');
      const panelTitle=document.createElement('summary');
      panelTitle.textContent='Stage 7 · Independently review every sentence';
      panel.append(panelTitle);
      const notice=document.createElement('p');notice.className='stage5-note';
      notice.textContent='Read the complete fictional source records, including evidence Gemma skipped. Decide whether EACH sentence is supported and whether the whole explanation omits important facts. These are your judgments, not automatic AI-verification scores. Nothing is saved or uploaded.';
      panel.append(notice);
      const sourceDetail=document.createElement('details');
      const sourceSummary=document.createElement('summary');
      sourceSummary.textContent='Full source packet (including unread fictional records)';
      sourceDetail.append(sourceSummary);
      for(const source of reviewPacket.source_records||[]){
        const header=document.createElement('p');
        header.textContent=(source.was_selected_by_model?'Read by Gemma: ':'Not read by Gemma: ')+source.source_id+' · '+source.title;
        sourceDetail.append(header);
        const sourceText=document.createElement('pre');
        sourceText.style.whiteSpace='pre-wrap';sourceText.style.overflowWrap='anywhere';
        sourceText.textContent=JSON.stringify(source.records,null,2);
        sourceDetail.append(sourceText);
      }
      panel.append(sourceDetail);
      const ratingControls=[];
      const choices=[['not_reviewed','Not reviewed'],['supported','Supported'],
        ['partially_supported','Partially supported'],
        ['unsupported','Unsupported'],['uncertain','Unclear / evidence missing']];
      for(const sentence of reviewPacket.author_sentences||[]){
        const group=document.createElement('div');group.className='stage5-review';
        const sentenceText=document.createElement('p');
        sentenceText.textContent='Sentence '+sentence.number+': '+sentence.text;
        group.append(sentenceText);
        const label=document.createElement('label');label.textContent='Your factual assessment: ';
        const rating=document.createElement('select');
        rating.setAttribute('aria-label','Sentence '+sentence.number+' factual review');
        for(const [v,t] of choices){
          const opt=document.createElement('option');opt.value=v;opt.textContent=t;rating.append(opt);
        }
        label.append(rating);group.append(label);panel.append(group);
        ratingControls.push({number:sentence.number,element:rating});
      }
      const overall=document.createElement('div');overall.className='stage5-review';
      const fields=[
        ['Overall completeness', [['not_reviewed','Not reviewed'],['adequate','Adequate'],['important_omissions','Important omissions'],['insufficient_information','Insufficient source coverage']]],
        ['Causal caution', [['not_reviewed','Not reviewed'],['appropriate','Appropriately cautious'],['overclaims','Overconfident causation'],['uncertain','Uncertain']]],
      ];
      const overallControls=[];
      for(const [name,options] of fields){
        const label=document.createElement('label');label.textContent=name+': ';
        const select=document.createElement('select');select.setAttribute('aria-label',name);
        for(const [value,title] of options){
          const opt=document.createElement('option');opt.value=value;opt.textContent=title;select.append(opt);
        }
        label.append(select);overall.append(label);
        overallControls.push(select);
      }
      panel.append(overall);
      const copy=document.createElement('button');copy.type='button';
      copy.className='secondary copy-button';
      copy.textContent='Copy independent review packet';
      copy.onclick=()=>{
        const review={
          per_sentence:ratingControls.map(item=>({
            sentence_number:item.number,reviewer_verdict:item.element.value
          })),
          overall_completeness:overallControls[0].value,
          causal_caution:overallControls[1].value,
          independently_reviewed_by_human:ratingControls.every(item=>
            item.element.value!=='not_reviewed')&&
            overallControls.every(item=>item.value!=='not_reviewed'),
        };
        const exportText=JSON.stringify({
          fictional_evidence_and_model_answer:reviewPacket,
          optional_manual_review:review,
          automatic_semantic_certification:false,
          production_publication_approval:false,
        },null,2);
        void copyText(exportText,copy,'Copy independent review packet');
      };
      panel.append(copy);
      out.append(panel);
    }
  }catch(error){out.textContent='Stage 6 unavailable: '+error.message}
  finally{document.getElementById('stage6Consent').checked=false;b.dataset.running='no';stage6RefreshButton()}
};
document.getElementById('checkCloudConnection').onclick=async()=>{
  const button=document.getElementById('checkCloudConnection');
  const output=document.getElementById('cloudConnectionResult');
  if(button.disabled)return;
  button.disabled=true;output.textContent='Checking Ollama account access without running any model…';
  try{
    const response=await fetch(apiPath('api/cloud-connection/check'),{
      method:'POST',
      headers:{'Content-Type':'application/json','X-HomeBrain-Benchmark':'confirmed'},
      body:'{}'
    });
    const data=await jsonResponse(response);
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Connection check failed');
    output.textContent=(data.http_status===null?'Network check: ':'Provider HTTP '+data.http_status+' · ')+
      data.guidance+' No model inference was requested.';
  }catch(error){output.textContent='Connection diagnostic unavailable: '+error.message}
  finally{button.disabled=false}
};
loadStage6Status();



status();setInterval(status,30000);
</script></body></html>"""
        .replace("__SAFE_TITLE__", safe_title)
        .replace("__TITLE__", title_json)
        .replace("__VERSION__", version_json)
    )


__all__ = ["render_page"]
