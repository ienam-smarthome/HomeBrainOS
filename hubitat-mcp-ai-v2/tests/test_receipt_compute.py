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

from receipt_compute import ComputeError, TOOL_NAME, compute, field_meaning_prose_note, partial_coverage_note, rows_hint  # noqa: E402
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


class SortRowsGetKbColumn(unittest.TestCase):
    def test_sorted_rows_carry_decimal_kb_for_byte_fields(self):
        rows = [{"name": "a", "stateSize": 79818}, {"name": "b", "stateSize": 37754}]
        rec = {"name": "hub_get_logs", "success": True, "result_kind": "tool_result",
               "response": json.dumps({"entries": rows})}
        out = compute([rec], {"operation": "sort", "field": "stateSize", "descending": True,
                              "rows_path": "entries"})
        self.assertEqual(out["rows"][0]["client_stateSize_KB_decimal"], 79.818)
        self.assertNotIn("client_stateSize_KB_decimal", rows[0])


class UnitConversionNote(unittest.TestCase):
    def test_free_memory_kb_gets_decimal_mb(self):
        from receipt_compute import unit_conversion_note
        body = {"current": {"freeMemoryKB": 881592, "internalTempC": 43.0}}
        res = {"content": [{"type": "text", "text": json.dumps(body)}]}
        note = unit_conversion_note(res)
        self.assertEqual(note["fields"]["freeMemoryKB"]["MB_decimal"], 881.592)
        self.assertEqual(note["fields"]["freeMemoryKB"]["MiB_binary"], 860.93)

    def test_no_kb_fields_no_note(self):
        from receipt_compute import unit_conversion_note
        self.assertIsNone(unit_conversion_note({"a": 1, "b": {"c": "x"}}))


class UnrunToolNote(unittest.TestCase):
    NAMES = {"hub_list_device_events", "hub_list_devices", "hub_get_metrics"}

    def test_names_mentioned_without_a_successful_receipt(self):
        from receipt_compute import unrun_tool_note
        receipts = [{"name": "hub_list_devices", "success": True}]
        answer = "Counts came from hub_list_device_events(deviceId=1) and hub_list_devices."
        note = unrun_tool_note(answer, receipts, self.NAMES)
        self.assertIn("hub_list_device_events", note)
        self.assertNotIn("hub_list_devices,", note)

    def test_failed_receipt_does_not_count_as_run(self):
        from receipt_compute import unrun_tool_note
        receipts = [{"name": "hub_get_metrics", "success": False}]
        self.assertIn("hub_get_metrics", unrun_tool_note("hub_get_metrics shows 5 values", receipts, self.NAMES))

    def test_no_note_when_all_mentioned_tools_ran_or_none_mentioned(self):
        from receipt_compute import unrun_tool_note
        receipts = [{"name": "hub_get_metrics", "success": True}]
        self.assertIsNone(unrun_tool_note("free memory from hub_get_metrics", receipts, self.NAMES))
        self.assertIsNone(unrun_tool_note("nothing relevant", receipts, self.NAMES))

    def test_partial_name_is_not_matched(self):
        from receipt_compute import unrun_tool_note
        self.assertIsNone(unrun_tool_note("hub_list_devices_extra", [], {"hub_list_devices"}))


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


class SourceOrderedCoverage(unittest.TestCase):
    def _result(self, sizes, total=293):
        rows = [{"id": i, "stateSize": s} for i, s in enumerate(sizes)]
        body = {"modes": {"devices": {"total": total, "entries": rows, "nextCursor": "50"}}}
        return {"content": [{"type": "text", "text": json.dumps(body)}]}

    def test_rows_that_follow_the_named_sort_are_marked_source_ordered(self):
        sizes = list(range(60, 10, -1))
        hint = rows_hint(self._result(sizes), 2, {"mode": ["devices"], "sortBy": "stateSize", "limit": 100})
        cov = hint["coverage"]
        self.assertEqual(cov["ordered_by_source"],
                         {"field": "stateSize", "argument": "sortBy", "direction": "descending"})
        self.assertIn("leading rows of the source's own ordering", cov["use"])
        self.assertTrue(cov["partial"])

    def test_unsorted_rows_or_no_sort_argument_stay_plain_partial(self):
        shuffled = [5, 9, 1, 7, 3, 8, 2, 6, 4, 10, 11, 12]
        self.assertNotIn("ordered_by_source",
                         rows_hint(self._result(shuffled), 1, {"sortBy": "stateSize"})["coverage"])
        self.assertNotIn("ordered_by_source",
                         rows_hint(self._result(sorted(shuffled, reverse=True)), 1, {"limit": 50})["coverage"])

    def test_footnote_uses_source_order_wording_for_matching_compute(self):
        sizes = list(range(60, 10, -1))
        read = {"name": "hub_get_logs", "success": True,
                "arguments": {"mode": ["devices"], "sortBy": "stateSize", "limit": 100},
                "row_coverage": rows_hint(self._result(sizes), 1,
                                          {"sortBy": "stateSize"})["coverage"]}
        compute = {"name": TOOL_NAME, "success": True, "result_kind": "local_compute",
                   "arguments": {"receipt_index": 1, "operation": "sort", "field": "stateSize"}}
        note = partial_coverage_note([read, compute])
        self.assertIn("already ordered descending by its own `stateSize` sort", note)
        self.assertIn("not independently verified", note)
        self.assertNotIn("remaining rows were not read", note)
        other = dict(compute, arguments={"receipt_index": 1, "operation": "sort", "field": "id"})
        self.assertIn("remaining rows were not read", partial_coverage_note([read, other]))


class FieldMeaningProseNote(unittest.TestCase):
    RECEIPTS = [{"name": "hub_get_logs", "success": True,
                 "field_meaning_fields": ["pct", "stateSize", "total"]}]

    def test_flags_unnegated_memory_claim_about_state_size(self):
        answer = ("The view does not give direct RAM usage; it reports stateSize, which "
                  "therefore correlates with memory consumption.")
        note = field_meaning_prose_note(answer, self.RECEIPTS)
        self.assertIn("`stateSize`", note)
        self.assertIn("none is RAM or memory use", note)
        self.assertIn("No memory source was read", note)

    def test_quiet_when_prose_already_negates_or_no_field_note(self):
        ok = "stateSize is bytes of stored state, not memory use."
        self.assertIsNone(field_meaning_prose_note(ok, self.RECEIPTS))
        bad = "stateSize is the memory each device uses."
        self.assertIsNone(field_meaning_prose_note(bad, [{"name": "hub_get_logs", "success": True}]))
        self.assertIsNone(field_meaning_prose_note("Memory is fine.", self.RECEIPTS))

    def test_names_memory_source_when_it_was_read(self):
        receipts = self.RECEIPTS + [{"name": "hub_get_metrics", "success": True}]
        note = field_meaning_prose_note("stateSize shows memory per device.", receipts)
        self.assertIn("hub_get_memory_history/hub_get_metrics", note)


class AnnotationOrderAndCapturedProse(unittest.TestCase):
    def test_client_annotations_come_first_in_model_json(self):
        from agent import compact_tool_result
        body = compact_tool_result({"content": [{"text": "x" * 50}],
                                    "client_row_compute_hint": {"receipt_index": 1},
                                    "_meta": {}})
        self.assertLess(body.index("client_row_compute_hint"), body.index('"content"'))
        self.assertEqual(json.loads(body)["content"][0]["text"], "x" * 50)

    def test_alpha175_capture_sentence_is_now_flagged(self):
        answer = ("While it isn’t a direct measurement of RAM, it is the primary size-like "
                  "metric and therefore provides a reliable indication of which devices are "
                  "occupying the most memory resources.")
        receipts = [{"name": "hub_get_logs", "success": True, "field_meaning_fields": ["stateSize"]}]
        self.assertIn("none is RAM or memory use", field_meaning_prose_note(answer, receipts))


class PartialRankingWarning(unittest.TestCase):
    CATALOG = [{"name": "hub_get_logs", "inputSchema": {"properties": {"mode": {}, "limit": {}, "sortBy": {}}}}]
    SOURCE = {"name": "hub_get_logs", "arguments": {"mode": ["apps"], "limit": 0},
              "row_coverage": {"rows_returned": 50, "source_reported_total": 189, "partial": True}}

    def test_warns_when_sort_offered_but_unused(self):
        from receipt_compute import partial_ranking_warning
        warn = partial_ranking_warning(self.SOURCE, {"operation": "sort", "field": "stateSize"}, self.CATALOG)
        self.assertEqual(warn["sort_parameter_offered"], "sortBy")
        self.assertIn('sortBy="stateSize"', warn["use"])
        self.assertIn("first 50 rows of 189", warn["use"])

    def test_quiet_when_sorted_complete_unoffered_or_not_a_ranking(self):
        from receipt_compute import partial_ranking_warning
        sorted_src = dict(self.SOURCE, arguments={"sortBy": "stateSize"})
        self.assertIsNone(partial_ranking_warning(sorted_src, {"operation": "sort"}, self.CATALOG))
        full = dict(self.SOURCE, row_coverage={"rows_returned": 50, "partial": False})
        self.assertIsNone(partial_ranking_warning(full, {"operation": "sort"}, self.CATALOG))
        self.assertIsNone(partial_ranking_warning(self.SOURCE, {"operation": "sort"}, [{"name": "hub_get_logs", "inputSchema": {"properties": {"mode": {}}}}]))
        self.assertIsNone(partial_ranking_warning(self.SOURCE, {"operation": "count"}, self.CATALOG))


class UnitsPathsAndNudgeGate(unittest.TestCase):
    def test_rows_path_tolerates_missing_modes_segment_and_lists_keys(self):
        import json as _j
        from receipt_compute import _receipt_rows, ComputeError
        payload = {"content": [{"text": _j.dumps({"modes": {"apps": {"entries": [{"a": 1}]}}})}]}
        receipt = {"response": _j.dumps({"mcp_result": payload})}
        path, rows = _receipt_rows(receipt, "content.0.text.apps.entries")
        self.assertEqual(rows, [{"a": 1}])
        with self.assertRaises(ComputeError) as ctx:
            _receipt_rows(receipt, "content.0.text.nope.entries")
        self.assertIn("keys here: modes", str(ctx.exception))

    def test_nudge_gate_skips_plain_lists_but_not_figures(self):
        from receipt_compute import draft_states_aggregate
        self.assertFalse(draft_states_aggregate("Front door: closed. Fridge door: closed. Water sensor: dry."))
        self.assertTrue(draft_states_aggregate("The top three apps are listed below."))
        self.assertTrue(draft_states_aggregate("Free memory is 839 MB."))
        self.assertTrue(draft_states_aggregate("There are 12 devices offline."))

    def test_temperature_unit_note(self):
        from receipt_compute import temperature_unit_note
        bare = [{"response": '{"temperature": 21.1}'}]
        self.assertIn("not read from the hub", temperature_unit_note("Hallway 21.1 °F", bare))
        self.assertEqual(temperature_unit_note("Hallway 21.1 °C", [{"response": '{"unit": "°C"}'}]), "")
        self.assertEqual(temperature_unit_note("Hallway 21.1 degrees", bare), "")


class FilterScopeAndHeldBackCoverage(unittest.TestCase):
    def test_filter_scope_note_uses_only_call_arguments(self):
        from receipt_compute import filter_scope_note
        note = filter_scope_note("hub_list_devices", {"changedSince": "2026-11-25T12:00:00Z", "format": "summary"})
        self.assertEqual(note["filters_applied"], {"changedSince": "2026-11-25T12:00:00Z"})
        self.assertIn("not the whole inventory", note["meaning"])
        self.assertIsNone(filter_scope_note("hub_list_devices", {"format": "summary"}))
        self.assertIsNone(filter_scope_note("hub_get_logs", {"changedSince": "x"}))

    def test_held_back_ranking_adds_no_coverage_footnote(self):
        from receipt_compute import partial_coverage_note, TOOL_NAME
        receipts = [
            {"name": "hub_get_logs", "success": True, "row_coverage": {"partial": True, "rows_returned": 50,
                                                                       "source_reported_total": 293}},
            {"name": TOOL_NAME, "success": True, "result_kind": "local_compute", "ranking_held_back": True,
             "arguments": {"receipt_index": 1, "operation": "sort", "field": "stateSize"}},
        ]
        self.assertIsNone(partial_coverage_note(receipts))


class ListDevicesArgNormalisation(unittest.TestCase):
    CAT = [{"name": "hub_list_devices", "inputSchema": {"properties": {"format": {}, "limit": {}, "attributeNames": {}}}}]

    def test_attribute_names_with_detailed_becomes_summary(self):
        from receipt_compute import normalize_list_devices_args
        out, note = normalize_list_devices_args(
            "hub_list_devices", {"format": "detailed", "attributeNames": ["battery"]}, self.CAT)
        self.assertEqual(out["format"], "summary")
        self.assertEqual(out["attributeNames"], ["battery"])
        self.assertIn("summary", note["changes"][0])

    def test_unbounded_detailed_gets_a_limit_and_other_calls_are_untouched(self):
        from receipt_compute import normalize_list_devices_args
        out, note = normalize_list_devices_args("hub_list_devices", {"format": "detailed"}, self.CAT)
        self.assertEqual(out["limit"], 40)
        same, none = normalize_list_devices_args("hub_list_devices", {"format": "summary"}, self.CAT)
        self.assertIsNone(none)
        self.assertEqual(same, {"format": "summary"})
        self.assertEqual(normalize_list_devices_args("hub_get_logs", {"format": "detailed"}, self.CAT)[1], None)


class YearAndChangedSinceTests(unittest.TestCase):
    def test_year_not_in_results_is_flagged(self):
        from receipt_compute import unsupported_year_note
        receipts = [{"response": '{"ts":"2026-11-25T15:00:00"}', "arguments": {}}]
        self.assertEqual(unsupported_year_note("At 2026-11-25 free memory fell", receipts), "")
        self.assertIn("2025", unsupported_year_note("On 2025-11-25 it fell", receipts))

    def test_numeric_changed_since_refused(self):
        from receipt_compute import changed_since_refusal
        self.assertIsNotNone(changed_since_refusal("hub_list_devices", {"changedSince": 1732559355601}))
        self.assertIsNone(changed_since_refusal("hub_list_devices", {"changedSince": "2026-11-25T14:00:00+00:00"}))


class UnrunMentionTests(unittest.TestCase):
    def test_advice_mention_is_not_footnoted_but_figure_claim_is(self):
        from receipt_compute import unrun_tool_note
        names = ["hub_get_device"]
        self.assertIsNone(unrun_tool_note("For details run hub_get_device with the id.", [], names))
        self.assertIsNotNone(unrun_tool_note("hub_get_device shows battery 12%.", [], names))
