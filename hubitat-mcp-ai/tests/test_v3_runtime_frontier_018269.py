"""V3 regression: newly feasible read leaves must reach the next model round.

No MCP reads or Hubitat calls occur in these tests. Full dependency responses
are represented by tightly whitelisted IDs, not historical execution claims.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from tool_executor import ToolExecutor
from investigation_evidence_cycle import ranked_upstream_continuation_checkpoint
from test_v3_ranked_upstream_frontier_018268 import feed, facts, QUESTION
from test_v3_reception_evidence_018267 import replay
from test_v3_source_feasibility_018263 import receipt


def dependents_result(device="101", apps=None):
    return SimpleNamespace(
        name="hub_read_apps_code",
        arguments={"tool": "hub_list_device_dependents",
                   "args": {"deviceId": device}},
        data={"deviceId": device, "appsUsing": apps if apps is not None else [
            {"id": 4300, "name": "Do not retain this name"},
            {"appId": 4301, "settings": {"secret": "never-retain"}},
            {"appId": "4301"}, {"appId": "invalid"},
        ]},
    )


def test_scoped_dependents_retains_only_verified_app_ids_not_names_or_settings():
    result = ToolExecutor.result_details(dependents_result())
    assert result == {
        "deviceId": "101",
        "appsUsing": [{"appId": "4300"}, {"appId": "4301"}],
        "appIdsCoverage": "bounded",
    }
    assert "secret" not in str(result)
    assert "Do not retain" not in str(result)
    assert ToolExecutor.result_details(SimpleNamespace(
        name="hub_read_apps_code",
        arguments={"tool": "hub_list_device_dependents",
                   "args": {"deviceId": "101"}},
        data={"deviceId": "other", "appsUsing": [{"appId": 4300}]},
    )) is None
    assert ToolExecutor.result_details(SimpleNamespace(
        name="hub_read_apps_code",
        arguments={"tool": "hub_list_device_dependents",
                   "args": {"deviceId": "101"}},
        data={"deviceId": "101", "appsUsing": {"appId": "4300"}},
    )) is None


def test_continuation_not_offered_before_read_leaf_is_known():
    rows = replay()
    assert ranked_upstream_continuation_checkpoint(rows, QUESTION) is None
    rows.append(receipt("hub_list_device_dependents", device=101))
    result = ranked_upstream_continuation_checkpoint(rows, QUESTION)
    assert result is not None
    key, content = result
    assert "hub_list_device_dependents" in key
    assert '"deviceId":"201"' in content
    assert "strongestSourceQualifiedRead" in content
    assert "CURRENT authorized READ catalog" in content
    assert "model" in content.lower()
    assert "same" not in key or "hub_list_device_dependents" in key


def test_verified_sensor_dependents_then_shared_app_uses_new_round_hint():
    rows = feed()
    first = ranked_upstream_continuation_checkpoint(rows, QUESTION)
    assert first and '"deviceId":"201"' in first[1]
    rows[-2]["details"] = ToolExecutor.result_details(
        dependents_result("101", [{"id": 4300}, {"appId": 4310}]))
    rows.append(receipt("hub_list_device_dependents", device=201))
    rows[-1]["details"] = ToolExecutor.result_details(
        dependents_result("201", [{"id": 4300}, {"appId": 5200}]))
    next_step = ranked_upstream_continuation_checkpoint(rows, QUESTION)
    assert next_step is not None
    assert next_step[0] != first[0]
    assert '"appId":"4300"' in next_step[1]
    assert '"leaf":"hub_get_app_config"' in next_step[1]
    assert "historical app execution" in next_step[1]
    rows.append(receipt("hub_get_app_config", app=4300))
    assert ranked_upstream_continuation_checkpoint(rows, QUESTION) is None


def test_failed_sensor_dependents_does_not_repeat_exact_attempt():
    rows = feed()
    rows.append(receipt("hub_list_device_dependents", device=201, success=False))
    assert ranked_upstream_continuation_checkpoint(rows, QUESTION) is None


def test_unverified_or_truncated_sensor_never_generates_host_offer():
    rows = feed()
    rows[10]["details"]["truncated"] = True
    assert ranked_upstream_continuation_checkpoint(rows, QUESTION) is None
    rows = feed()
    rows[10]["details"]["observations"] = []
    assert ranked_upstream_continuation_checkpoint(rows, QUESTION) is None
