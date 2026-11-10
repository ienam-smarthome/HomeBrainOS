"""Opt-in native-result variant for future blinded evaluation only.

The production Agent.answer loop, model-selected tools, server schemas,
permissions, confirmation flow and original MCP results are unchanged.
This class is NOT instantiated by the production add-on or existing frozen
benchmark experiments. A new independent prospectively frozen evaluation
can compare this one general source-presentation difference to baseline.
"""
from __future__ import annotations

from agent import Agent
from source_ledger import with_source_ledger


class SourceLedgerExperimentalAgent(Agent):
    def present_native_result(self, result: dict, arguments: dict) -> dict:
        return with_source_ledger(
            super().present_native_result(result, arguments), arguments
        )
