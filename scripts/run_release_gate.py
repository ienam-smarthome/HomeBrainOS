from __future__ import annotations

import subprocess
import sys


# The repository test tree now contains only maintained runtime and platform tests.
RELEASE_GATE_TESTS = ["tests"]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *RELEASE_GATE_TESTS]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
