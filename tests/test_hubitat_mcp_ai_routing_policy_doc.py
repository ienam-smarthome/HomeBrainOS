from pathlib import Path


def test_routing_policy_documented():
    text = Path("hubitat-mcp-ai/ROUTING_POLICY.md").read_text(encoding="utf-8")
    assert "MCP-fast" in text
    assert "verified MCP context" in text
    assert "Ollama MCP planner" in text
