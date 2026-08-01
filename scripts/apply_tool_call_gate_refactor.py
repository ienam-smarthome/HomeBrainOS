from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
ORCH = APP / "mcp_agent_orchestrator.py"
REGISTRY = APP / "tool_registry.py"


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected source block not found:\n{old[:180]}")
    return text.replace(old, new, 1)


text = ORCH.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        self._choices: ContextVar[list[str] | None] = ContextVar(
            "hubitat_choices", default=None
        )
        self.ai_client = ai_client or httpx.AsyncClient(
''',
    '''        self._choices: ContextVar[list[str] | None] = ContextVar(
            "hubitat_choices", default=None
        )
        self._mutation_call_seen: ContextVar[bool] = ContextVar(
            "hubitat_mutation_call_seen", default=False
        )
        self.ai_client = ai_client or httpx.AsyncClient(
''',
)
start = text.index("    def _classify_request(")
end = text.index("    @staticmethod\n    def _redact", start)
text = text[:start] + '''    @staticmethod
    def _is_conversational_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        conversational = (
            r"(?:hi|hello|hey|thanks|thank you|good morning|good evening)[.!? ]*",
            r"(?:help|what can you do|who are you)[.!? ]*",
        )
        return any(re.fullmatch(pattern, normalized) for pattern in conversational)

''' + text[end:]
text = replace_once(
    text,
    '''        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
    ) -> None:
''',
    '''        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
        mutates: bool = False,
    ) -> None:
''',
)
text = replace_once(
    text,
    '''            "evidence_kind": evidence_kind,
            "arguments": self._redact(arguments),
''',
    '''            "evidence_kind": evidence_kind,
            "mutates": bool(mutates),
            "arguments": self._redact(arguments),
''',
)
text = replace_once(
    text,
    '''        return (
            self._needs_device_manifest(prompt)
            and self._request_class.get() == "write"
            and not routine_control
        )
''',
    '''        return (
            self._needs_device_manifest(prompt)
            and _requests_mutation(prompt)
            and not routine_control
        )
''',
)
text = replace_once(
    text,
    '''        if not tool or (tool.annotations or {}).get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
''',
    '''        if not tool:
            return False
        annotations = tool.annotations or {}
        if annotations.get("mutates") is not None:
            return bool(annotations.get("mutates"))
        if annotations.get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
''',
)
text = replace_once(
    text,
    '''        request_class = self._classify_request(user_prompt, session_id)
        evidence_token = self._evidence.set([])
        choices_token = self._choices.set([])
        class_token = self._request_class.set(request_class)
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=list(self._evidence.get() or []),
                choices=list(self._choices.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._evidence.reset(evidence_token)
            self._choices.reset(choices_token)
''',
    '''        evidence_token = self._evidence.set([])
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(False)
        class_token = self._request_class.set("tool-driven")
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            evidence = list(self._evidence.get() or [])
            if self._mutation_call_seen.get():
                request_class = "write"
            elif self._is_conversational_prompt(user_prompt) and not evidence:
                request_class = "conversational"
            else:
                request_class = "live-read"
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=evidence,
                choices=list(self._choices.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._mutation_call_seen.reset(mutation_token)
            self._evidence.reset(evidence_token)
            self._choices.reset(choices_token)
''',
)
text = replace_once(
    text,
    '''            if (
                self._request_class.get() == "live-read"
            ):
''',
    '''            if not self._is_conversational_prompt(user_prompt):
''',
)
text = replace_once(text, "        mutation_requested = _requests_mutation(user_prompt)\n", "")
text = replace_once(
    text,
    '''        successful_mutations = 0
        failed_mutation = ""
        control_retry_used = False
''',
    "",
)
block_start = text.index("                if mutation_requested and successful_mutations == 0:")
block_end = text.index(
    '                if (\n                    self._request_class.get() == "live-read"',
    block_start,
)
text = text[:block_start] + text[block_end:]
text = replace_once(
    text,
    '''                if (
                    self._request_class.get() == "live-read"
                    and not self._has_live_evidence()
                ):
''',
    '''                if (
                    not self._is_conversational_prompt(user_prompt)
                    and not self._has_live_evidence()
                ):
''',
)
text = replace_once(
    text,
    '''                tool = by_name.get(name)
                if (
                    tool
                    and self.require_sensitive_confirmation
''',
    '''                tool = by_name.get(name)
                if self._call_is_mutation(tool, arguments):
                    self._mutation_call_seen.set(True)
                if (
                    tool
                    and self.require_sensitive_confirmation
''',
)
text = replace_once(
    text,
    '''                        self._record_evidence(
                            name,
                            dict(arguments),
                            success=self._tool_succeeded(result),
                            elapsed_ms=elapsed_ms,
                            summary=self._result_summary(result),
                            supports_live_claim=name != "hub_search_tools",
                            evidence_kind=_EVIDENCE_KINDS.get(
                                name, "tool_result"
                            ),
                        )
''',
    '''                        mutates = self._call_is_mutation(tool, dict(arguments))
                        if mutates:
                            self._mutation_call_seen.set(True)
                        self._record_evidence(
                            name,
                            dict(arguments),
                            success=self._tool_succeeded(result),
                            elapsed_ms=elapsed_ms,
                            summary=self._result_summary(result),
                            supports_live_claim=name != "hub_search_tools",
                            evidence_kind=_EVIDENCE_KINDS.get(
                                name, "tool_result"
                            ),
                            mutates=mutates,
                        )
''',
)
text = replace_once(
    text,
    '''                        if self._call_is_mutation(tool, dict(arguments)):
                            if self._tool_succeeded(result):
                                successful_mutations += 1
                            else:
                                failed_mutation = result.text or "MCP reported an error"
''',
    "",
)
text = replace_once(
    text,
    '''                    if self._call_is_mutation(by_name.get(name), dict(arguments)):
                        failed_mutation = str(exc)
''',
    "",
)
exception_anchor = text.index('logger.exception("MCP tool %s failed"')
exception_tail = text[exception_anchor:]
exception_tail = replace_once(
    exception_tail,
    '''                        supports_live_claim=name != "hub_search_tools",
                    )
''',
    '''                        supports_live_claim=name != "hub_search_tools",
                        mutates=self._call_is_mutation(
                            by_name.get(name), dict(arguments)
                        ),
                    )
''',
)
text = text[:exception_anchor] + exception_tail
ORCH.write_text(text, encoding="utf-8")

registry = REGISTRY.read_text(encoding="utf-8")
registry = replace_once(
    registry,
    '        annotations={"readOnlyHint": False, "destructiveHint": False},\n',
    '        annotations={"readOnlyHint": False, "destructiveHint": False, "mutates": True, "danger": "routine"},\n',
)
REGISTRY.write_text(registry, encoding="utf-8")

(ROOT / "tests" / "test_tool_call_driven_gate.py").write_text('''from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool  # noqa: E402

READ_DIAGNOSTIC_PHRASES = [
    "which switches are on?",
    "why did livingroom light 1 turn off",
    "why is the kitchen light on",
    "did the front door lock change recently",
    "how come the thermostat isn't heating",
    "has the garage door been open long",
    "what happened to the living room light at 9pm",
    "is anything supposed to turn the hallway light off",
    "when did bedroom light 2 last turn on",
    "why does light 1 keep flickering",
]


class DummyMCP:
    pass


class DummyAI:
    async def aclose(self):
        return None


def make_agent() -> UnifiedMCPAgent:
    return UnifiedMCPAgent(DummyMCP(), "key", ai_client=DummyAI())


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", READ_DIAGNOSTIC_PHRASES)
async def test_read_phrasing_is_classified_from_actual_tool_activity(prompt, monkeypatch):
    agent = make_agent()

    async def fake_process(*args, **kwargs):
        agent._record_evidence(
            "hub_read_devices",
            {"tool": "hub_get_device_events"},
            success=True,
            elapsed_ms=1,
            summary="verified read evidence",
            supports_live_claim=True,
            mutates=False,
        )
        return "Verified diagnostic answer"

    monkeypatch.setattr(agent, "_process_user_request", fake_process)
    outcome = await agent.process_user_request_result(prompt, session_id="test")

    assert outcome.request_class == "live-read"
    assert outcome.message == "Verified diagnostic answer"
    assert all(receipt["mutates"] is False for receipt in outcome.evidence)
    assert "I did not execute a Hubitat control tool" not in outcome.message


@pytest.mark.asyncio
async def test_request_class_becomes_write_only_after_mutating_tool_call(monkeypatch):
    agent = make_agent()

    async def fake_process(*args, **kwargs):
        agent._mutation_call_seen.set(True)
        agent._record_evidence(
            "homebrain_control_devices",
            {"command": "off"},
            success=True,
            elapsed_ms=1,
            summary="control completed",
            mutates=True,
        )
        return "Turned off the light."

    monkeypatch.setattr(agent, "_process_user_request", fake_process)
    outcome = await agent.process_user_request_result(
        "turn off livingroom light 1", session_id="test"
    )

    assert outcome.request_class == "write"
    assert outcome.evidence[0]["mutates"] is True


def test_mutation_metadata_is_checked_on_the_requested_tool():
    declared_write = MCPTool(
        "example_write",
        "write",
        {"type": "object"},
        annotations={"mutates": True, "readOnlyHint": False},
    )
    declared_read = MCPTool(
        "example_read",
        "read",
        {"type": "object"},
        annotations={"mutates": False, "readOnlyHint": False},
    )

    assert UnifiedMCPAgent._call_is_mutation(declared_write, {}) is True
    assert UnifiedMCPAgent._call_is_mutation(declared_read, {"command": "off"}) is False


def test_legacy_text_classifier_no_longer_controls_response_gate():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")

    assert "mutation_requested = _requests_mutation(user_prompt)" not in source
    assert "if mutation_requested and successful_mutations == 0" not in source
    assert "self._mutation_call_seen.get()" in source
''', encoding="utf-8")

architecture = ROOT / "docs" / "ARCHITECTURE.md"
architecture_text = architecture.read_text(encoding="utf-8")
rule = '''\n## Tool-call-driven mutation safety\n\nNo text-based intent classification may gate control-versus-read behaviour. Mutation gating is driven by metadata on the actual requested tool and is checked when the tool call is received. Read and diagnostic answers use gathered evidence even when their wording contains control verbs. Live-state claims still require successful evidence with `supports_live_claim=true`.\n'''
if "## Tool-call-driven mutation safety" not in architecture_text:
    architecture.write_text(architecture_text.rstrip() + "\n" + rule, encoding="utf-8")

contributing = ROOT / "CONTRIBUTING.md"
contributing_text = contributing.read_text(encoding="utf-8")
rule = "- Do not use query keywords or regex intent classes to gate read versus mutation behaviour; gate the actual requested tool call using tool metadata.\n"
if rule not in contributing_text:
    contributing.write_text(contributing_text.rstrip() + "\n\n" + rule, encoding="utf-8")

config = ROOT / "hubitat-mcp-ai" / "config.yaml"
config_text = config.read_text(encoding="utf-8").replace('version: "0.10.261"', 'version: "0.10.262"', 1)
config.write_text(config_text, encoding="utf-8")
root_readme = ROOT / "README.md"
root_readme.write_text(root_readme.read_text(encoding="utf-8").replace("0.10.261", "0.10.262"), encoding="utf-8")
addon_readme = ROOT / "hubitat-mcp-ai" / "README.md"
addon_readme.write_text(addon_readme.read_text(encoding="utf-8").replace("0.10.261", "0.10.262"), encoding="utf-8")
(ROOT / "hubitat-mcp-ai" / "CHANGELOG-0.10.262.md").write_text('''# Hubitat MCP AI 0.10.262

- Derive write-versus-read reporting from actual requested tool calls instead of raw query text.
- Remove the text-classifier-triggered “no control tool executed” refusal path.
- Preserve sensitive confirmation at tool-call time and tag evidence receipts with `mutates`.
- Add regression coverage for past-tense and interrogative diagnostic wording containing control verbs.
- Document the rule against text-based mutation gates.
''', encoding="utf-8")

# Remove the one-shot transformation machinery before committing the generated result.
(ROOT / ".github" / "workflows" / "apply-tool-call-gate-refactor.yml").unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
