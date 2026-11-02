"""Offline evidence checkpoint selection: no MCP/network/live hub access."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from evidence_first_checkpoint_plan import select_evidence_checkpoint, SourceCheckpointBudget


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


def read_scope(tool="hub_read_devices", args=None, *, success=True, effect="read"):
    return {"tool": tool, "arguments": args if args is not None else
            {"deviceId": "42"}, "success": success, "effect": effect}


class EvidenceEpochFrozenReplayTests(unittest.TestCase):
    """Synthetic receipt timelines: rounds tested, not model answer accuracy."""

    def test_no_read_progress_allows_only_first_source_retry(self):
        b = SourceCheckpointBudget()
        self.assertTrue(b.offer("target-history", []))
        self.assertFalse(b.offer("upstream-input", []))
        self.assertFalse(b.offer("missing-required-source", [
            read_scope(success=False)]))
        self.assertEqual(b.offered_kinds, ["target-history"])

    def test_source_complete_packet_allows_progress_but_not_duplicate(self):
        # Heating-like packet, purely anonymous; not a live Hubitat capture.
        b = SourceCheckpointBudget()
        status = read_scope(args={"deviceId": "11", "attribute": "thermostatMode"})
        history = read_scope(args={"deviceId": "11", "attribute": "command-setThermostatMode"})
        app_logs = read_scope(tool="hub_read_diagnostics",
                              args={"tool": "hub_get_logs", "args": {"appId": "22"}})
        self.assertTrue(b.offer("target-history", [status]))
        self.assertFalse(b.offer("upstream-input", [status, dict(status)]))
        self.assertTrue(b.offer("issuer-decision", [status, history]))
        self.assertTrue(b.offer("configuration-semantics",
                                [status, history, app_logs]))
        self.assertFalse(b.offer("missing-required-source", [
            status, history, app_logs,
            read_scope(args={"deviceId": "12"})]))
        self.assertEqual(len(b.offered_kinds), 3)

    def test_failed_and_write_receipts_do_not_rearm(self):
        b = SourceCheckpointBudget()
        status = read_scope()
        self.assertTrue(b.offer("diagnostic-discriminator", [status]))
        self.assertFalse(b.offer("driver-or-controller", [
            status, read_scope(args={"deviceId": "43"}, success=False),
            read_scope(tool="hub_set_device", args={"deviceId": "43"}, effect="write"),
        ]))

    def test_read_scope_is_order_independent_and_no_data_exposure(self):
        a = read_scope(args={"since": "time", "deviceId": "42"})
        duplicate = read_scope(args={"deviceId": "42", "since": "time"})
        self.assertEqual(SourceCheckpointBudget.successful_read_scopes([a]),
                         SourceCheckpointBudget.successful_read_scopes([duplicate]))
        self.assertEqual(len(SourceCheckpointBudget.successful_read_scopes(
            [a, duplicate])), 1)

    def test_separate_requests_have_independent_budgets(self):
        first = SourceCheckpointBudget(max_offers=1)
        second = SourceCheckpointBudget(max_offers=1)
        self.assertTrue(first.offer("target-history", []))
        self.assertFalse(first.offer("upstream-input", [read_scope()]))
        self.assertTrue(second.offer("target-history", []))
        self.assertFalse(second.offer("upstream-input", []))

    def test_structural_gate_covers_major_no_tool_recovery_paths(self):
        source = (Path(__file__).resolve().parents[1] /
                  "hubitat-mcp-ai" / "rootfs" / "app" /
                  "mcp_agent_orchestrator.py").read_text()
        for name in ("target-history", "upstream-input", "inventory-evidence",
                     "configuration-semantics", "diagnostic-discriminator",
                     "missing-required-source", "driver-or-controller",
                     "incident-progress", "task-evidence-coverage",
                     "causal-provenance"):
            self.assertIn(f'offer_source_checkpoint("{name}")', source)


if __name__ == "__main__":
    unittest.main()
