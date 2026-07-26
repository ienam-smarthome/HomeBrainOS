from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from assistant_contracts import EntityResolutionResult, ResolvedTarget, ResolutionStatus


_STOP_WORDS: dict[str, set[str]] = {
    "app": {"a", "an", "and", "app", "application", "the"},
    "rule": {"a", "an", "and", "automation", "rule", "the"},
    "room": {"a", "an", "and", "room", "the"},
}


def normalise_named_entity(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: Any, entity_type: str) -> frozenset[str]:
    ignored = _STOP_WORDS.get(entity_type, {"a", "an", "and", "the"})
    return frozenset(
        token
        for token in normalise_named_entity(value).split()
        if len(token) > 1 and token not in ignored
    )


@dataclass(frozen=True, slots=True)
class NamedEntity:
    entity_type: str
    entity_id: str
    label: str
    normalised: str
    payload: dict[str, Any]


class NamedEntityResolver:
    """One deterministic name-resolution service for non-device Hubitat entities."""

    def resolve(
        self,
        entities: Sequence[NamedEntity],
        variants: Iterable[str],
        *,
        exact_id: str | None = None,
        limit: int = 5,
        minimum_score: float = 0.65,
    ) -> EntityResolutionResult:
        requested = tuple(
            dict.fromkeys(
                normalise_named_entity(variant)
                for variant in variants
                if normalise_named_entity(variant)
            )
        )
        entity_type = entities[0].entity_type if entities else "entity"

        if exact_id is not None:
            matches = [entity for entity in entities if entity.entity_id == str(exact_id)]
            if len(matches) == 1:
                return self._result(
                    ResolutionStatus.RESOLVED,
                    "exact-id",
                    "Matched the authoritative entity ID.",
                    targets=matches,
                    confidence=1.0,
                )
            return self._result(
                ResolutionStatus.NOT_FOUND,
                "id-not-found",
                "No entity has the requested ID.",
            )

        exact = [entity for entity in entities if entity.normalised in requested]
        if len(exact) == 1:
            return self._result(
                ResolutionStatus.RESOLVED,
                "exact-name",
                "Matched one normalised entity name.",
                targets=exact,
                confidence=1.0,
            )
        if len(exact) > 1:
            return self._result(
                ResolutionStatus.AMBIGUOUS,
                "duplicate-exact-name",
                "Multiple entities share the exact normalised name.",
                candidates=exact[:limit],
                confidence=1.0,
            )

        ranked: list[tuple[float, int, int, str, NamedEntity]] = []
        requested_token_sets = [_tokens(variant, entity_type) for variant in requested]
        requested_token_sets = [terms for terms in requested_token_sets if terms]
        for entity in entities:
            terms = _tokens(entity.normalised or entity.label, entity.entity_type)
            if not terms:
                continue
            best_score = 0.0
            best_overlap = 0
            best_requested_count = 0
            for requested_terms in requested_token_sets:
                # One-word fuzzy matches are intentionally blocked. They are too
                # broad for safe app and Rule Machine selection.
                if len(requested_terms) < 2:
                    continue
                overlap = len(requested_terms & terms)
                if overlap < 2:
                    continue
                coverage = overlap / len(requested_terms)
                precision = overlap / len(terms)
                score = coverage * 0.8 + precision * 0.2
                if requested_terms <= terms:
                    score += 0.25
                if score > best_score:
                    best_score = score
                    best_overlap = overlap
                    best_requested_count = len(requested_terms)
            if best_score >= minimum_score:
                ranked.append(
                    (
                        -best_score,
                        -best_overlap,
                        best_requested_count,
                        entity.label.lower(),
                        entity,
                    )
                )

        ranked.sort(key=lambda item: item[:4])
        candidates = [item[4] for item in ranked[: max(1, limit)]]
        if candidates:
            confidence = max(0.0, min(1.0, -ranked[0][0]))
            return self._result(
                ResolutionStatus.AMBIGUOUS,
                "ranked-candidates",
                "Safe candidate matches were found, but confirmation is required.",
                candidates=candidates,
                confidence=confidence,
            )
        return self._result(
            ResolutionStatus.NOT_FOUND,
            "no-safe-candidate",
            "No exact or sufficiently specific candidate match was found.",
        )

    @staticmethod
    def _target(entity: NamedEntity, *, confidence: float, reason: str) -> ResolvedTarget:
        return ResolvedTarget(
            device_id=entity.entity_id,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            label=entity.label,
            types=[entity.entity_type],
            confidence=confidence,
            match_reason=reason,
        )

    def _result(
        self,
        status: ResolutionStatus,
        method: str,
        reason: str,
        *,
        targets: Sequence[NamedEntity] = (),
        candidates: Sequence[NamedEntity] = (),
        confidence: float = 0.0,
    ) -> EntityResolutionResult:
        return EntityResolutionResult(
            status=status,
            confidence=confidence,
            method=method,
            reason=reason,
            targets=[self._target(item, confidence=confidence, reason=reason) for item in targets],
            candidates=[self._target(item, confidence=confidence, reason=reason) for item in candidates],
            trace=[
                f"method={method}",
                f"confidence={confidence:.3f}",
                f"resolved={len(targets)}",
                f"candidates={len(candidates)}",
            ],
        )


def records_from_rows(rows: Sequence[dict[str, Any]], entity_type: str) -> list[NamedEntity]:
    records: list[NamedEntity] = []
    for row in rows:
        entity_id = row.get("id")
        label = str(row.get("name") or row.get("label") or "").strip()
        if entity_id in (None, "") or not label:
            continue
        records.append(
            NamedEntity(
                entity_type=entity_type,
                entity_id=str(entity_id),
                label=label,
                normalised=normalise_named_entity(row.get("normalised") or label),
                payload=dict(row),
            )
        )
    return records


__all__ = [
    "NamedEntity",
    "NamedEntityResolver",
    "normalise_named_entity",
    "records_from_rows",
]
