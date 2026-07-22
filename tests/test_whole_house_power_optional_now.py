from __future__ import annotations
import sys
from pathlib import Path
APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period


# Regression coverage for the exact wording reported from the live Web UI.
def test_whole_house_power_without_now_is_terminal():
    query = "What is the whole house power consumption?"
    assert is_whole_house_power_query(query)
    assert is_octopus_energy_query(query)
    assert requested_octopus_period(query) == "power"


def test_whole_house_power_with_now_remains_terminal():
    assert is_whole_house_power_query("What is the whole house power consumption now?")


def test_hyphenated_whole_house_without_now_is_terminal():
    assert is_whole_house_power_query("What is the whole-house power consumption?")


def test_device_specific_power_is_not_captured():
    assert not is_whole_house_power_query("What is the freezer power consumption?")
