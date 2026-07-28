from __future__ import annotations

import json

from semantic_attention_reconciliation import reconcile_semantic_attention


def test_quiet_rows_are_not_promoted_to_offline_and_stale_counts_match_kind():
    answer = {
        "route": "ai-semantic-home-attention",
        "message": "Incorrect old message",
        "semantic_attention": {
            "low_batteries": {
                "count": 2,
                "items": [
                    {"device": "Livingroom TRV", "value": 10.0},
                    {"device": "Fridge Door", "value": 14.0},
                ],
            },
            "offline": {
                "count": 4,
                "items": [
                    {"id": "1", "device": "Iron", "value": "Offline"},
                    {"id": "2", "device": "Roborock", "value": "Offline"},
                    {"id": "3", "device": "Quiet Helper", "value": "Quiet, not offline"},
                    {"id": "4", "device": "Periodic Sensor", "value": "Offline"},
                ],
            },
            "stale": {
                "count": 1,
                "items": [
                    {"id": "4", "device": "Periodic Sensor", "value": "Telemetry stale 48h+"},
                ],
            },
            "warnings": {"count": 0, "items": []},
            "updates": {"count": 0, "items": []},
            "open_contacts": {
                "open_count": 1,
                "open": [{"title": "Microwave Door", "value": "Open"}],
            },
        },
        "technical": json.dumps(
            {
                "health_evidence": {
                    "health_items": [
                        {"id": "1", "title": "Iron", "kind": "offline", "reason": "Live healthStatus is offline."},
                        {"id": "2", "title": "Roborock", "kind": "offline", "reason": "Live healthStatus is offline."},
                        {"id": "3", "title": "Quiet Helper", "kind": "quiet", "reason": "Event age is not connectivity."},
                        {"id": "4", "title": "Periodic Sensor", "kind": "stale", "reason": "Periodic telemetry stopped."},
                    ]
                }
            }
        ),
    }

    result = reconcile_semantic_attention(answer)
    attention = result["semantic_attention"]

    assert result["health_reconciled"] is True
    assert attention["offline"]["count"] == 2
    assert [item["id"] for item in attention["offline"]["items"]] == ["1", "2"]
    assert attention["stale"]["count"] == 1
    assert attention["stale"]["items"][0]["id"] == "4"
    assert attention["quiet_health_rows_suppressed"] == 1
    assert "2 devices are confirmed offline" in result["message"]
    assert "Quiet Helper" not in result["message"]
    assert "Periodic Sensor" in result["message"]
    assert "Microwave Door" in result["message"]
    assert "Livingroom TRV at 10%" in result["message"]

    technical = json.loads(result["technical"])
    assert technical["health_reconciliation"]["authoritative_kind_counts"] == {
        "offline": 2,
        "stale": 1,
        "quiet": 1,
    }


def test_non_attention_answers_are_unchanged():
    answer = {"route": "mcp-fast", "message": "OK"}
    assert reconcile_semantic_attention(answer) == answer


def test_top_level_health_evidence_survives_truncated_debug_payload():
    answer = {
        "route": "ai-semantic-home-attention",
        "message": "Incomplete answer",
        "semantic_attention": {
            "low_batteries": {"count": 0, "items": []},
            "offline": {"count": 0, "items": []},
            "stale": {"count": 0, "items": []},
            "warnings": {"count": 0, "items": []},
            "updates": {"count": 0, "items": []},
            "open_contacts": {"open_count": 0, "open": []},
        },
        "_health_evidence": {
            "health_items": [
                {
                    "id": "1",
                    "title": "Iron",
                    "kind": "offline",
                    "reason": "Live healthStatus is offline.",
                }
            ]
        },
        "technical": '{"health_evidence": {"health_items": [',
    }

    result = reconcile_semantic_attention(answer)

    assert result["health_reconciled"] is True
    assert result["semantic_attention"]["offline"]["count"] == 1
    assert "Iron" in result["message"]
