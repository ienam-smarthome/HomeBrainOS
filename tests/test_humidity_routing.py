from pathlib import Path
import sys

APP = Path(
    "hubitat-mcp-ai/rootfs/app"
)

sys.path.insert(0,str(APP))

from ai_evidence_planner import AIEvidencePlanner


def test_humidity_question_selects_measurement():
    assert "humidity" in (
        " ".join(
            AIEvidencePlanner._fallback_plan(
                None,
                "which room has highest humidity?",
            )
        )
    )
