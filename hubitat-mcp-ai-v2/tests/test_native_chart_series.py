"""External diagnostics native source-cadence regression for v2 only.

Synthetic records. No live hub or network access.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest


_PATH = Path(__file__).resolve().parents[1] / "rootfs" / "app" / "external_hub_diagnostics.py"
_SPEC = importlib.util.spec_from_file_location("v2_native_diagnostics_source_test", _PATH)
_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_module)
summarize_history_samples = _module.summarize_history_samples


def stamp(value):
    return value.isoformat(timespec="milliseconds")


class NativeSeriesTests(unittest.TestCase):
    def test_native_short_range_returns_distinct_source_samples_not_repeated_polls(self):
        """Cached 5m rows must not fragment every genuine source line segment."""
        start = datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(30):  # 15 min of 30s probes, 3 actual 5m samples
            rows.append({
                "recorded_at": stamp(start + timedelta(seconds=i * 30)),
                "reachable": 1,
                "native_sample_label": "native-%02d" % (i // 10),
                "native_load5": (0.63, 1.17, 0.95)[i // 10],
                "native_load_pct": (15.8, 29.2, 23.8)[i // 10],
                "java_free_mb": (125.0, 123.4, 124.0)[i // 10],
            })
        for metric in ("native_load5", "native_load_pct", "java_free_mb"):
            with self.subTest(metric=metric):
                result = summarize_history_samples(
                    iter([dict(x) for x in rows]), metric=metric,
                    start=start, finish=start + timedelta(hours=1),
                    probe_seconds=30,
                )
                self.assertEqual(result["source_sample_count"], 30)
                self.assertEqual(result["observed_metric_points"], 3)
                self.assertFalse(result["downsampled"])
                self.assertEqual([p["native_sample_label"] for p in result["samples"]],
                                 ["native-00", "native-01", "native-02"])
                self.assertEqual([p["diag_segment"] for p in result["samples"]],
                                 [0, 0, 0])
                self.assertEqual(result["samples"][0]["recorded_at"], rows[0]["recorded_at"])
                self.assertEqual(result["samples"][1]["recorded_at"], rows[10]["recorded_at"])

    def test_native_outage_or_missing_reading_breaks_line_without_fabricated_values(self):
        start = datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc)
        spec = [
            (0, 1, "s0", .5),
            (30, 1, "s0", .5),
            (300, 1, "s1", .6),
            (330, 1, "s1", .6),
            (360, 0, None, None),
            (390, 1, "s1", .6),
            (600, 1, "s2", .9),
            (630, 1, "s2", .9),
            (2400, 1, "s3", 1.0),  # true source gap > 15 minutes
        ]
        rows = [{"recorded_at": stamp(start + timedelta(seconds=sec)),
                 "reachable": reachable, "native_sample_label": label,
                 "native_load5": value} for sec, reachable, label, value in spec]
        out = summarize_history_samples(
            iter(rows), metric="native_load5",
            start=start, finish=start + timedelta(hours=1), probe_seconds=30,
        )
        self.assertEqual(out["source_sample_count"], len(rows))
        self.assertEqual(out["observed_metric_points"], 4)
        self.assertEqual([r["native_sample_label"] for r in out["samples"]],
                         ["s0", "s1", "s2", "s3"])
        self.assertEqual([r["diag_segment"] for r in out["samples"]],
                         [0, 0, 1, 2])
        self.assertEqual([r["native_load5"] for r in out["samples"]],
                         [.5, .6, .9, 1.0])

    def test_probe_cadence_and_outage_rows_preserved_for_real_os_metric(self):
        start = datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc)
        rows = [
            {"recorded_at": stamp(start + timedelta(seconds=i * 30)),
             "reachable": 0 if i == 2 else 1,
             "free_os_mb": None if i == 2 else 840.0 + i}
            for i in range(6)
        ]
        result = summarize_history_samples(
            iter(rows), metric="free_os_mb",
            start=start, finish=start + timedelta(hours=1), probe_seconds=30,
        )
        self.assertEqual(result["source_sample_count"], 6)
        self.assertEqual(result["observed_metric_points"], 5)
        self.assertEqual(len(result["samples"]), 6)
        self.assertEqual(result["samples"][2]["reachable"], 0)
        self.assertGreater(result["samples"][3]["diag_segment"],
                           result["samples"][1]["diag_segment"])

    def test_native_load_percentage_is_existing_backend_core_normalisation(self):
        # Original raw native reading remains intact; the percentage is a
        # derived 5m load-equivalent, never a CPU-utilisation measurement.
        recorder = object.__new__(_module.ExternalHubDiagnostics)
        recorder.cpu_cores = 4
        row = {"native_load5": 0.6, "native_sample_label": "source-at-11-08-18:49:56"}
        percent = recorder._with_load_pct(row)
        self.assertEqual(percent["native_load_pct"], 15.0)
        self.assertEqual(percent["native_load5"], 0.6)
        self.assertNotIn("native_load_pct", row)
        self.assertEqual(percent["native_sample_label"], row["native_sample_label"])
        self.assertEqual(recorder._with_load_pct({"native_load5": 4.8})["native_load_pct"], 120.0)
        self.assertIsNone(recorder._with_load_pct({"native_load5": -1})["native_load_pct"])
        recorder.cpu_cores = 8
        self.assertEqual(recorder._with_load_pct(row)["native_load_pct"], 7.5)

    def test_native_long_window_downsamples_real_distinct_sources_only(self):
        start = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
        rows = [
            {"recorded_at": stamp(start + timedelta(seconds=i * 30)),
             "reachable": 1, "native_sample_label": "sample-%03d" % (i // 10),
             "native_load5": 2.4 if i // 10 == 25 else .6}
            for i in range(4000)
        ]
        result = summarize_history_samples(
            iter(rows), metric="native_load5",
            start=start, finish=start + timedelta(days=2),
            probe_seconds=30, raw_limit=100,
        )
        self.assertTrue(result["downsampled"])
        self.assertEqual(result["source_sample_count"], 4000)
        self.assertEqual(result["observed_metric_points"], 400)
        self.assertEqual(max(r["native_load5"] for r in result["samples"]), 2.4)
        self.assertEqual(len({r["native_sample_label"] for r in result["samples"]}),
                         len(result["samples"]))


    def test_native_csv_recovers_peak_between_polls_using_original_hub_labels(self):
        observed = "2026-11-09T22:26:53+00:00"
        csv = (
            "11-09 22:15:10,870400,0.6,262144,131072\n"
            "11-09 22:20:10,1303347,0.8,262144,131072\n"
            "11-09 22:20:10,1303347,0.8,262144,131072\n"  # same source
            "11-09 22:25:10,945152,4.8,262144,131072\n"
        )
        rows = _module.parse_native_history(
            csv, collected_at=observed, hub_timezone="Europe/London",
            retention_days=30,
        )
        self.assertEqual(len(rows), 3)
        peak = max(rows, key=lambda r: r["native_free_os_mb"])
        self.assertEqual(peak["native_free_os_mb"], 1272.8)
        self.assertEqual(peak["recorded_at"], "2026-11-09T22:20:10.000+00:00")
        self.assertEqual(peak["collected_at"], observed)
        self.assertEqual(peak["native_sample_label"], "11-09 22:20:10")
        self.assertEqual(peak["timestamp_basis"], "native_label_hub_timezone")

    def test_native_time_requires_valid_timezone_and_nonfuture_source(self):
        observed = "2026-11-09T22:26:53+00:00"
        self.assertIsNone(_module.native_sample_time(
            "11-09 22:20:10", observed, "Invalid/Timezone", 30))
        self.assertIsNone(_module.native_sample_time(
            "11-09 23:59:10", observed, "Europe/London", 30))
        self.assertEqual(_module.native_sample_time(
            "11-09 22:20:10", observed, "Europe/London", 30),
            "2026-11-09T22:20:10.000+00:00")
        # Summer hub-local time is NOT UTC.
        self.assertEqual(_module.native_sample_time(
            "07-01 21:20:10", "2026-07-01T21:26:53+00:00",
            "Europe/London", 30),
            "2026-07-01T20:20:10.000+00:00")

    def test_native_peak_persists_separately_and_timeline_retains_source_time(self):
        now = datetime.now(timezone.utc)
        zone = ZoneInfo("Europe/London")
        source_times = [now - timedelta(minutes=11),
                        now - timedelta(minutes=6),
                        now - timedelta(minutes=1)]
        lines = [
            f"{t.astimezone(zone):%m-%d %H:%M:%S},{free},0.8,262144,131072"
            for t, free in zip(source_times, (870400, 1303347, 945152))
        ]
        captured = stamp(now)
        native = _module.parse_native_history(
            "\n".join(lines), collected_at=captured,
            hub_timezone="Europe/London", retention_days=30,
        )
        self.assertEqual(len(native), 3)
        with TemporaryDirectory() as folder:
            recorder = _module.ExternalHubDiagnostics(
                enabled=True, hub_url="http://192.168.1.239",
                path=Path(folder) / "diagnostics.sqlite3",
                hub_timezone="Europe/London",
            )
            recorder._initialize()
            recorder._save(
                {"recorded_at":captured, "reachable":1, "free_os_mb":230.0},
                opened=None, recovered=False, native_samples=native,
            )
            recorder._save(
                {"recorded_at":stamp(now + timedelta(milliseconds=1)),
                 "reachable":0, "free_os_mb":None},
                opened=stamp(now), recovered=False,
            )
            timeline = recorder.timeline(1)
            external = timeline["metrics"]["free_os_mb"]["samples"]
            rows = timeline["metrics"]["native_free_os_mb"]["samples"]
            self.assertTrue(any(r["free_os_mb"] == 230.0 for r in external))
            self.assertEqual(len(rows), 3)
            self.assertEqual(max(r["native_free_os_mb"] for r in rows), 1272.8)
            self.assertEqual(timeline["metrics"]["native_free_os_mb"]["timestamp_basis"],
                             "native_label_hub_timezone")
            self.assertTrue(all(r["collected_at"] == captured for r in rows))
            self.assertEqual(len(timeline["metrics"]["native_load_pct"]["samples"]), 3)
            self.assertEqual(recorder.history(1, "native_free_os_mb")["observed_metric_points"], 3)
            # Replay the same CSV after restart/reconnect: no duplicate history.
            recorder._save(
                {"recorded_at":stamp(now + timedelta(milliseconds=2)),
                 "reachable":1, "free_os_mb":940.0},
                opened=None, recovered=True, native_samples=native,
            )
            self.assertEqual(len(recorder.timeline(1)["metrics"]["native_free_os_mb"]["samples"]), 3)


if __name__ == "__main__":
    unittest.main()
