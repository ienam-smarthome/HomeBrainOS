"""Offline, fail-closed shape preflight for a future native Rule Machine compiler.

This module never calls MCP, creates rules or authorises execution. The new
hub_set_rule document contract is not compatible with the legacy shortcut
compiler. A syntactically well-formed native batch is NOT evidence that its
capability-specific fields, timing or device effects are correct.

The source for these *structural* rules is the upstream
mcp-native-documents-lib.groovy _ndValidateChange/_ndOperationSchema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rule_writer_contract import NATIVE_DOCUMENT, installed_rule_writer_contract


@dataclass(frozen=True)
class NativeCreatePreflight:
    contract: str
    schema_verified: bool
    parent_verified: bool
    batch_shape_verified: bool
    gaps: tuple[str, ...]

    @property
    def write_ready(self) -> bool:
        """No runtime writer is enabled by this structural preflight."""
        return False


def _positive_id(value: Any) -> bool:
    return type(value) is int and value > 0


def _typed_fields(fields: Any, *, selectors: set[str]) -> bool:
    if not isinstance(fields, list):
        return False
    names: set[str] = set()
    for row in fields:
        if not isinstance(row, dict) or set(row) != {"name", "type", "value"}:
            return False
        name, kind = row["name"], row["type"]
        if not isinstance(name, str) or name.count("#") != 1:
            return False
        if not isinstance(kind, str) or not kind.strip():
            return False
        native_name = name.replace("#", "1")
        if native_name in selectors or native_name in names:
            return False
        names.add(native_name)
    return True


def native_schedule_batch_shape_valid(changes: Any) -> bool:
    """Check native shape only, never capability-specific field semantics.

    Scheduling needs a trigger and an action in *one* atomic batch. This
    deliberately rejects arbitrary native operations (variables, expressions,
    deletions and form mutations), whose execution has different safeguards.
    """
    if not isinstance(changes, list) or len(changes) != 2:
        return False
    if [item.get("part") if isinstance(item, dict) else None for item in changes] != ["trigger", "action"]:
        return False
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"part", "value"}:
            return False
        value = item["value"]
        if not isinstance(value, dict):
            return False
        if item["part"] == "trigger":
            if set(value) != {"capability", "fields"}:
                return False
            if not isinstance(value["capability"], str) or not value["capability"].strip():
                return False
            if not _typed_fields(value["fields"], selectors={"tCapab1", "rCapab_1"}):
                return False
        else:
            if set(value) != {"type", "subtype", "fields"}:
                return False
            if not all(isinstance(value[k], str) and value[k].strip() for k in ("type", "subtype")):
                return False
            if not _typed_fields(value["fields"], selectors={"actType.1", "actSubType.1"}):
                return False
    return True


def _property(properties: Any, name: str) -> dict[str, Any]:
    if not isinstance(properties, dict):
        return {}
    value = properties.get(name)
    return value if isinstance(value, dict) else {}


def _required(schema: dict[str, Any], names: set[str]) -> bool:
    required = schema.get("required")
    return isinstance(required, list) and all(isinstance(item, str) for item in required) and names.issubset(set(required))


def _native_create_schema(schema_reply: Any) -> bool:
    """Require the *actual unconfirmed* native operation schema, not a guide.

    The caller must supply the decoded, trusted response to
    hub_set_rule(operation="create", confirm=false); no such call occurs here.
    """
    if not isinstance(schema_reply, dict):
        return False
    if schema_reply.get("operation") != "create" or schema_reply.get("confirm_required") is not True:
        return False
    root = schema_reply.get("inputSchema")
    if not isinstance(root, dict) or root.get("type") != "object" or root.get("additionalProperties") is not False:
        return False
    properties = root.get("properties")
    if not isinstance(properties, dict) or not _required(root, {"operation", "args", "confirm"}):
        return False
    if _property(properties, "operation").get("enum") != ["create"]:
        return False
    if _property(properties, "confirm").get("type") != "boolean":
        return False
    args = _property(properties, "args")
    if not isinstance(args, dict) or args.get("type") != "object" or args.get("additionalProperties") is not False:
        return False
    props = args.get("properties")
    if not isinstance(props, dict) or not _required(args, {"parent_id", "name", "changes"}):
        return False
    return (
        _property(props, "parent_id").get("type") == "integer"
        and _property(props, "name").get("type") == "string"
        and _property(props, "changes").get("type") == "array"
    )


def _native_parent(parent: Any) -> bool:
    """Do not accept a guessed ID or a Rule-5.1 child in place of the parent."""
    if not isinstance(parent, dict) or not _positive_id(parent.get("id")):
        return False
    app_type = parent.get("appType")
    return (
        isinstance(app_type, dict)
        and app_type.get("namespace") == "hubitat"
        and app_type.get("name") == "Rule Machine"
    )


def assess_native_schedule_preflight(
    *, guide: Any, schema_reply: Any = None, parent: Any = None,
    changes: Any = None,
) -> NativeCreatePreflight:
    """Report what a future native authoring implementation still lacks.

    A trusted guide, matching schema, parent record and structural fields
    are necessary but *not sufficient*. Native field names and values must
    be independently matched to the requested device/command and one-time
    trigger semantics; confirmation, fresh duplicate checks, backup,
    idempotency, and post-create readback must then be implemented.
    """
    contract = installed_rule_writer_contract(guide)
    schema_ok = _native_create_schema(schema_reply)
    parent_ok = _native_parent(parent)
    shape_ok = native_schedule_batch_shape_valid(changes)
    gaps: list[str] = []
    if contract != NATIVE_DOCUMENT:
        gaps.append("installed_native_contract_unverified")
    if not schema_ok:
        gaps.append("native_create_schema_unverified")
    if not parent_ok:
        gaps.append("native_rule_machine_parent_unverified")
    if not shape_ok:
        gaps.append("atomic_trigger_action_shape_unverified")
    # Structural validation cannot substitute for real native editor inputs.
    gaps.extend((
        "capability_specific_native_fields_unattested",
        "schedule_and_one_time_semantics_unattested",
        "approved_write_and_post_create_verification_not_implemented",
    ))
    return NativeCreatePreflight(contract, schema_ok, parent_ok, shape_ok, tuple(gaps))


__all__ = [
    "NativeCreatePreflight", "assess_native_schedule_preflight",
    "native_schedule_batch_shape_valid",
]
