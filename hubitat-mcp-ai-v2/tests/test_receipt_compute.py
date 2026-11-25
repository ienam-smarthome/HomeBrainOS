"""Regressions for deterministic computation over rows already returned.

Cases mirror the alpha154 owner-capture failures (miscounted battery range,
36 KB vs 36,074.5 KB memory arithmetic, adjacent-row gaps) using fictional data.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from receipt_compute import ComputeError, TOOL_NAME, compute, rows_hint  # noqa: E402
from investigation_review import is_read_only_review_tool  # noqa: E402


def native(payload, name="hub_list_devices", args=None, **extra):
    outer = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    row = {"name": name, "arguments": args or {}, "success": True,
           "result_kind": "tool_result", "response": json.dumps(outer)}
    row.update(extra)
    return row


class InventoryCounting(unittest.TestCase):
    def setUp(self):
        devices = ([{"id": str(i), "battery": b} for i, b in
                    enumerate([80, 85, 90, 94, 94, 80, 79, 95, 100])]
                   + [{"id": f"x{i}"} for i in range(20)]
                   + [{"id": "s", "battery": "n/a"}])
        self.receipts = [native({"devices": devices, "hasMore": True})]

    def test_battery_range_counts_exactly_and_reports_skips(self):
        out = compute(self.receipts, {
            "operation": "count",
            "where": [{"field": "battery", "op": "gte", "value": 80},
                      {"field": "battery", "op": "lte", "value": 94}]})
        self.assertEqual(out["count"], 6)
        self.assertEqual(out["rows_in_list"], 30)
        self.assertEqual(out["rows_path"], "content.0.text.devices")
        self.assertTrue(out["covers_only_rows_the_source_returned"])

    def test_missing_and_nonnumeric_are_reported_not_guessed(self):
        out = compute(self.receipts, {"operation": "mean", "field": "battery"})
        self.assertEqual(out["rows_missing_field"], 20)
        self.assertEqual(out["rows_non_numeric"], 1)
        self.assertEqual(out["rows_used"], 9)

    def test_group_and_unique(self):
        g = compute(self.receipts, {"operation": "group_count", "field": "battery"})
        self.assertEqual(g["groups"][0]["count"], 2)
        self.assertIn(g["groups"][0]["value"], ("80", "94"))
        u = compute(self.receipts, {"operation": "unique_count", "field": "id"})
        self.assertEqual(u["unique_count"], 30)


class MemoryArithmetic(unittest.TestCase):
    def test_difference_between_latest_and_mean_is_not_36kb(self):
        values = [881840, 976616, 889048, 925000, 940000]
        receipts = [native({"entries": [{"freeMemory": v} for v in values]},
                           name="hub_get_memory_history")]
        out = compute(receipts, {"operation": "mean", "field": "freeMemory"})
        self.assertEqual(out["result"], sum(values) / len(values))
        self.assertEqual(out["min"], 881840)
        self.assertEqual(out["max"], 976616)
        d = compute(receipts, {"operation": "diff", "field": "freeMemory"})
        self.assertEqual(d["difference"], 940000 - 881840)


class Timestamps(unittest.TestCase):
    ROWS = [{"time": "2026-11-20T10:00:00Z", "value": "open"},
            {"time": "2026-11-20T10:20:00Z", "value": "closed"},
            {"time": "2026-11-20T09:00:00Z", "value": "open"},   # unsorted on purpose
            {"time": "2026-11-20T13:07:40.747Z", "value": "open"},
            {"time": "bad", "value": "x"}]

    def test_gaps_sorted_exactly_and_flagged_as_not_proof(self):
        out = compute([native({"events": self.ROWS})], {"operation": "time_gaps", "field": "time"})
        top = out["largest_gaps"][0]
        self.assertEqual(top["seconds"], 10060.747)
        self.assertEqual(top["readable"], "2h 47m 40.747s")
        self.assertEqual(out["rows_unparseable_time"], 1)
        self.assertTrue(out["gaps_are_between_returned_rows_not_proof_of_no_events"])

    def test_span(self):
        out = compute([native({"events": self.ROWS[:4]})], {"operation": "diff", "field": "time"})
        self.assertEqual(out["kind"], "timestamp_span")
        self.assertEqual(out["seconds"], 14860.747)

    def test_naive_timestamps_are_not_guessed(self):
        rows = [{"t": "2026-11-20T10:00:00"}, {"t": "2026-11-20T11:00:00"}]
        out = compute([native({"events": rows})], {"operation": "time_gaps", "field": "t"})
        self.assertEqual(out["rows_unparseable_time"], 2)
        self.assertEqual(out["largest_gaps"], [])

    def test_sort_descending_with_limit(self):
        out = compute([native({"events": self.ROWS[:4]})],
                      {"operation": "sort", "field": "time", "descending": True, "limit": 2})
        self.assertEqual([r["value"] for r in out["rows"]], ["open", "closed"])
        self.assertTrue(out["rows_truncated_to_limit"])


class Refusals(unittest.TestCase):
    def test_truncated_receipt_refused(self):
        r = native({})
        r["response"] = json.dumps({"truncated": True, "visible_prefix": "[{"})
        with self.assertRaisesRegex(ComputeError, "truncated"):
            compute([r], {"operation": "count"})

    def test_failed_or_local_receipts_refused_and_listed(self):
        bad = native({"devices": [{"id": 1}]}, success=False)
        good = native({"devices": [{"id": 1}]}, name="hub_get_x", args={"a": 1})
        clock = {"name": "homebrain_read_clock", "success": True,
                 "result_kind": "local_clock_read", "response": "{}"}
        with self.assertRaisesRegex(ComputeError, "usable receipts"):
            compute([bad, good, clock], {"operation": "count", "receipt_index": 3})
        self.assertEqual(compute([bad, good, clock], {"operation": "count"})["receipt_index"], 2)

    def test_unknown_args_and_operations(self):
        r = [native({"devices": []})]
        with self.assertRaises(ComputeError):
            compute(r, {"operation": "count", "code": "1+1"})
        with self.assertRaises(ComputeError):
            compute(r, {"operation": "eval"})
        with self.assertRaises(ComputeError):
            compute(r, {"operation": "sum"})   # needs field

    def test_no_receipts(self):
        with self.assertRaises(ComputeError):
            compute([], {"operation": "count"})


class Classification(unittest.TestCase):
    def test_local_tool_is_read_only(self):
        self.assertTrue(is_read_only_review_tool(TOOL_NAME))


class LiveCaptureShapes(unittest.TestCase):
    """Shapes from the alpha.156 live captures, with fictional values."""

    def test_nested_string_battery_counts_exactly(self):
        devices = []
        for i, b in enumerate(["94", "80", "79", "95", "85", "100", "90", "94", "81", "50"]):
            devices.append({"id": str(i), "currentStates": {"battery": b}})
        devices += [{"id": f"n{i}", "currentStates": {}} for i in range(20)]
        rec = [native({"devices": devices, "count": 30, "total": 30})]
        inrange = compute(rec, {"operation": "count", "where": [
            {"field": "currentStates.battery", "op": "gte", "value": 80},
            {"field": "currentStates.battery", "op": "lte", "value": 94}]})
        self.assertEqual(inrange["count"], 6)   # 94,80,85,90,94,81
        none = compute(rec, {"operation": "count", "where": [
            {"field": "currentStates.battery", "op": "missing"}]})
        self.assertEqual(none["count"], 20)

    def test_newest_first_events_skipped_row_gap_is_not_reported(self):
        times = ["15:50:08.121", "15:49:02.667", "15:48:42.144", "15:47:46.649",
                 "15:47:45.550", "15:47:12.918", "15:30:57.123", "15:30:25.685",
                 "15:23:44.757", "15:23:08.671"]
        events = [{"name": "motion", "date": f"2026-11-24T{t}+0000"} for t in times]
        out = compute([native({"device": "x", "events": events})],
                      {"operation": "time_gaps", "field": "date", "limit": 3})
        self.assertEqual([g["seconds"] for g in out["largest_gaps"]],
                         [975.795, 400.928, 65.454])
        # a gap that skips the 15:48:42 row (76.018 s) must never appear
        self.assertNotIn(76.018, [g["seconds"] for g in out["largest_gaps"]])


class RowsHint(unittest.TestCase):
    def test_hint_names_receipt_path_and_nested_fields(self):
        payload = {"devices": [{"id": str(i), "currentStates": {"battery": "9"}}
                               for i in range(12)]}
        res = {"content": [{"type": "text", "text": json.dumps(payload)}]}
        hint = rows_hint(res, 4)
        self.assertEqual(hint["receipt_index"], 4)
        self.assertEqual(hint["rows_path"], "content.0.text.devices")
        self.assertEqual(hint["rows_returned"], 12)
        self.assertIn("currentStates.battery", hint["field_names_seen"])
        self.assertIn(TOOL_NAME, hint["use"])

    def test_no_hint_for_short_lists_or_scalars(self):
        res = {"content": [{"type": "text", "text": json.dumps({"devices": [{"id": 1}] * 9})}]}
        self.assertIsNone(rows_hint(res, 1))
        self.assertIsNone(rows_hint({"content": [{"type": "text", "text": "ok"}]}, 1))

    def test_hint_does_not_disturb_later_computation(self):
        payload = {"devices": [{"id": str(i), "v": i} for i in range(12)]}
        res = {"content": [{"type": "text", "text": json.dumps(payload)}]}
        wrapped = dict(res, client_row_compute_hint=rows_hint(res, 1))
        r = {"name": "hub_list_devices", "arguments": {}, "success": True,
             "result_kind": "tool_result", "response": json.dumps(wrapped)}
        out = compute([r], {"operation": "sum", "field": "v"})
        self.assertEqual(out["result"], 66)
        self.assertEqual(out["rows_in_list"], 12)


class PartialCoverageNote(unittest.TestCase):
    def receipts(self, partial=True):
        src = {"name": "hub_get_logs", "success": True, "result_kind": "tool_result",
               "row_coverage": {"rows_returned": 50, "source_reported_total": 189, "partial": partial}}
        comp = {"name": "homebrain_compute_receipt", "success": True, "result_kind": "local_compute",
                "arguments": {"receipt_index": 1, "operation": "max", "field": "stateSize"}}
        return [src, comp]

    def test_note_added_for_partial_source(self):
        from receipt_compute import partial_coverage_note
        note = partial_coverage_note(self.receipts())
        self.assertIn("50 of 189 rows", note)
        self.assertIn("hub_get_logs", note)

    def test_no_note_when_complete_or_no_compute(self):
        from receipt_compute import partial_coverage_note
        self.assertIsNone(partial_coverage_note(self.receipts(partial=False)))
        self.assertIsNone(partial_coverage_note(self.receipts()[:1]))


class RowCoverage(unittest.TestCase):
    def result(self, total, cursor=None):
        rows = [{"name": f"d{i}", "stateSize": 1000 + i} for i in range(12)]
        body = {"modes": {"devices": {"total": total, "entries": rows}}}
        if cursor:
            body["modes"]["devices"]["nextCursor"] = cursor
        return {"content": [{"type": "text", "text": json.dumps(body)}]}

    def test_partial_page_is_reported_with_cursor(self):
        from receipt_compute import rows_hint
        cov = rows_hint(self.result(293, "12"), 1)["coverage"]
        self.assertTrue(cov["partial"])
        self.assertEqual((cov["rows_returned"], cov["source_reported_total"], cov["next_cursor"]),
                         (12, 293, "12"))

    def test_complete_page_is_not_partial(self):
        from receipt_compute import rows_hint
        self.assertFalse(rows_hint(self.result(12), 1)["coverage"]["partial"])

    def test_no_total_means_no_coverage_claim(self):
        from receipt_compute import rows_hint
        rows = [{"a": i} for i in range(12)]
        res = {"content": [{"type": "text", "text": json.dumps({"entries": rows})}]}
        self.assertNotIn("coverage", rows_hint(res, 1))

    def test_byte_fields_get_kb_conversions(self):
        rec = {"name": "hub_get_logs", "success": True, "result_kind": "tool_result",
               "response": json.dumps(self.result(12))}
        out = compute([rec], {"operation": "max", "field": "stateSize"})
        self.assertEqual(out["unit_conversions_from_bytes"]["result"]["KB_decimal"], 1.011)


class MemoryHistoryWindow(unittest.TestCase):
    def receipt(self):
        rows = [{"timestamp": f"11-24 {h:02d}:{m:02d}:00", "freeMemoryKB": v}
                for h, m, v in [(18, 10, 1000), (18, 30, 900), (18, 35, 800), (19, 0, 700)]]
        outer = {"content": [{"type": "text", "text": json.dumps({"entries": rows})}],
                 "client_cpu_load_context": {"returned_samples": [{"load": 1}] * 10}}
        return {"name": "hub_get_memory_history", "arguments": {}, "success": True,
                "result_kind": "tool_result", "response": json.dumps(outer)}

    def test_client_annotation_lists_are_not_source_rows(self):
        out = compute([self.receipt()], {"operation": "mean", "field": "freeMemoryKB"})
        self.assertEqual(out["rows_in_list"], 4)
        self.assertEqual(out["result"], 850)

    def test_month_day_stamp_window_filters_rows(self):
        out = compute([self.receipt()], {
            "operation": "mean", "field": "freeMemoryKB",
            "where": [{"field": "timestamp", "op": "gte", "value": "11-24 18:20:00"}]})
        self.assertEqual(out["rows_after_filter"], 3)
        self.assertEqual(out["result"], 800)
        self.assertEqual(out["min"], 700)

    def test_kb_fields_get_decimal_and_binary_conversions(self):
        out = compute([self.receipt()], {"operation": "mean", "field": "freeMemoryKB"})
        self.assertEqual(out["unit_conversions_from_KB"]["result"]["MB_decimal"], 0.85)
        self.assertAlmostEqual(out["unit_conversions_from_KB"]["result"]["MiB_binary"], 0.830078, places=5)


class GapsInTimeOrder(unittest.TestCase):
    def test_time_gaps_lists_every_gap_oldest_first(self):
        rows = [{"date": "2026-11-24T10:00:30.000+0000"}, {"date": "2026-11-24T10:00:00.000+0000"},
                {"date": "2026-11-24T10:05:00.000+0000"}]
        out = compute([native({"events": rows})], {"operation": "time_gaps", "field": "date"})
        self.assertEqual([g["seconds"] for g in out["gaps_in_time_order"]], [30.0, 270.0])
        self.assertEqual([g["seconds"] for g in out["largest_gaps"]], [270.0, 30.0])


class PagedReceipts(unittest.TestCase):
    """The alpha.157 capture: one 181-device inventory returned as two pages."""

    def pages(self, overlap=False):
        p1 = [{"id": str(i), "currentStates": ({"battery": str(60 + (i % 40))} if i % 3 == 0 else {})}
              for i in range(100)]
        p2 = [{"id": str(i), "currentStates": ({"battery": str(60 + (i % 40))} if i % 3 == 0 else {})}
              for i in range(99 if overlap else 100, 181)]
        return [native({"devices": p1, "count": 100, "total": 181, "hasMore": True}),
                native({"devices": p2, "count": len(p2), "total": 181, "hasMore": False})]

    def test_one_page_alone_undercounts_two_pages_are_exact(self):
        recs = self.pages()
        where = [{"field": "currentStates.battery", "op": "gte", "value": 80},
                 {"field": "currentStates.battery", "op": "lte", "value": 94}]
        one = compute(recs, {"operation": "count", "receipt_index": 1, "where": where})["count"]
        both = compute(recs, {"operation": "count", "receipt_indexes": [1, 2], "where": where})
        expected = sum(1 for i in range(181) if i % 3 == 0 and 80 <= 60 + (i % 40) <= 94)
        self.assertEqual(both["count"], expected)
        self.assertLess(one, both["count"])
        self.assertEqual(both["rows_in_list"], 181)
        self.assertEqual([r["rows"] for r in both["receipts_combined"]], [100, 81])

    def test_overlapping_pages_count_each_id_once(self):
        out = compute(self.pages(overlap=True), {"operation": "count", "receipt_indexes": [1, 2]})
        self.assertEqual(out["rows_in_list"], 181)
        self.assertEqual(out["duplicate_id_rows_removed"], 1)

    def test_bad_multi_arguments_are_refused(self):
        recs = self.pages()
        for bad in ([1], [1, 1], [1, 9], "1,2"):
            with self.assertRaises(ComputeError):
                compute(recs, {"operation": "count", "receipt_indexes": bad})
        with self.assertRaises(ComputeError):
            compute(recs, {"operation": "count", "receipt_index": 1, "receipt_indexes": [1, 2]})


if __name__ == "__main__":
    unittest.main()
