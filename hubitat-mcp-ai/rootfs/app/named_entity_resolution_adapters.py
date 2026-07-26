from __future__ import annotations

from types import MethodType
from typing import Any

from assistant_contracts import ResolutionStatus
from named_entity_resolver import NamedEntityResolver, records_from_rows


def _payloads_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in rows if row.get("id") not in (None, "")}


def _resolved_rows(
    rows: list[dict[str, Any]],
    *,
    entity_type: str,
    variants: tuple[str, ...],
    exact_id: str | None,
    candidates_only: bool,
    limit: int,
) -> list[dict[str, Any]]:
    resolver = NamedEntityResolver()
    result = resolver.resolve(
        records_from_rows(rows, entity_type),
        variants,
        exact_id=exact_id,
        limit=limit,
    )
    payloads = _payloads_by_id(rows)
    selected = result.candidates if candidates_only else result.targets
    if candidates_only and result.status is ResolutionStatus.RESOLVED:
        selected = result.targets
    return [
        payloads[target.entity_id or target.device_id]
        for target in selected
        if (target.entity_id or target.device_id) in payloads
    ]


def install_named_entity_resolution_adapters(
    *,
    app_controller: Any,
    rule_controller: Any,
) -> NamedEntityResolver:
    """Make app and rule controllers share the same typed resolver."""

    resolver = NamedEntityResolver()

    def app_exact_matches(self: Any, apps: list[dict[str, Any]], intent: Any) -> list[dict[str, Any]]:
        requested_id = self._requested_id(intent)
        return _resolved_rows(
            apps,
            entity_type="app",
            variants=tuple(intent.variants),
            exact_id=requested_id,
            candidates_only=False,
            limit=8,
        )

    def app_possible_matches(self: Any, apps: list[dict[str, Any]], intent: Any) -> list[dict[str, Any]]:
        return _resolved_rows(
            apps,
            entity_type="app",
            variants=tuple(intent.variants),
            exact_id=None,
            candidates_only=True,
            limit=8,
        )

    def rule_exact_matches(self: Any, rules: list[dict[str, Any]], intent: Any) -> list[dict[str, Any]]:
        requested_id = self._requested_id(intent)
        return _resolved_rows(
            rules,
            entity_type="rule",
            variants=tuple(intent.variants),
            exact_id=requested_id,
            candidates_only=False,
            limit=5,
        )

    def rule_possible_matches(self: Any, rules: list[dict[str, Any]], intent: Any) -> list[dict[str, Any]]:
        return _resolved_rows(
            rules,
            entity_type="rule",
            variants=tuple(intent.variants),
            exact_id=None,
            candidates_only=True,
            limit=5,
        )

    app_controller._exact_matches = MethodType(app_exact_matches, app_controller)
    app_controller._possible_matches = MethodType(app_possible_matches, app_controller)
    rule_controller._exact_matches = MethodType(rule_exact_matches, rule_controller)
    rule_controller._possible_matches = MethodType(rule_possible_matches, rule_controller)
    app_controller.entity_resolver = resolver
    rule_controller.entity_resolver = resolver
    return resolver


__all__ = ["install_named_entity_resolution_adapters"]
