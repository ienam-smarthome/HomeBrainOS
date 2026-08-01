from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "mcp_agent_orchestrator.py"
TEST_ORCH = ROOT / "tests" / "test_mcp_agent_orchestrator.py"
TEST_EXTRACTED = ROOT / "tests" / "test_orchestrator_extracted_modules.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected block not found in {path}: {old[:160]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Preserve the lean write-only tool declaration selected by _select_tools.
# Safe read helpers are added only when the selected path is not already a
# concrete control path.
replace_once(
    ORCH,
    '''            if not self._is_conversational_prompt(user_prompt):
                declared = [tool for tool in declared if tool.name != "hub_get_info"]
                declared_names = {tool.name for tool in declared}
                declared.extend(tool for tool in safe_read_tools if tool.name not in declared_names)
''',
    '''            if (
                not self._is_conversational_prompt(user_prompt)
                and all(tool.name != _LOCAL_CONTROL_TOOL for tool in declared)
            ):
                declared = [tool for tool in declared if tool.name != "hub_get_info"]
                declared_names = {tool.name for tool in declared}
                declared.extend(tool for tool in safe_read_tools if tool.name not in declared_names)
''',
)

# Replace classifier-era assertions with tests for the new architecture.
replace_once(
    TEST_ORCH,
    '''def test_general_request_classification():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    assert agent._classify_request("hello", "s") == "conversational"
    assert agent._classify_request("What is the hub status?", "s") == "live-read"
    assert agent._classify_request("turn off hallway lights", "s") == "write"
''',
    '''def test_conversational_prompt_detection_does_not_classify_mutations():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    assert agent._is_conversational_prompt("hello") is True
    assert agent._is_conversational_prompt("What is the hub status?") is False
    assert agent._is_conversational_prompt("turn off hallway lights") is False
    assert not hasattr(agent, "_classify_request")
''',
)
replace_once(
    TEST_ORCH,
    '''    assert "did not execute a Hubitat control tool" in answer
    assert len(ai.requests) == 2
''',
    '''    assert answer == "I could not retrieve verified live Hubitat evidence, so I will not provide an inferred answer."
    assert "did not execute a Hubitat control tool" not in answer
    assert len(ai.requests) == 2
''',
)

replace_once(
    TEST_EXTRACTED,
    '''    assert control.annotations == {"readOnlyHint": False, "destructiveHint": False}
''',
    '''    assert control.annotations == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "mutates": True,
        "danger": "routine",
    }
''',
)

(ROOT / ".github" / "workflows" / "apply-tool-gate-ci-fix.yml").unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
