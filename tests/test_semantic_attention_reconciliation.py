from __future__ import annotations

import json

from semantic_attention_reconciliation import reconcile_semantic_attention


def test_quiet_timestamp_rows_are_not_promoted_to_offline():
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
                "count": 3,
                "items": [
                    {"device": "Iron", "value": "Offline"},
                    {"device": "Roborock", "value": "Offline"},
                    {"device": "Quiet Helper", "value": "Offline", "detail": "Last event yesterday"},
                ],
            },
            "stale": {"count": 0, "items": []},
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
                    "display": {
                        "items": [
                            {"title": "Iron", "value": "Offline", "subtitle": "Live healthStatus: offline"},
                            {"title": "Roborock", "value": "Offline", "subtitle": "Live healthStatus: offline"},
                            {"title": "Quiet Helper", "value": "Quiet timestamp", "subtitle": "Old lastActivity is not proof of a fault"},
                        ]
                    }
                }
            }
        ),
    }

    result = reconcile_semantic_attention(answer)

    assert result["health_reconciled"] is True
    assert result["semantic_attention"]["offline"]["count"] == 2
    assert [
        item["device"] for item in result["semantic_attention"]["offline"]["items"]
    ] == ["Iron", "Roborock"]
    assert result["semantic_attention"]["quiet_health_rows_suppressed"] == 1
    assert "2 devices are confirmed offline" in result["message"]
    assert "Quiet Helper" not in result["message"]
    assert "Microwave Door" in result["message"]
    assert "Livingroom TRV at 10%" in result["message"]


def test_non_attention_answers_are_unchanged():
    answer = {"route": "mcp-fast", "message": "OK"}
    assert reconcile_semantic_attention(answer) == answer
