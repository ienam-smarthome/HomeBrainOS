from __future__ import annotations

import subprocess
import sys


# The release gate intentionally runs the complete test suite. Historical failures
# remain visible as non-strict xfails through tests/conftest.py; every other failure
# blocks release. Keeping a hand-maintained subset here previously allowed roadmap
# registry/composition regressions to pass CI unnoticed.
RELEASE_GATE_TESTS = ["tests"]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *RELEASE_GATE_TESTS]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
