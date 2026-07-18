from __future__ import annotations

from typing import Any, Callable


_AUTOMATION_SHORTCUT = (
    '<button class="secondary" data-q="Suggest one useful automation for the devices I have">'
    '⚙️ Suggest automation</button>'
)

_ROUTE_LABELS = {
    "ollama+automation-recommendation": "Ollama recommendation",
    "mcp-automation-recommendation-ai-fallback": "Hubitat recommendation (AI fallback)",
    "mcp-automation-recommendation": "Hubitat recommendation",
}


def install_automation_recommendation_webui(module: Any) -> Callable[[str], str]:
    """Patch the final generated page without duplicating the base Web UI renderer."""
    original = module.patch_page
    if getattr(original, "_homebrain_automation_recommendation_patch", False):
        return original

    def patched(page: str) -> str:
        rendered = original(page)
        shortcut_anchor = (
            '<button class="secondary" data-q="What can Ollama help with?">'
            '🤖 AI question guide</button>'
        )
        if _AUTOMATION_SHORTCUT not in rendered:
            rendered = rendered.replace(
                shortcut_anchor,
                shortcut_anchor + _AUTOMATION_SHORTCUT,
                1,
            )

        label_marker = "'error':'Error'}"
        if label_marker in rendered:
            additions = "".join(
                f",'{route}':'{label}'" for route, label in _ROUTE_LABELS.items()
            )
            rendered = rendered.replace(
                label_marker,
                "'error':'Error'" + additions + "}",
                1,
            )
        return rendered

    patched._homebrain_automation_recommendation_patch = True  # type: ignore[attr-defined]
    module.patch_page = patched
    return patched


__all__ = ["install_automation_recommendation_webui"]
