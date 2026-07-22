from __future__ import annotations
import sys
from pathlib import Path
APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period

def test_generic_live_power_routes_to_octopus_reader():
    query = "How much power are we using now?"
    assert is_whole_house_power_query(query)
    assert is_octopus_energy_query(query)
    assert requested_octopus_period(query) == "power"

def test_non_live_device_power_question_is_not_captured():
    assert not is_whole_house_power_query("How much power is the freezer using?")
