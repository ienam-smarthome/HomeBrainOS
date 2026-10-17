from __future__ import annotations

import subprocess
import sys


# Test both maintained trees: core/runtime regressions and add-on-specific
# Groovy workbench/transport tests. A green gate must not silently omit the
# second tree merely because its path differs from the root test directory.
RELEASE_GATE_TESTS = ["tests", "hubitat-mcp-ai/tests"]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *RELEASE_GATE_TESTS]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
