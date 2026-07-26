import sys
from pathlib import Path

APP = Path(
    "hubitat-mcp-ai/rootfs/app"
)

sys.path.insert(
    0,
    str(APP)
)

from environmental_insight_engine import (
    build_environmental_insights
)


evidence = {
    "temperatures": [
        {
            "device": "Livingroom FP300",
            "room": "Livingroom",
            "value": 29.0,
        }
    ],
    "humidities": [
        {
            "device": "Bathroom Meter",
            "room": "Bathroom",
            "value": 47,
        }
    ],
}


result = build_environmental_insights(
    evidence
)

print(result)
