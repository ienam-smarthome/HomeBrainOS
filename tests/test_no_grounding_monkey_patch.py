from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def test_production_agent_does_not_patch_orchestrator_grounding_symbol() -> None:
    source = (APP_DIR / "homebrain_agent.py").read_text(encoding="utf-8")

    assert "orchestrator.GroundingPolicy" not in source
    assert "_ProductionGroundingAuthority" not in source
    assert "_CURRENT_EVIDENCE_RECORDER" not in source
    assert "set_grounding_policy_factory" in source
    assert "reset_grounding_policy_factory" in source
