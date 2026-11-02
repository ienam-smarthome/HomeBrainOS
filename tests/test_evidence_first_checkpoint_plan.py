"""Offline evidence checkpoint selection: no MCP/network/live hub access."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from evidence_first_checkpoint_plan import select_evidence_checkpoint


def candidate(kind, signature, **overrides):
    item = dict(kind=kind, signature=signature, verified=True, available=True,
                read_only=True, tool="hub_read_devices", args={"deviceId": "42"})
    item.update(overrides)
    return item


class EvidenceFirstCheckpointPlanTests(unittest.TestCase):
    def test_source_priority_does_not_depend_on_input_order(self):
        options = [candidate("upstream-input", "c"),
                   candidate("target-history", "a"),
                   candidate("issuer-decision", "b")]
        self.assertEqual(select_evidence_checkpoint(options)["signature"], "a")
        self.assertEqual(select_evidence_checkpoint(reversed(options))["signature"], "a")

    def test_prior_attempt_is_not_retried(self):
        self.assertEqual(select_evidence_checkpoint([
            candidate("target-history", "a"), candidate("issuer-decision", "b")
        ], attempted={"a"})["signature"], "b")

    def test_denies_unverified_or_mutating_candidates(self):
        options = [candidate("target-history", "a", verified=False),
                   candidate("issuer-decision", "b", read_only=False),
                   candidate("upstream-input", "c", available=False)]
        self.assertIsNone(select_evidence_checkpoint(options))

    def test_does_not_grant_a_tool_to_a_missing_scope(self):
        self.assertIsNone(select_evidence_checkpoint([
            candidate("target-history", "a", args=None),
            candidate("target-history", "", args={}),
            candidate("other", "b"),
        ]))

    def test_does_not_mutate_input_arguments(self):
        source = candidate("target-history", "a")
        result = select_evidence_checkpoint([source])
        result["args"]["deviceId"] = "999"
        self.assertEqual(source["args"]["deviceId"], "42")

    def test_no_candidates_means_unresolved_not_success(self):
        self.assertIsNone(select_evidence_checkpoint([]))


if __name__ == "__main__":
    unittest.main()
