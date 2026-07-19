from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_0438_release_note_records_stable_stage_and_reload_command():
    note = (ROOT / "docs" / "releases" / "0.4.38.md").read_text(encoding="utf-8")

    assert "experimental` to `stable" in note
    assert "ha supervisor reload" in note
    assert "Check for updates" in note
