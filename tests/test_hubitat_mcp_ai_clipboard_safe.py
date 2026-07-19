from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui_clipboard_safe import patch_clipboard  # noqa: E402


def test_clipboard_patch_replaces_silent_message_only_handler():
    page = """
    <html><head><style></style></head><body><script>
    function showAnswer(answer){
      const actions=el('div','answer-actions'),copy=el('button','small-button','Copy');copy.onclick=()=>navigator.clipboard?.writeText(answer.message||'');actions.appendChild(copy);
    }
    </script></body></html>
    """

    patched = patch_clipboard(page)

    assert "copy.onclick=()=>homebrainCopyResult(answer,copy);" in patched
    assert "navigator.clipboard?.writeText(answer.message||'')" not in patched
    assert "function homebrainLegacyCopy(text)" in patched
    assert "document.execCommand('copy')" in patched
    assert "window.isSecureContext&&navigator.clipboard" in patched
    assert "function homebrainShowManualCopy(text,button)" in patched


def test_copy_payload_includes_technical_details_and_manual_selection_fallback():
    page = """
    <html><head><style></style></head><body><script>
    const actions=el('div','answer-actions'),copy=el('button','small-button','Copy');copy.onclick=()=>navigator.clipboard?.writeText(answer.message||'');actions.appendChild(copy);
    </script></body></html>
    """

    patched = patch_clipboard(page)

    assert "Technical details\\n'+technical" in patched
    assert "Automatic copy is blocked by this browser" in patched
    assert "area.setSelectionRange(0,area.value.length)" in patched
    assert "Text selected" in patched
    assert "copy-success" in patched
    assert "copy-error" in patched


def test_clipboard_patch_is_idempotent():
    page = """
    <html><head><style></style></head><body><script>
    const actions=el('div','answer-actions'),copy=el('button','small-button','Copy');copy.onclick=()=>navigator.clipboard?.writeText(answer.message||'');actions.appendChild(copy);
    </script></body></html>
    """

    first = patch_clipboard(page)
    second = patch_clipboard(first)

    assert second == first
    assert second.count("function homebrainCopyResult") == 1
