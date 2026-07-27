from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_clusters import (  # noqa: E402
    INTENTIONAL_FAMILY_LAYERS,
    build_report,
)


def _rows_by_module(app_dir: Path, family: str) -> dict[str, dict[str, object]]:
    return {
        str(row["module"]): row
        for row in build_report(app_dir)[family]
    }


def test_live_ollama_chain_reports_documented_layers_not_suspects():
    rows = _rows_by_module(APP_DIR, "ollama_agent")

    assert INTENTIONAL_FAMILY_LAYERS == {
        "ollama_agent": {
            "ollama_agent_fast",
            "ollama_agent_inference",
        }
    }
    assert rows["ollama_agent_fast"]["signal"] == (
        "LIVE (intentional documented layer)"
    )
    assert rows["ollama_agent_inference"]["signal"] == (
        "LIVE (intentional documented layer)"
    )
    assert not any(
        str(row["signal"]).startswith("SUSPECT")
        for row in rows.values()
    )


def test_plain_sibling_composition_is_live(tmp_path: Path):
    (tmp_path / "control_agent_base.py").write_text(
        "def value():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "control_agent_wrapper.py").write_text(
        "from control_agent_base import value\n\nRESULT = value()\n",
        encoding="utf-8",
    )

    rows = _rows_by_module(tmp_path, "control_agent")

    assert rows["control_agent_base"]["signal"] == (
        "LIVE (composed by sibling)"
    )
    assert rows["control_agent_wrapper"]["signal"] == (
        "ORPHAN (imported by nothing)"
    )


def test_unlisted_sibling_subclass_layer_remains_suspect(tmp_path: Path):
    (tmp_path / "control_agent_base.py").write_text(
        "class Base:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "control_agent_wrapper.py").write_text(
        "from control_agent_base import Base\n\nclass Wrapper(Base):\n    pass\n",
        encoding="utf-8",
    )

    rows = _rows_by_module(tmp_path, "control_agent")

    assert rows["control_agent_base"]["signal"] == (
        "SUSPECT (only used by a same-family sibling)"
    )
    assert rows["control_agent_wrapper"]["signal"] == (
        "ORPHAN (imported by nothing)"
    )


def test_allowlisted_layer_without_an_importer_is_still_orphaned(
    tmp_path: Path,
):
    (tmp_path / "ollama_agent_fast.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    rows = _rows_by_module(tmp_path, "ollama_agent")

    assert rows["ollama_agent_fast"]["signal"] == (
        "ORPHAN (imported by nothing)"
    )


def test_live_semantic_evidence_composition_is_not_a_suspect():
    rows = _rows_by_module(APP_DIR, "semantic")

    assert rows["semantic_home_evidence"]["signal"] == (
        "LIVE (composed by sibling)"
    )
