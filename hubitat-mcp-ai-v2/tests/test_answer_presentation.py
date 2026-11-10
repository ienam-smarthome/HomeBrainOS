"""UK date presentation is model guidance and display; MCP receipts stay original."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import _SKILL


class AnswerPresentationGuidanceTests(unittest.TestCase):
    def test_uk_skill_loaded_into_production_agent(self):
        path = Path(__file__).resolve().parents[1] / "rootfs" / "app" / "skills" / "hubitat" / "answer-presentation.md"
        guidance = path.read_text(encoding="utf-8")
        self.assertIn(guidance.strip(), _SKILL)
        for required in ("Europe/London", "GMT", "BST", "24-hour",
                         "fractional", "time zone is unspecified",
                         "Technical JSON", "Do not rewrite or convert tool arguments"):
            self.assertIn(required, guidance)
        self.assertNotIn("Dehumidifier 1", guidance)
        self.assertNotIn("5313", guidance)
        self.assertNotIn("08:10:10.107+0000", guidance)

    def test_source_reliability_not_overridden_by_presentation_skill(self):
        # Formatting instructions cannot become a fictional source or an
        # independent confirmation of a reported causal event.
        self.assertIn("source identity and chronology", _SKILL)
        self.assertIn("do **not** guess the zone", _SKILL)
        self.assertIn("readable display", _SKILL)
        self.assertIn("Do not project current snapshots back", _SKILL)


if __name__ == "__main__":
    unittest.main()
