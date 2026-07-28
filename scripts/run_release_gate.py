from __future__ import annotations

import subprocess
import sys


# The native MCP refactor deliberately removes the legacy router/resolver stack.
# Keep its historical tests visible in the workflows' non-blocking audit jobs, but
# make release eligibility depend on the maintained runtime and transport contracts.
RELEASE_GATE_TESTS = [
    "tests/test_hubitat_mcp_ai_unified_agent.py",
    "tests/test_mcp_structured_content_priority.py",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *RELEASE_GATE_TESTS]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
