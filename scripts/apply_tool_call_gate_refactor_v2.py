from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
ORCH = APP / "mcp_agent_orchestrator.py"
REGISTRY = APP / "tool_registry.py"
OLD_SCRIPT = ROOT / "scripts" / "apply_tool_call_gate_refactor.py"


def sub_once(pattern: str, replacement: str, text: str, *, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected one match for: {pattern[:160]}")
    return updated


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected source block not found: {old[:160]}")
    return text.replace(old, new, 1)


text = ORCH.read_text(encoding="utf-8")
text = replace_once(
    text,
    '        self._choices: ContextVar[list[str] | None] = ContextVar(\n            "hubitat_choices", default=None\n        )\n',
    '        self._choices: ContextVar[list[str] | None] = ContextVar(\n            "hubitat_choices", default=None\n        )\n        self._mutation_call_seen: ContextVar[bool] = ContextVar(\n            "hubitat_mutation_call_seen", default=False\n        )\n',
)
text = sub_once(
    r"    def _classify_request\(self, prompt: str, session_id: str\) -> str:\n.*?(?=    @staticmethod\n    def _redact)",
    '''    @staticmethod
    def _is_conversational_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        conversational = (
            r"(?:hi|hello|hey|thanks|thank you|good morning|good evening)[.!? ]*",
            r"(?:help|what can you do|who are you)[.!? ]*",
        )
        return any(re.fullmatch(pattern, normalized) for pattern in conversational)

''',
    text,
    flags=re.DOTALL,
)
text = replace_once(
    text,
    '        evidence_kind: str = "tool_result",\n    ) -> None:\n',
    '        evidence_kind: str = "tool_result",\n        mutates: bool = False,\n    ) -> None:\n',
)
text = replace_once(
    text,
    '            "evidence_kind": evidence_kind,\n            "arguments": self._redact(arguments),\n',
    '            "evidence_kind": evidence_kind,\n            "mutates": bool(mutates),\n            "arguments": self._redact(arguments),\n',
)
text = replace_once(
    text,
    '            self._needs_device_manifest(prompt)\n            and self._request_class.get() == "write"\n            and not routine_control\n',
    '            self._needs_device_manifest(prompt)\n            and _requests_mutation(prompt)\n            and not routine_control\n',
)
text = replace_once(
    text,
    '        if not tool or (tool.annotations or {}).get("readOnlyHint") is True:\n            return False\n        name = tool.name.lower().replace("-", "_")\n',
    '        if not tool:\n            return False\n        annotations = tool.annotations or {}\n        if annotations.get("mutates") is not None:\n            return bool(annotations.get("mutates"))\n        if annotations.get("readOnlyHint") is True:\n            return False\n        name = tool.name.lower().replace("-", "_")\n',
)
text = sub_once(
    r"        request_class = self\._classify_request\(user_prompt, session_id\)\n.*?        finally:\n            self\._request_class\.reset\(class_token\)\n            self\._evidence\.reset\(evidence_token\)\n            self\._choices\.reset\(choices_token\)\n",
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
    text,
    flags=re.DOTALL,
)
text = replace_once(
    text,
    '            if self._request_class.get() == "live-read":\n',
    '            if not self._is_conversational_prompt(user_prompt):\n',
)
text = text.replace('        mutation_requested = _requests_mutation(user_prompt)\n', '', 1)
text = text.replace('        successful_mutations = 0\n        failed_mutation = ""\n        control_retry_used = False\n', '', 1)
text = sub_once(
    r"                if mutation_requested and successful_mutations == 0:\n.*?(?=                if self\._request_class\.get\(\) == \"live-read\" and not self\._has_live_evidence\(\):)",
    '',
    text,
    flags=re.DOTALL,
)
text = replace_once(
    text,
    '                if self._request_class.get() == "live-read" and not self._has_live_evidence():\n',
    '                if not self._is_conversational_prompt(user_prompt) and not self._has_live_evidence():\n',
)
text = replace_once(
    text,
    '                tool = by_name.get(name)\n                if tool and self.require_sensitive_confirmation and self._is_sensitive(tool, arguments):\n',
    '                tool = by_name.get(name)\n                if self._call_is_mutation(tool, arguments):\n                    self._mutation_call_seen.set(True)\n                if tool and self.require_sensitive_confirmation and self._is_sensitive(tool, arguments):\n',
)
text = replace_once(
    text,
    '                        self._record_evidence(\n                            name,\n                            dict(arguments),\n                            success=self._tool_succeeded(result),\n                            elapsed_ms=elapsed_ms,\n                            summary=self._result_summary(result),\n                            supports_live_claim=name != "hub_search_tools",\n                            evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),\n                        )\n',
    '                        mutates = self._call_is_mutation(tool, dict(arguments))\n                        if mutates:\n                            self._mutation_call_seen.set(True)\n                        self._record_evidence(\n                            name,\n                            dict(arguments),\n                            success=self._tool_succeeded(result),\n                            elapsed_ms=elapsed_ms,\n                            summary=self._result_summary(result),\n                            supports_live_claim=name != "hub_search_tools",\n                            evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),\n                            mutates=mutates,\n                        )\n',
)
text = sub_once(
    r"                        if self\._call_is_mutation\(tool, dict\(arguments\)\):\n                            if self\._tool_succeeded\(result\):\n                                successful_mutations \+= 1\n                            else:\n                                failed_mutation = result\.text or \"MCP reported an error\"\n",
    '',
    text,
)
text = replace_once(
    text,
    '                        supports_live_claim=name != "hub_search_tools",\n                    )\n                    content = json.dumps({"error": str(exc)})\n                    if self._call_is_mutation(by_name.get(name), dict(arguments)):\n                        failed_mutation = str(exc)\n',
    '                        supports_live_claim=name != "hub_search_tools",\n                        mutates=self._call_is_mutation(by_name.get(name), dict(arguments)),\n                    )\n                    content = json.dumps({"error": str(exc)})\n',
)
ORCH.write_text(text, encoding="utf-8")

# Reuse the already-reviewed tail for registry metadata, tests, docs, versioning,
# release notes, and cleanup of the one-shot files.
old_source = OLD_SCRIPT.read_text(encoding="utf-8")
tail = old_source[old_source.index("registry = REGISTRY.read_text"):]
exec(compile(tail, str(OLD_SCRIPT), "exec"), globals(), globals())
Path(__file__).unlink(missing_ok=True)
