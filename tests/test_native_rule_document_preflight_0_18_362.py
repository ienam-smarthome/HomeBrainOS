"""Native Rule Machine migration preflight; synthetic, no MCP calls or writes."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from native_rule_document_preflight import (
    assess_native_schedule_preflight, native_schedule_batch_shape_valid,
)

NATIVE_GUIDE = {
    "content": (
        '## Set Rule Reference\n'
        'hub_set_rule(operation:"create",args:{parent_id,name,changes:[...]},confirm:true) '
        'creates a Rule-5.1 child under native Rule Machine. '
        'Native typed fields must be read; no shortcut field translation.'
    )
}

SCHEMA = {
    "operation": "create", "confirm_required": True,
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "required": ["operation", "args", "confirm"],
        "properties": {
            "operation": {"type": "string", "enum": ["create"]},
            "confirm": {"type": "boolean"},
            "args": {
                "type": "object", "additionalProperties": False,
                "required": ["parent_id", "name", "changes"],
                "properties": {
                    "parent_id": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1},
                    "changes": {"type": "array", "minItems": 0},
                },
            },
        },
    },
}
PARENT = {"id": 21, "appType": {"namespace": "hubitat", "name": "Rule Machine"}}
# These are intentionally SYNTHETIC field names, not a claim that the real
# native editor accepts this timer or device-control contract.
SHAPE = [
    {"part": "trigger", "value": {
        "capability": "syntheticTimer", "fields": [
            {"name": "syntheticTime.#", "type": "time", "value": "07:00"}
        ],
    }},
    {"part": "action", "value": {
        "type": "syntheticActionType", "subtype": "syntheticCommand",
        "fields": [{"name": "syntheticDevice.#", "type": "capability", "value": "123"}],
    }},
]


def _assess(**overrides):
    values = dict(guide=NATIVE_GUIDE, schema_reply=SCHEMA, parent=PARENT, changes=SHAPE)
    values.update(overrides)
    return assess_native_schedule_preflight(**values)


def test_all_structural_inputs_still_do_not_enable_writer():
    result = _assess()
    assert result.contract == "native-document"
    assert result.schema_verified and result.parent_verified and result.batch_shape_verified
    assert not result.write_ready
    assert result.gaps == (
        "capability_specific_native_fields_unattested",
        "schedule_and_one_time_semantics_unattested",
        "approved_write_and_post_create_verification_not_implemented",
    )


def test_guide_alone_is_not_schema_or_parent_or_semantic_authorisation():
    result = assess_native_schedule_preflight(guide=NATIVE_GUIDE)
    assert not result.write_ready
    assert not result.schema_verified
    assert not result.parent_verified
    assert not result.batch_shape_verified
    assert "native_create_schema_unverified" in result.gaps


@pytest.mark.parametrize("schema", [
    {}, {"operation": "create"}, {"operation": "create", "confirm_required": False},
    {"operation": "create", "confirm_required": True, "inputSchema": {"type": "object"}},
    {**SCHEMA, "inputSchema": {**SCHEMA["inputSchema"], "additionalProperties": True}},
    {**SCHEMA, "inputSchema": {**SCHEMA["inputSchema"], "properties": {"args": None}}},
    {**SCHEMA, "inputSchema": {**SCHEMA["inputSchema"], "properties": {"operation": None}}},
])
def test_missing_or_broken_read_only_schema_fails_closed(schema):
    assert not _assess(schema_reply=schema).schema_verified


@pytest.mark.parametrize("parent", [
    None, {"id": "21", "appType": {"namespace": "hubitat", "name": "Rule Machine"}},
    {"id": True, "appType": {"namespace": "hubitat", "name": "Rule Machine"}},
    {"id": 0, "appType": {"namespace": "hubitat", "name": "Rule Machine"}},
    {"id": 21, "appType": {"namespace": "hubitat", "name": "Rule-5.1"}},
    {"id": 21, "appType": {"namespace": "custom", "name": "Rule Machine"}},
])
def test_parent_must_be_native_rule_machine(parent):
    assert not _assess(parent=parent).parent_verified


@pytest.mark.parametrize("bad", [
    [],
    [SHAPE[0]],
    [SHAPE[1], SHAPE[0]],
    [SHAPE[0], SHAPE[1], SHAPE[1]],
    [{"part": "trigger", "value": {"capability": "timer", "fields": "wrong"}}, SHAPE[1]],
    [{"part": "trigger", "value": {"capability": "timer", "fields": [],
                                  "unrecognised": 1}}, SHAPE[1]],
    [{"part": "trigger", "value": {"capability": "timer",
                                  "fields": [{"name": "day", "type": "time", "value": "07:00"}]}}, SHAPE[1]],
    [{"part": "trigger", "value": {"capability": "timer",
                                  "fields": [{"name": "tCapab#", "type": "enum", "value": "timer"}]}}, SHAPE[1]],
    [{"part": "trigger", "value": {"capability": "timer", "fields": [
        {"name": "time.#", "type": "time", "value": "07:00"},
        {"name": "time.#", "type": "time", "value": "08:00"}]}}, SHAPE[1]],
    [SHAPE[0], {"part": "action", "value": {"type": "command",
                                           "subtype": "on", "fields": [],
                                           "unknownProperty": True}}],
])
def test_invalid_or_non_atomic_native_batch_does_not_pass_shape_check(bad):
    assert not native_schedule_batch_shape_valid(bad)
    assert not _assess(changes=bad).batch_shape_verified


def test_no_native_contract_from_legacy_shortcut_guide():
    legacy = {"content": "set_rule_reference hub_set_rule name addTrigger and addAction old shortcut API"}
    result = _assess(guide=legacy)
    assert result.contract == "legacy-shortcut"
    assert "installed_native_contract_unverified" in result.gaps
    assert not result.write_ready


def test_inputs_are_not_modified():
    inputs = [copy.deepcopy(value) for value in (NATIVE_GUIDE, SCHEMA, PARENT, SHAPE)]
    _assess()
    assert inputs == [NATIVE_GUIDE, SCHEMA, PARENT, SHAPE]
