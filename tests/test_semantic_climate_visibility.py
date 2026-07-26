from pathlib import Path
import sys

APP = Path(
    "hubitat-mcp-ai/rootfs/app"
)

sys.path.insert(0,str(APP))

from semantic_home_summary_agent import _public_evidence


def test_public_evidence_contains_climate():

    result = _public_evidence(
        {
            "data":{
                "climate":{
                    "warmest":[
                        {
                            "device":"Livingroom FP300",
                            "value":29
                        }
                    ]
                }
            }
        }
    )

    assert result["climate"]["warmest"][0]["value"] == 29
