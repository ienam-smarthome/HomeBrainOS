from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "mcp_agent_orchestrator.py"
TEST = ROOT / "tests" / "test_tool_call_driven_gate.py"

text = ORCH.read_text(encoding="utf-8")
old = '''        for tool_name, arguments in pending.actions:
            try:
                started = time.monotonic()
'''
new = '''        for tool_name, arguments in pending.actions:
            self._mutation_call_seen.set(True)
            try:
                started = time.monotonic()
'''
if old not in text:
    raise RuntimeError("Pending confirmation loop not found")
text = text.replace(old, new, 1)
text = text.replace(
    '''                    summary=self._result_summary(result),
                )
                content = self._result_payload(result)
''',
    '''                    summary=self._result_summary(result),
                    mutates=True,
                )
                content = self._result_payload(result)
''',
    1,
)
text = text.replace(
    '''                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                )
                content = json.dumps({"error": str(exc)})
''',
    '''                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                    mutates=True,
                )
                content = json.dumps({"error": str(exc)})
''',
    1,
)
ORCH.write_text(text, encoding="utf-8")

with TEST.open("a", encoding="utf-8") as handle:
    handle.write('''\n\ndef test_confirmed_pending_actions_remain_mutating_in_source():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    confirmation = source[source.index("async def _resume_confirmation"):source.index("async def process_user_request_result")]

    assert "self._mutation_call_seen.set(True)" in confirmation
    assert confirmation.count("mutates=True") == 2
''')

(ROOT / ".github" / "workflows" / "apply-pending-confirmation-fix.yml").unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
