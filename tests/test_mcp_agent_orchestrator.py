from __future__ import annotations

import importlib.util
from pathlib import Path


_SUITE_PATH = Path(__file__).with_name("_entity_first_orchestrator_cases.py")
_SPEC = importlib.util.spec_from_file_location("_entity_first_orchestrator_cases", _SUITE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_suite = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_suite)

_REPLACED = {
    "test_rule_authoring_uses_deterministic_compiler_before_model",
    "test_history_uses_local_fuzzy_resolver_instead_of_raw_gateway",
}
for _name, _value in vars(_suite).items():
    if _name.startswith("test_") and _name not in _REPLACED:
        globals()[_name] = _value
