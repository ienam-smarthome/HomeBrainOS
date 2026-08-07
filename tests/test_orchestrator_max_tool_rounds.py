from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402


def test_default_max_tool_rounds_is_nine():
    # Regression guard: the old default of 6 was proven too tight in live
    # testing for a query that has to discover an unconventional attribute
    # name (a dedicated power meter reporting under 'value'/'valueStr'
    # instead of 'power') -- it could exhaust every round on failed
    # attribute-name guesses and invalid-parameter retries before ever
    # reaching a usable answer, producing an empty
    # "MCP request completed without a written answer." response instead
    # of a real one. See CHANGELOG-0.10.368.md.
    agent = UnifiedMCPAgent(
        object(), "cloud-key", "gemma4:31b-cloud", ai_client=object()
    )

    assert agent.max_tool_rounds == 9


def test_max_tool_rounds_is_configurable_and_floored_at_one():
    agent = UnifiedMCPAgent(
        object(), "cloud-key", "gemma4:31b-cloud",
        max_tool_rounds=3, ai_client=object(),
    )
    assert agent.max_tool_rounds == 3

    floored = UnifiedMCPAgent(
        object(), "cloud-key", "gemma4:31b-cloud",
        max_tool_rounds=0, ai_client=object(),
    )
    assert floored.max_tool_rounds == 1
