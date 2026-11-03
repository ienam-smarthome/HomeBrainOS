"""Fail-closed one-shot form discovery using synthetic typed settings.

No real Hubitat writes, app IDs, credentials or installed inference; matches
only the contrast between dated and undated native read-only settings.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from native_oneshot_date_contract import inspect_native_one_shot_date_field
from rule_authoring_service import RuleAuthoringService

UNDATED = {
    "rule_id": 4163, "success": True,
    "settings": [
        {"name": "tCapab1", "type": "enum",
         "value": "Certain Time (and optional date)"},
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time", "value": "17:30"},
        {"name": "date1", "type": "bool", "value": False},
        {"name": "onOff.1", "type": "bool", "value": False},
    ],
}
DATED = {
    "rule_id": 4321, "success": True,
    "settings": [
        {"name": "tCapab1", "type": "enum",
         "value": "Certain Time (and optional date)"},
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time", "value": "17:30"},
        {"name": "date1", "type": "bool", "value": True},
        {"name": "atDate1", "type": "date", "value": "2026-11-07"},
        {"name": "onOff.1", "type": "bool", "value": False},
    ],
}


def test_unique_typed_dated_field_is_discovery_only():
    result = inspect_native_one_shot_date_field(
        dated_read=DATED, undated_read=UNDATED
    )
    assert result.date_flag == {"name": "date#", "type": "bool"}
    assert result.date_value == {
        "name": "atDate#", "type": "date", "fmt": "YYYY-MM-DD"
    }
    assert result.gaps == ("native_oneshot_create_placeholder_and_readback_unverified",)
    assert result.write_ready is False


@pytest.mark.parametrize("change", [
    lambda d: d.pop("settings"),
    lambda d: d.__setitem__("success", False),
    lambda d: d.__setitem__("rule_id", 4163),
    lambda d: d["settings"].__setitem__(3, {"name": "date1", "type": "bool", "value": False}),
    lambda d: d["settings"].__setitem__(4, {"name": "atDate1", "type": "date", "value": "tomorrow"}),
    lambda d: d["settings"].__setitem__(4, {"name": "atDate1", "type": "date", "value": "2026-02-30"}),
    lambda d: d["settings"].append({"name": "atDate1", "type": "date", "value": "2026-11-07"}),
    lambda d: d["settings"].append({"name": "scheduleDate1", "type": "date", "value": "2026-11-08"}),
    lambda d: d["settings"].__setitem__(1, {"name": "time1", "type": "enum", "value": "Sunrise"}),
])
def test_invalid_or_ambiguous_source_does_not_guess_date_field(change):
    dated = deepcopy(DATED)
    change(dated)
    result = inspect_native_one_shot_date_field(dated_read=dated, undated_read=UNDATED)
    assert result.date_value is None
    assert result.gaps == ("native_oneshot_date_field_unverified",)
    assert not result.write_ready


def test_identical_or_untrusted_undated_sample_cannot_attest_change():
    undated = deepcopy(UNDATED)
    undated["settings"][3]["value"] = True
    assert inspect_native_one_shot_date_field(
        dated_read=DATED, undated_read=undated
    ).date_value is None
    undated = deepcopy(UNDATED)
    undated["settings"].append(
        {"name": "atDate1", "type": "date", "value": "2026-11-06"}
    )
    assert inspect_native_one_shot_date_field(
        dated_read=DATED, undated_read=undated
    ).date_value is None


def test_ceiled_elapsed_delay_crosses_midnight_without_early_fire():
    tz = ZoneInfo("Europe/London")
    start = datetime(2026, 11, 3, 23, 50, 12, tzinfo=tz)
    result = RuleAuthoringService._relative_next_minute(start, 15)
    assert result.isoformat() == "2026-11-04T00:06:00+00:00"


def test_spring_dst_elapsed_delay_never_creates_missing_local_hour():
    tz = ZoneInfo("Europe/London")
    start = datetime(2027, 3, 28, 0, 50, 12, tzinfo=tz)
    result = RuleAuthoringService._relative_next_minute(start, 15)
    assert result.isoformat() == "2027-03-28T02:06:00+01:00"


def test_autumn_dst_elapsed_delay_preserves_absolute_elapsed_time():
    tz = ZoneInfo("Europe/London")
    start = datetime(2027, 10, 31, 1, 50, 12, tzinfo=tz, fold=0)
    result = RuleAuthoringService._relative_next_minute(start, 15)
    assert result.isoformat() == "2027-10-31T01:06:00+00:00"
    assert result.fold == 1
    # Ambiguous local time is *not* a native authoring guarantee; the
    # native writer is still closed until an offset-aware trigger is proven.
