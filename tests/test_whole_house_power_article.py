from __future__ import annotations
import sys
from pathlib import Path
APP = Path('hubitat-mcp-ai/rootfs/app').resolve()
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period

def test_the_hyphenated_whole_house_power_query_is_terminal():
    query = 'What is the whole-house power consumption?'
    assert is_whole_house_power_query(query)
    assert is_octopus_energy_query(query)
    assert requested_octopus_period(query) == 'power'

def test_the_spaced_whole_house_power_query_is_terminal():
    assert is_whole_house_power_query('What is the whole house power consumption?')
