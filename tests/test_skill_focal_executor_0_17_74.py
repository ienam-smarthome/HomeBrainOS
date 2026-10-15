"""Read-only source completion: the host may use tools hidden from the model.

Replays the specific v0.17.73 error: hub_read_devices exists in the
available registry, but INITIAL_TOOL_ORDER excludes it. The focal state
gateway must execute, and events must survive as a source-typed receipt.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from skill_focal_window import build_focal_source_plan, execute_focal_source_plan, project_focal_state_result
from skill_grounded_answer import render_grounded_causal_answer
from test_skill_focal_window_0_17_73 import _recent_unbounded, QUESTION


class Registry:
    def __init__(self, *, missing=()):
        self.missing = set(missing)
        self.lookups = []

    def declared_tool(self, name):
        # The Hubitat read gateway is deliberately not model-declared.
        return None if name == "hub_read_devices" else name

    def available_tool(self, name):
        self.lookups.append(name)
        return None if name in self.missing else SimpleNamespace(name=name)


class FakeExecutor:
    def __init__(self, *, fail=()):
        self.calls = []
        self.fail = set(fail)

    async def execute(self, name, arguments, **kwargs):
        self.calls.append((name, arguments, kwargs))
        if name in self.fail:
            return SimpleNamespace(success=False, result=None, content='{"error":"offline"}')
        if name == "hub_read_devices":
            data = {"events": [
                {"name": "switch", "value": "off",
                 "date": "2026-10-14T19:54:57.946+0100",
                 "producedBy": {"label": "Matter Hue Bridge Pro"}},
                {"name": "switch", "value": "on",
                 "date": "2026-10-14T19:55:00.049+0100",
                 "producedBy": {"label": "Matter Hue Bridge Pro"}},
            ]}
        else:
            data = {"logs": [], "count": 0}
        return SimpleNamespace(success=True, result=SimpleNamespace(data=data), content="{}")


class Recorder:
    def __init__(self):
        self.rows = []

    def record(self, gateway, arguments, **options):
        from gateway_argument_view import gateway_operation
        self.rows.append({
            "tool": gateway,
            "sub_tool": gateway_operation(arguments),
            "arguments": arguments,
            **options,
        })


def _run(*, missing=(), fail=()):
    events = _recent_unbounded()
    plan = build_focal_source_plan(events, QUESTION)
    assert plan["stateRead"] is not None
    assert plan["producerLogRead"] is not None
    catalog = Registry(missing=missing)
    executor = FakeExecutor(fail=fail)
    recorder = Recorder()
    messages = []
    metrics = Counter()
    statuses = asyncio.run(execute_focal_source_plan(
        plan,
        catalog=catalog,
        executor=executor,
        recorder=recorder,
        messages=messages,
        count_metric=lambda key: metrics.update((key,)),
    ))
    return events, plan, catalog, executor, recorder, messages, metrics, statuses


def test_host_executes_hidden_but_available_device_gateway():
    original, plan, catalog, executor, recorder, messages, metrics, statuses = _run()
    assert catalog.declared_tool("hub_read_devices") is None
    assert catalog.lookups == ["hub_read_devices", "hub_read_diagnostics"]
    assert [name for name, *_ in executor.calls] == [
        "hub_read_devices", "hub_read_diagnostics",
    ]
    assert executor.calls[0][1]["args"] == plan["stateRead"]
    assert statuses["state"] == "rows-retained"
    assert statuses["producer_logs"] == "queried"
    assert metrics["skills_focal_state_window"] == 1
    assert metrics["skills_focal_state_rows_retained"] == 1
    assert metrics["skills_focal_producer_logs"] == 1
    receipt = [r for r in recorder.rows
               if r.get("evidence_kind") == "focal_exact_state_history"]
    assert len(receipt) == 1
    assert [e["value"] for e in receipt[0]["details"]["events"]] == ["off", "on"]
    # The renderer consumes the retained receipt, not the model's text.
    message = render_grounded_causal_answer(original + recorder.rows, QUESTION)
    assert "19:54:57.946" in message
    assert "timestamp-filtered" in message


def test_missing_gateway_is_a_failure_not_silent_completed_source():
    original, plan, catalog, executor, recorder, messages, metrics, statuses = _run(
        missing=("hub_read_devices",)
    )
    assert statuses["state"] == "gateway-unavailable"
    assert statuses["producer_logs"] == "queried"
    assert "hub_read_devices" not in [name for name, *_ in executor.calls]
    assert metrics["skills_focal_state_window"] == 0
    assert metrics["skills_focal_read_failed"] == 1
    assert any(r["evidence_kind"] == "focal_source_unavailable"
               and r["success"] is False for r in recorder.rows)


def test_failed_gateway_is_not_labeled_checked():
    _, _, _, _, recorder, _, metrics, statuses = _run(fail=("hub_read_devices",))
    assert statuses["state"] == "read-failed"
    assert metrics["skills_focal_state_rows_retained"] == 0
    assert metrics["skills_focal_read_failed"] == 1
    assert not any(r["evidence_kind"] == "focal_exact_state_history"
                   and r["success"] is True for r in recorder.rows)


def test_busy_focal_window_preserves_requested_transition_under_redaction_cap():
    from datetime import datetime, timedelta
    plan = build_focal_source_plan(_recent_unbounded(), QUESTION)
    target = datetime.fromisoformat("2026-10-14T19:55:00.049+01:00")
    many = [{
        "name": "switch",
        "value": "off" if i % 2 else "on",
        "date": (target + timedelta(milliseconds=20 * i)).isoformat(),
    } for i in range(35)]
    many.append({
        "name": "switch", "value": "off",
        "date": "2026-10-14T19:54:57.946+0100",
    })
    retained = project_focal_state_result({"events": many}, plan)
    assert retained["returnedRowsInWindow"] == 36
    assert retained["retainedRows"] == 20
    assert retained["eventsTruncated"] is True
    assert len(retained["events"]) == 20
    assert any(e["date"] == "2026-10-14T19:55:00.049+01:00"
               for e in retained["events"])
    assert any(e["date"] == "2026-10-14T19:54:57.946+0100"
               for e in retained["events"])
