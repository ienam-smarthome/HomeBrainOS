import asyncio
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from home_knowledge import (BriefingSchedule, HomeKnowledge, HomeNotes, briefing_text,  # noqa: E402
                            clean_notes, profile_text)
from home_overview import summarize_device_inventory  # noqa: E402

run = asyncio.run


def inventory():
    def dev(i, label, **states):
        return {"id": str(i), "label": label, "currentStates": {k: v for k, v in states.items()}}
    import json
    devices = [
        dev(1, "Hall Light", switch="on"), dev(2, "Kettle socket", switch="on"),
        dev(3, "Front Door Contact", contact="closed", battery=12),
        dev(4, "Water leak sensor", water="dry"), dev(5, "Lounge TRV", thermostatOperatingState="heating"),
    ]
    return {"content": [{"type": "text", "text": json.dumps({"devices": devices, "total": 5})}]}


class NotesTests(unittest.TestCase):
    def test_clean_and_limit(self):
        self.assertEqual(clean_notes(" a\x00b\r\nc "), "ab\nc")
        with self.assertRaises(ValueError):
            clean_notes("x" * 3001)
        with self.assertRaises(ValueError):
            clean_notes(5)

    def test_round_trip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            notes = HomeNotes(Path(d) / "n.txt")
            self.assertEqual(notes.load(), "")
            notes.save("Lights are dimmers.")
            self.assertEqual(notes.load(), "Lights are dimmers.")


class ProfileAndContextTests(unittest.TestCase):
    def test_profile_separates_lights_from_sockets(self):
        snap = summarize_device_inventory(inventory())
        text = profile_text(snap)
        self.assertIn("Hall Light", text)
        self.assertNotIn("Kettle socket", text.split("Heating")[0])
        self.assertIn("Lounge TRV", text)
        self.assertIn("Front Door Contact", text)

    def test_context_labels_notes_and_profile_and_survives_refresh_failure(self):
        with tempfile.TemporaryDirectory() as d:
            notes = HomeNotes(Path(d) / "n.txt")
            notes.save("Block switches are internet blockers.")

            async def ok():
                return summarize_device_inventory(inventory())

            async def bad():
                raise RuntimeError("hub down")
            k = HomeKnowledge(notes, ok)
            run(k.refresh())
            ctx = k.context()
            self.assertIn("not tool data", ctx)
            self.assertIn("Observed device profile", ctx)
            k2 = HomeKnowledge(notes, bad)
            run(k2.refresh())
            self.assertIn("internet blockers", k2.context())
            self.assertNotIn("Observed device profile", k2.context())


class BriefingTests(unittest.TestCase):
    def test_briefing_lists_attention_items_only(self):
        snap = summarize_device_inventory(inventory())
        title, body = briefing_text(snap, problems={"internet": "internet unreachable for about 6 min"},
                                    local_now=datetime(2026, 11, 25, 7, 30, tzinfo=ZoneInfo("Europe/London")))
        self.assertIn("Wed 25 Nov, 07:30", title)
        self.assertIn("Front Door Contact 12%", body)
        self.assertIn("Lights on: Hall Light", body)
        self.assertIn("Heating now: Lounge TRV", body)
        self.assertIn("Problem: internet", body)

    def test_quiet_home_says_so(self):
        _, body = briefing_text({"metrics": {}, "inventory_full_coverage_verified": True})
        self.assertIn("Nothing needs attention", body)

    def test_schedule_sends_once_per_day_inside_window(self):
        zone = ZoneInfo("Europe/London")
        clock = {"now": datetime(2026, 11, 25, 7, 0, tzinfo=zone)}
        sent = []

        async def build():
            return "T", "B"

        async def send(t, b):
            sent.append((t, b))
        s = BriefingSchedule(build, send, time_of_day="07:30", timezone="Europe/London", now=lambda: clock["now"])
        self.assertFalse(run(s.tick()))
        clock["now"] = datetime(2026, 11, 25, 7, 31, tzinfo=zone)
        self.assertTrue(run(s.tick()))
        self.assertFalse(run(s.tick()))
        clock["now"] = datetime(2026, 11, 25, 12, 0, tzinfo=zone)
        self.assertFalse(run(s.tick()))
        clock["now"] = datetime(2026, 11, 26, 7, 45, tzinfo=zone)
        self.assertTrue(run(s.tick()))
        self.assertEqual(len(sent), 2)

    def test_failed_send_is_retried_and_reported(self):
        zone = ZoneInfo("Europe/London")
        attempts = []

        async def build():
            return "T", "B"

        async def send(t, b):
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError("offline")
        s = BriefingSchedule(build, send, time_of_day="07:30", timezone="Europe/London",
                             now=lambda: datetime(2026, 11, 25, 7, 40, tzinfo=zone))
        self.assertFalse(run(s.tick()))
        self.assertIn("not sent", s.last_error)
        self.assertTrue(run(s.tick()))
        self.assertIsNone(s.last_error)


if __name__ == "__main__":
    unittest.main()


class HomeWatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_water_alerts_at_once_contact_after_grace_battery_once(self):
        from home_knowledge import HomeWatch
        sent, now = [], [0.0]
        snap = {"metrics": {
            "water_wet": {"members": [{"name": "Kitchen leak", "id": "9"}]},
            "contact_open": {"members": [{"name": "Back door", "id": "4"}]},
            "battery_low": {"members": [{"name": "Hall sensor", "id": "7", "battery_pct": 6.0},
                                        {"name": "Other", "id": "8", "battery_pct": 15.0}]}}}

        async def read(): return snap
        async def notify(t, m): sent.append((t, m))
        w = HomeWatch(read, notify, clock=lambda: now[0])
        await w.tick()
        self.assertEqual([t for t, _ in sent], ["HomeBrainOS: water detected", "HomeBrainOS: battery very low"])
        now[0] = 1900
        await w.tick()
        await w.tick()
        self.assertEqual([t for t, _ in sent].count("HomeBrainOS: left open"), 1)
        self.assertEqual(len(sent), 3)
        snap = {"metrics": {}}
        await w.tick()
        titles = [t for t, _ in sent]
        self.assertIn("HomeBrainOS: water cleared", titles)
        self.assertIn("HomeBrainOS: closed again", titles)

    async def test_failed_delivery_is_retried(self):
        from home_knowledge import HomeWatch
        calls = []

        async def read(): return {"metrics": {"water_wet": {"members": [{"name": "A", "id": "1"}]}}}
        async def notify(t, m):
            calls.append(t)
            if len(calls) == 1:
                raise RuntimeError("offline")
        w = HomeWatch(read, notify)
        await w.tick()
        self.assertEqual(w.status()["undelivered"], 1)
        await w.tick()
        self.assertEqual(w.status()["undelivered"], 0)
        self.assertEqual(len(calls), 2)
