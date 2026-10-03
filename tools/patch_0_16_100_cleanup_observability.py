from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor not unique in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- scheduler/service observability + manual run ---
path = "hubitat-mcp-ai/rootfs/app/one_time_rule_cleanup.py"
replace_once(
    path,
    """    list_error: str | None = None\n\n\nclass OneTimeRuleCleanupService:\n""",
    """    list_error: str | None = None\n\n    def as_dict(self) -> dict[str, Any]:\n        return {\n            \"checked_at\": self.checked_at,\n            \"scanned\": self.scanned,\n            \"eligible\": self.eligible,\n            \"deleted\": list(self.deleted),\n            \"deleted_count\": len(self.deleted),\n            \"failed\": list(self.failed),\n            \"failed_count\": len(self.failed),\n            \"list_error\": self.list_error,\n        }\n\n\nclass OneTimeRuleCleanupService:\n""",
)
replace_once(
    path,
    """        self._task: asyncio.Task[Any] | None = None\n        self.next_run: str | None = None\n        self.last_result: OneTimeRuleCleanupResult | None = None\n\n    def start(self) -> None:\n        if not self.enabled or self._task is not None:\n            return\n        self._task = asyncio.create_task(self._run(), name=\"homebrain-one-time-rule-cleanup\")\n""",
    """        self._task: asyncio.Task[Any] | None = None\n        self._run_lock = asyncio.Lock()\n        self.next_run: str | None = None\n        self.last_run: str | None = None\n        self.last_trigger: str | None = None\n        self.last_result: OneTimeRuleCleanupResult | None = None\n\n    def status(self) -> dict[str, Any]:\n        return {\n            \"enabled\": self.enabled,\n            \"time\": self.daily_time,\n            \"next_run\": self.next_run,\n            \"last_run\": self.last_run,\n            \"last_trigger\": self.last_trigger,\n            \"last_error\": self.last_error,\n            \"running\": self._run_lock.locked(),\n            \"task_active\": bool(self._task is not None and not self._task.done()),\n            \"last_result\": self.last_result.as_dict() if self.last_result else None,\n        }\n\n    async def run_now(self) -> OneTimeRuleCleanupResult:\n        \"\"\"Run the same guarded cleanup path immediately on explicit request.\"\"\"\n        return await self._run_once(trigger=\"manual\")\n\n    def start(self) -> None:\n        if not self.enabled:\n            logger.info(\"One-time cleanup scheduler disabled\")\n            return\n        if self._task is not None:\n            return\n        logger.info(\n            \"One-time cleanup scheduler started: daily_time=%s grace_minutes=%s\",\n            self.daily_time,\n            self.service.grace_minutes,\n        )\n        self._task = asyncio.create_task(self._run(), name=\"homebrain-one-time-rule-cleanup\")\n""",
)
replace_once(
    path,
    """    async def _run_once(self) -> None:\n        try:\n            self.last_result = await self.service.run()\n            self.last_error = self.last_result.list_error\n        except asyncio.CancelledError:\n            raise\n        except Exception as exc:\n            self.last_error = f\"{type(exc).__name__}: {str(exc)[:300]}\"\n            logger.exception(\"Scheduled one-time rule cleanup failed\")\n\n    async def _run(self) -> None:\n""",
    """    async def _run_once(self, *, trigger: str) -> OneTimeRuleCleanupResult:\n        async with self._run_lock:\n            logger.info(\"One-time cleanup starting: trigger=%s\", trigger)\n            try:\n                result = await self.service.run()\n            except asyncio.CancelledError:\n                raise\n            except Exception as exc:\n                self.last_error = f\"{type(exc).__name__}: {str(exc)[:300]}\"\n                self.last_trigger = trigger\n                logger.exception(\"One-time rule cleanup failed: trigger=%s\", trigger)\n                raise\n\n            self.last_result = result\n            self.last_run = result.checked_at\n            self.last_trigger = trigger\n            self.last_error = result.list_error\n            logger.info(\n                \"One-time cleanup completed: trigger=%s scanned=%s eligible=%s deleted=%s failed=%s list_error=%s\",\n                trigger,\n                result.scanned,\n                result.eligible,\n                len(result.deleted),\n                len(result.failed),\n                result.list_error or \"none\",\n            )\n            return result\n\n    async def _run(self) -> None:\n""",
)
replace_once(
    path,
    """                self.next_run = target.isoformat()\n                delay = max(1.0, (target - now).total_seconds())\n                await asyncio.sleep(delay)\n                await self._run_once()\n                self.next_run = None\n""",
    """                self.next_run = target.isoformat()\n                logger.info(\n                    \"One-time cleanup next run: configured_time=%s next_run=%s\",\n                    self.daily_time,\n                    self.next_run,\n                )\n                delay = max(1.0, (target - now).total_seconds())\n                await asyncio.sleep(delay)\n                await self._run_once(trigger=\"scheduled\")\n                self.next_run = None\n""",
)

# --- API status + manual-run endpoint ---
path = "hubitat-mcp-ai/rootfs/app/app.py"
replace_once(
    path,
    """        \"tts\": home_assistant_tts.status(),\n    }\n""",
    """        \"tts\": home_assistant_tts.status(),\n        \"one_time_rule_cleanup\": one_time_rule_cleanup_scheduler.status(),\n    }\n""",
)
replace_once(
    path,
    """@app.post(\"/api/tts\")\nasync def speak_tts(payload: TTSRequest, request: Request) -> dict[str, Any]:\n""",
    """@app.get(\"/api/one-time-rule-cleanup\")\nasync def one_time_rule_cleanup_status() -> dict[str, Any]:\n    return {\n        \"success\": True,\n        \"schedule\": one_time_rule_cleanup_scheduler.status(),\n    }\n\n\n@app.post(\"/api/one-time-rule-cleanup/run\")\nasync def run_one_time_rule_cleanup() -> dict[str, Any]:\n    try:\n        result = await request_coordinator.run(\n            \"one-time-rule-cleanup\",\n            one_time_rule_cleanup_scheduler.run_now(),\n        )\n    except Exception as exc:\n        logger.exception(\"Manual one-time rule cleanup failed\")\n        raise HTTPException(status_code=502, detail=str(exc)) from exc\n    payload = result.as_dict()\n    return {\n        \"success\": not bool(result.list_error),\n        \"result\": payload,\n        \"schedule\": one_time_rule_cleanup_scheduler.status(),\n    }\n\n\n@app.post(\"/api/tts\")\nasync def speak_tts(payload: TTSRequest, request: Request) -> dict[str, Any]:\n""",
)

# --- Web UI card, live status and explicit manual-run button ---
path = "hubitat-mcp-ai/rootfs/app/webui.py"
replace_once(
    path,
    """</section>\n<p class=\"muted\">Powered by Ollama Online native function calling and Hubitat MCP.</p>\n""",
    """</section>\n<section class=\"card\" id=\"oneTimeCleanupCard\">\n<div><div class=\"health-heading\"><strong>One-time rule cleanup</strong><span class=\"health-status-chip health-neutral\" id=\"cleanupStatus\">Loading</span></div><div class=\"muted\" id=\"cleanupMeta\">Loading cleanup scheduler…</div></div>\n<div class=\"health-grid\">\n<div class=\"health-stat\"><div class=\"big\" id=\"cleanupNextRun\">—</div><div class=\"muted\">Next run</div></div>\n<div class=\"health-stat\"><div class=\"big\" id=\"cleanupLastRun\">—</div><div class=\"muted\">Last run</div></div>\n<div class=\"health-stat\"><div class=\"big\" id=\"cleanupDeleted\">—</div><div class=\"muted\">Last deleted</div></div>\n<div class=\"health-stat\"><div class=\"big\" id=\"cleanupFailed\">—</div><div class=\"muted\">Last failed</div></div>\n</div>\n<div class=\"health-actions\"><button id=\"runOneTimeCleanup\">🧹 Run cleanup now</button></div>\n<details class=\"health-details\" id=\"cleanupDetails\"><summary>View cleanup details</summary><div id=\"cleanupDetailsBody\" class=\"muted\">No cleanup has run yet.</div></details>\n</section>\n<p class=\"muted\">Powered by Ollama Online native function calling and Hubitat MCP.</p>\n""",
)
replace_once(
    path,
    """async function loadHealthAudit(){try{renderHealthAuditV2(await jsonResponse(await fetch(apiPath('api/health-audit'))))}catch(error){console.warn('Health audit unavailable',error);document.getElementById('healthAuditMeta').textContent='System check unavailable: '+error.message}}\nfunction pill(id,ok,text){const node=document.getElementById(id);node.textContent=text;node.className='pill '+(ok?'ok':'error')}\n""",
    """async function loadHealthAudit(){try{renderHealthAuditV2(await jsonResponse(await fetch(apiPath('api/health-audit'))))}catch(error){console.warn('Health audit unavailable',error);document.getElementById('healthAuditMeta').textContent='System check unavailable: '+error.message}}\nfunction renderOneTimeCleanup(payload){const schedule=payload&&payload.schedule?payload.schedule:{};const result=schedule.last_result||payload&&payload.result||null;const statusNode=document.getElementById('cleanupStatus'),meta=document.getElementById('cleanupMeta'),details=document.getElementById('cleanupDetailsBody');const enabled=!!schedule.enabled,running=!!schedule.running,hasError=!!schedule.last_error;statusNode.className='health-status-chip '+(hasError?'health-critical':enabled?'health-ok':'health-neutral');statusNode.textContent=running?'Running':hasError?'Error':enabled?'Enabled':'Disabled';document.getElementById('cleanupNextRun').textContent=schedule.next_run?healthTime(schedule.next_run):'—';document.getElementById('cleanupLastRun').textContent=schedule.last_run?healthTime(schedule.last_run):'—';document.getElementById('cleanupDeleted').textContent=result&&result.deleted_count!==undefined?result.deleted_count:'—';document.getElementById('cleanupFailed').textContent=result&&result.failed_count!==undefined?result.failed_count:'—';let line=enabled?('Daily '+(schedule.time||'')):'Automatic cleanup disabled';if(schedule.next_run)line+=' · next '+healthTime(schedule.next_run);if(schedule.last_trigger)line+=' · last '+schedule.last_trigger;if(schedule.last_error)line+=' · '+schedule.last_error;meta.textContent=line;details.textContent='';if(!result){details.textContent='No cleanup has run yet. Use “Run cleanup now” to test the guarded cleanup path.';return}const summary=document.createElement('p');summary.textContent=`Checked ${result.scanned??0} rules · eligible ${result.eligible??0} · deleted ${result.deleted_count??0} · failed ${result.failed_count??0}`;details.appendChild(summary);const deleted=Array.isArray(result.deleted)?result.deleted:[];if(deleted.length){const h=document.createElement('strong');h.textContent='Deleted';const list=document.createElement('ul');list.className='health-list';deleted.forEach(item=>{const li=document.createElement('li');li.textContent=`${item.name||'One-time rule'} (appId ${item.appId||'?'})`;list.appendChild(li)});details.append(h,list)}const failed=Array.isArray(result.failed)?result.failed:[];if(failed.length){const h=document.createElement('strong');h.textContent='Failed';const list=document.createElement('ul');list.className='health-list';failed.forEach(item=>{const li=document.createElement('li');li.textContent=`${item.name||'One-time rule'} (appId ${item.appId||'?'}) — ${item.error||'failed'}`;list.appendChild(li)});details.append(h,list)}if(result.list_error){const error=document.createElement('p');error.className='health-critical';error.textContent=result.list_error;details.appendChild(error)}}\nasync function loadOneTimeCleanup(){try{renderOneTimeCleanup(await jsonResponse(await fetch(apiPath('api/one-time-rule-cleanup'))))}catch(error){console.warn('One-time cleanup status unavailable',error);document.getElementById('cleanupMeta').textContent='Cleanup status unavailable: '+error.message}}\nfunction pill(id,ok,text){const node=document.getElementById(id);node.textContent=text;node.className='pill '+(ok?'ok':'error')}\n""",
)
replace_once(
    path,
    """}catch(error){console.warn('Dashboard unavailable',error)}loadHealthAudit()}\n""",
    """}catch(error){console.warn('Dashboard unavailable',error)}loadHealthAudit();loadOneTimeCleanup()}\n""",
)
replace_once(
    path,
    """document.getElementById('runHealthAudit').onclick=async()=>{const button=document.getElementById('runHealthAudit');button.disabled=true;button.textContent='🩺 Checking…';try{const data=await jsonResponse(await fetch(apiPath('api/health-audit/run'),{method:'POST'}));renderHealthAuditV2(data);document.getElementById('healthAuditDetails').open=true}catch(error){document.getElementById('healthAuditMeta').textContent='System check failed: '+error.message}finally{button.disabled=false;button.textContent='🩺 Run system check now'}};\n""",
    """document.getElementById('runHealthAudit').onclick=async()=>{const button=document.getElementById('runHealthAudit');button.disabled=true;button.textContent='🩺 Checking…';try{const data=await jsonResponse(await fetch(apiPath('api/health-audit/run'),{method:'POST'}));renderHealthAuditV2(data);document.getElementById('healthAuditDetails').open=true}catch(error){document.getElementById('healthAuditMeta').textContent='System check failed: '+error.message}finally{button.disabled=false;button.textContent='🩺 Run system check now'}};\ndocument.getElementById('runOneTimeCleanup').onclick=async()=>{if(!window.confirm('Delete expired HomeBrain one-time rules now? Future and ordinary rules are excluded.'))return;const button=document.getElementById('runOneTimeCleanup');button.disabled=true;button.textContent='🧹 Cleaning…';try{const response=await fetch(apiPath('api/one-time-rule-cleanup/run'),{method:'POST'}),data=await jsonResponse(response);renderOneTimeCleanup(data);document.getElementById('cleanupDetails').open=true;if(!response.ok||!data.success)throw new Error(data.result?.list_error||data.detail||'Cleanup did not complete')}catch(error){document.getElementById('cleanupMeta').textContent='Cleanup failed: '+error.message}finally{button.disabled=false;button.textContent='🧹 Run cleanup now'}};\n""",
)

# --- regression coverage ---
path = "hubitat-mcp-ai/tests/test_one_time_rule_cleanup.py"
p = Path(path)
text = p.read_text(encoding="utf-8")
text = text.replace(
    "from one_time_rule_cleanup import OneTimeRuleCleanupService",
    "from one_time_rule_cleanup import OneTimeRuleCleanupScheduler, OneTimeRuleCleanupService",
)
append = r'''

@pytest.mark.asyncio
async def test_scheduler_status_and_manual_run_are_observable() -> None:
    mcp = FakeMCP()
    service = OneTimeRuleCleanupService(mcp, local_now=local_now, grace_minutes=10)
    scheduler = OneTimeRuleCleanupScheduler(
        service,
        enabled=True,
        daily_time="15:15",
        local_now=local_now,
    )

    initial = scheduler.status()
    assert initial["enabled"] is True
    assert initial["time"] == "15:15"
    assert initial["last_run"] is None
    assert initial["last_result"] is None

    result = await scheduler.run_now()

    assert [item["appId"] for item in result.deleted] == ["4210", "4211"]
    status = scheduler.status()
    assert status["last_trigger"] == "manual"
    assert status["last_run"] == result.checked_at
    assert status["last_error"] is None
    assert status["last_result"]["scanned"] == 5
    assert status["last_result"]["eligible"] == 2
    assert status["last_result"]["deleted_count"] == 2
    assert status["last_result"]["failed_count"] == 0


def test_cleanup_result_serialises_counts_and_details() -> None:
    outcome = OneTimeRuleCleanupResult(
        checked_at="2026-10-03T15:15:00+01:00",
        scanned=4,
        eligible=2,
        deleted=[{"appId": "4210", "name": "Example"}],
        failed=[{"appId": "4211", "name": "Example 2", "error": "blocked"}],
    )
    payload = outcome.as_dict()
    assert payload["deleted_count"] == 1
    assert payload["failed_count"] == 1
    assert payload["deleted"][0]["appId"] == "4210"
'''
# Need result class import for serialization contract.
text = text.replace(
    "from one_time_rule_cleanup import OneTimeRuleCleanupScheduler, OneTimeRuleCleanupService",
    "from one_time_rule_cleanup import OneTimeRuleCleanupResult, OneTimeRuleCleanupScheduler, OneTimeRuleCleanupService",
)
if "test_scheduler_status_and_manual_run_are_observable" not in text:
    text += append
p.write_text(text, encoding="utf-8")

Path("hubitat-mcp-ai/tests/test_cleanup_webui_contract.py").write_text(
    '''from __future__ import annotations\n\nimport sys\nfrom pathlib import Path\n\nAPP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"\nsys.path.insert(0, str(APP_DIR))\n\nfrom webui import render_page\n\n\ndef test_cleanup_status_and_manual_controls_are_visible() -> None:\n    page = render_page("HomeBrain", "0.16.100")\n    assert "One-time rule cleanup" in page\n    assert 'id="cleanupNextRun"' in page\n    assert 'id="cleanupLastRun"' in page\n    assert 'id="cleanupDeleted"' in page\n    assert 'id="runOneTimeCleanup"' in page\n    assert "api/one-time-rule-cleanup" in page\n    assert "api/one-time-rule-cleanup/run" in page\n''',
    encoding="utf-8",
)

# --- version/release metadata ---
replace_once("hubitat-mcp-ai/config.yaml", 'version: "0.16.99"', 'version: "0.16.100"')
replace_once("README.md", "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.99 |", "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.100 |")
replace_once("hubitat-mcp-ai/README.md", "Current add-on version: **0.16.99**.", "Current add-on version: **0.16.100**.")
replace_once(
    "hubitat-mcp-ai/README.md",
    "## Architecture\n\n",
    "## Architecture\n\n0.16.100 makes one-time-rule cleanup observable and manually testable. HomeBrain exposes the effective scheduler time, next run, last run, last trigger, last result and last error; the Web UI adds a guarded ‘Run cleanup now’ control and deletion details. Scheduler start/next-run/completion events are logged explicitly. Automatic cleanup remains strict and Hubitat-local, and there is still no destructive startup catch-up.\n\n",
)
replace_once(
    "hubitat-mcp-ai/CHANGELOG-INDEX.md",
    "## Current release\n\n- [0.16.99](CHANGELOG-0.16.99.md)",
    "## Current release\n\n- [0.16.100](CHANGELOG-0.16.100.md)\n\n## Recent performance releases\n\n- [0.16.99](CHANGELOG-0.16.99.md)",
)
# Remove duplicate heading introduced by the simple current-release replacement if present.
p = Path("hubitat-mcp-ai/CHANGELOG-INDEX.md")
text = p.read_text(encoding="utf-8")
text = text.replace("\n## Recent performance releases\n\n## Recent performance releases\n", "\n## Recent performance releases\n")
p.write_text(text, encoding="utf-8")

Path("hubitat-mcp-ai/CHANGELOG-0.16.100.md").write_text(
    '''# Hubitat MCP AI 0.16.100\n\n## One-time cleanup observability\n\n- Exposes the effective cleanup schedule, next run, last run, last trigger, last result, running state and last error.\n- Adds `GET /api/one-time-rule-cleanup` for deterministic status.\n- Adds guarded `POST /api/one-time-rule-cleanup/run` to execute the exact same strict cleanup service immediately.\n- HomeBrain Web UI now shows cleanup status, next/last run, last deleted/failed counts and per-rule details, plus **Run cleanup now** with a confirmation prompt.\n- Scheduler logs now state when it starts, the exact next Hubitat-local run time, when a cleanup begins and the scanned/eligible/deleted/failed result.\n- Automatic cleanup safety is unchanged: only exact expired `(One-time YYYY-MM-DD HH:MM)` HomeBrain rules are eligible; soft delete remains `force=false`, `confirm=true`; there is no startup catch-up deletion.\n\n## Why\n\nA live test changed the configured cleanup time to 15:15, but there was no visible proof that the in-process scheduler had loaded that time or run. The previous scheduler kept `next_run`, `last_result` and `last_error` only in memory and exposed none of them. This release makes the effective running schedule directly inspectable and allows safe same-day live proof without creating a separate Hubitat Rule Machine cleanup rule.\n''',
    encoding="utf-8",
)

print("0.16.100 patch applied")
