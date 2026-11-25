"""Ratchet: runtime modules must not add regex checks on user question text.

Safety and routing decisions should come from the declared tool call, structured
arguments and receipts, never from phrase-matching what the user typed. Phrase
matching silently stops working when a question is reworded.

The BASELINE counts calls such as ``PATTERN.search(question)`` or
``re.search(p, question)`` found by static analysis (argument named like user
text). It may only go DOWN: lower a number when you remove a check, never raise
one or add a file. The check is a heuristic by variable name; it catches the
common shape, not every possible one.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
TEXT_NAMES = {"question", "user_question", "user_text", "prompt", "message",
              "text", "query", "user_message"}
REGEX_METHODS = {"search", "match", "fullmatch", "findall", "finditer", "sub", "split"}

BASELINE = {
    "agent.py": 2,
    "bounded_source_projection.py": 7,
    "bounded_temporal_projection.py": 10,
    "causal_claim_publication.py": 1,
    "control_surface_recovery.py": 2,
    "investigation_review.py": 39,
    "memory_window_provenance.py": 1,
    "native_action_contract.py": 2,
    "one_off_rule_policy.py": 3,
    "routine_action_fastpath.py": 2,
    "temporal_transition_verification.py": 3,
    "typed_history_verification.py": 7,
    "write_receipt_evidence.py": 2,
}


def count_sites(path: Path) -> int:
    total = 0
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in REGEX_METHODS
                and any(isinstance(a, ast.Name) and a.id in TEXT_NAMES
                        for a in node.args)):
            total += 1
    return total


class QuestionTextGatingRatchet(unittest.TestCase):
    def test_no_new_or_growing_question_text_regex_checks(self):
        found = {p.name: count_sites(p) for p in sorted(APP.glob("*.py"))}
        found = {name: n for name, n in found.items() if n}
        problems = []
        for name, n in found.items():
            allowed = BASELINE.get(name, 0)
            if n > allowed:
                problems.append(f"{name}: {n} regex checks on question text, "
                                f"baseline {allowed}. Gate on the tool call, "
                                "structured arguments or receipts instead.")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_baseline_is_tight(self):
        """Fail when a count dropped, so the baseline is lowered with the code."""
        found = {p.name: count_sites(p) for p in sorted(APP.glob("*.py"))}
        stale = [f"{name}: baseline {allowed}, now {found.get(name, 0)}"
                 for name, allowed in BASELINE.items()
                 if found.get(name, 0) < allowed]
        self.assertEqual(stale, [], "Lower BASELINE: " + "; ".join(stale))


if __name__ == "__main__":
    unittest.main()
