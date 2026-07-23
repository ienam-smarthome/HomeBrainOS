from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from system_presenter_v2 import present_hub_info_v2


def _metric(display, label):
    return next(item for item in display["metrics"] if item["label"] == label)


def test_hub_health_shows_available_firmware_and_database_size_tiles():
    message, display = present_hub_info_v2(
        {
            "name": "Hub C8 Pro",
            "firmwareVersion": "2.5.1.132",
            "databaseSizeKB": "208896",
            "platformUpdate": {
                "available": True,
                "currentVersion": "2.5.1.132",
                "availableVersion": "2.5.1.134",
            },
        }
    )

    assert _metric(display, "Installed firmware")["value"] == "2.5.1.132"
    assert _metric(display, "Software update")["value"] == "Available 2.5.1.134"
    assert _metric(display, "Database size")["value"] == "204.0 MB"
    assert "Hub platform update available: 2.5.1.134." in message
    assert display["database_size"] == "204.0 MB"


def test_hub_health_marks_current_firmware_up_to_date():
    _, display = present_hub_info_v2(
        {
            "firmwareVersion": "2.5.1.134",
            "platformUpdate": {
                "available": False,
                "currentVersion": "2.5.1.134",
                "availableVersion": "2.5.1.134",
            },
        }
    )

    assert _metric(display, "Software update")["value"] == "Up to date"
