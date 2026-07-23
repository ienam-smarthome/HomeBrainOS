from __future__ import annotations

import subprocess
import sys


RELEASE_GATE_TESTS = [
    "tests/test_addon_security.py",
    "tests/test_device_model.py",
    "tests/test_entity_request_policy.py",
    "tests/test_entity_resolution.py",
    "tests/test_hubitat_maker.py",
    "tests/test_normalizer.py",
    "tests/test_hubitat_mcp_ai_control_focus.py",
    "tests/test_hubitat_mcp_ai_docs.py",
    "tests/test_hubitat_mcp_ai_release_metadata.py",
    "tests/test_hubitat_mcp_ai_room_inventory_and_cpu_percent.py",
    "tests/test_hubitat_mcp_ai_state_broker.py",
    "tests/test_room_inventory_parser.py",
    "tests/test_repository_hygiene.py",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *RELEASE_GATE_TESTS]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
