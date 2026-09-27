from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from log_evidence_compactor import compact_log_evidence  # noqa: E402


def test_threshold_sample_survives_outside_twenty_row_receipt_excerpt() -> None:
    logs = [
        {"message": f"device|{index}|Noise|unrelated row {index}"}
        for index in range(25)
    ]
    logs.extend(
        [
            {
                "message": (
                    "app|2817|Power saving: TV OFF (medium setting)|"
                    "Triggered: Power level of TV(87) reported >= 65.0"
                )
            },
            {
                "message": (
                    "app|2817|Power saving: TV OFF (medium setting)|"
                    "Action: Wait for event: Power level of TV(87) is <= 50.0 "
                    "and stays that way for: 0:03:00"
                )
            },
            {
                "message": (
                    "app|2817|Power saving: TV OFF (medium setting)|"
                    "Event: TV power 87"
                )
            },
            {
                "message": (
                    "app|2817|Power saving: TV OFF (medium setting)|"
                    "Event: TV power 84"
                )
            },
            {
                "message": (
                    "app|2817|Power saving: TV OFF (medium setting)|"
                    "Event: TV power 80"
                )
            },
        ]
    )

    details = compact_log_evidence({"count": len(logs), "logs": logs})

    assert len(details["logs"]) == 20
    assert all("Power saving: TV OFF" not in row["message"] for row in details["logs"])
    assert details["thresholdSamples"] == [
        {
            "source": "Power saving: TV OFF (medium setting)",
            "operator": ">=",
            "threshold": 65.0,
            "values": [87.0, 84.0, 80.0],
            "allQualifying": True,
            "observedValueCount": 3,
        }
    ]


def test_action_timer_is_not_misread_as_event_value() -> None:
    logs = [
        {
            "message": (
                "app|2817|TV Rule|"
                "Triggered: Power level of TV(70) reported >= 65.0"
            )
        },
        {
            "message": (
                "app|2817|TV Rule|"
                "Action: Wait for event: Power level <= 50.0 and stays that way for: 0:03:00"
            )
        },
        {"message": "app|2817|TV Rule|Event: TV power 70"},
        {"message": "app|2817|TV Rule|Event: TV power 72"},
    ]

    details = compact_log_evidence({"logs": logs})

    assert details["thresholdSamples"][0]["values"] == [70.0, 72.0]
    assert details["thresholdSamples"][0]["allQualifying"] is True


def test_full_sample_crossing_prevents_one_sided_flag() -> None:
    logs = [
        {
            "message": (
                "app|2817|TV Rule|"
                "Triggered: Power level of TV(70) reported >= 65.0"
            )
        },
        {"message": "app|2817|TV Rule|Event: TV power 70"},
        {"message": "app|2817|TV Rule|Event: TV power 61"},
    ]

    details = compact_log_evidence({"logs": logs})

    assert details["thresholdSamples"][0]["allQualifying"] is False
