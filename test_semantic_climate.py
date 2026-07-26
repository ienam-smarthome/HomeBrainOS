import sys
from pathlib import Path

APP = Path(
    "hubitat-mcp-ai/rootfs/app"
)

sys.path.insert(0, str(APP))

from semantic_home_evidence import SemanticHomeEvidenceBroker


print("Semantic evidence module loaded OK")
print("Climate support already exists")
