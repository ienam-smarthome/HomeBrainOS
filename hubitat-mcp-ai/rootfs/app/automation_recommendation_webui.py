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
    "mcp-rule-draft": "Hubitat rule draft",
    "mcp-rule-created": "Hubitat rule created",
    "mcp-rule-tested": "Hubitat rule test",
    "mcp-rule-enabled": "Hubitat rule enabled",
    "mcp-rule-paused": "Hubitat rule paused",
    "mcp-rule-duplicate": "Existing Hubitat rule",
    "mcp-rule-workflow": "Hubitat rule workflow",
}

_ACTION_CSS = r"""
.rule-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0 4px}
.rule-action{width:100%;margin:0;padding:10px 12px;border-radius:10px;background:#1d4ed8;font-size:13px;font-weight:700}
.rule-action.secondary{background:#333}
.rule-action.warning{background:#92400e}
.rule-action.danger{background:#991b1b}
.rule-action.primary{background:#166534}
.rule-action:disabled{opacity:.55}
"""

_ACTION_FUNCTION = r"""function ruleActionButtons(items){if(!Array.isArray(items)||!items.length)return null;const box=el('div','rule-actions');items.forEach(item=>{const button=el('button','rule-action '+String(item.tone||'secondary'),(item.icon?String(item.icon)+' ':'')+String(item.label||'Continue'));button.type='button';button.onclick=()=>{const query=String(item.query||'').trim();if(!query)return;input.value=query;submit(query)};box.appendChild(button)});return box}"
"""


def install_automation_recommendation_webui(module: Any) -> Callable[[str], str]:
    """Patch shortcuts, route labels and safe rule-workflow action buttons."""
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

        if ".rule-actions{" not in rendered:
            rendered = rendered.replace("</style>", _ACTION_CSS + "</style>", 1)
        if "function ruleActionButtons(items)" not in rendered:
            rendered = rendered.replace(
                "function routeLabel(route){",
                _ACTION_FUNCTION + "\nfunction routeLabel(route){",
                1,
            )

        marker = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)"
        replacement = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));const workflowActions=ruleActionButtons(answer.display.actions);if(workflowActions)output.appendChild(workflowActions);if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)"
        if marker in rendered:
            rendered = rendered.replace(marker, replacement, 1)
        return rendered

    patched._homebrain_automation_recommendation_patch = True  # type: ignore[attr-defined]
    module.patch_page = patched
    return patched


__all__ = ["install_automation_recommendation_webui"]
