from __future__ import annotations

from typing import Any, Callable

import ai_evidence_planner as planner_module
from automation_recommendation import AutomationRecommendationService


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
.result-item.clickable{cursor:pointer;transition:border-color .15s ease,background .15s ease,transform .15s ease}
.result-item.clickable:hover,.result-item.clickable:focus-visible{background:#242428;border-color:#3b82f6;outline:2px solid #3b82f6;outline-offset:1px}
.result-item.clickable:active{transform:translateY(1px)}
"""

_ACTION_FUNCTION = r"""function ruleActionButtons(items){if(!Array.isArray(items)||!items.length)return null;const box=el('div','rule-actions');items.forEach(item=>{const button=el('button','rule-action '+String(item.tone||'secondary'),(item.icon?String(item.icon)+' ':'')+String(item.label||'Continue'));button.type='button';button.onclick=()=>{const query=String(item.query||'').trim();if(!query)return;input.value=query;submit(query)};box.appendChild(button)});return box}"""

_CLICKABLE_ITEM_FUNCTION = r"""function itemList(items){if(!Array.isArray(items)||!items.length)return null;const list=el('div','result-list');items.forEach(item=>{const query=String(item.query||'').trim(),row=el('div','result-item '+(item.tone||'')+(query?' clickable':''));row.appendChild(el('div','',item.icon||'•'));const main=el('div','result-main');main.appendChild(el('div','result-name',item.title||''));if(item.subtitle)main.appendChild(el('div','result-sub',item.subtitle));row.appendChild(main);if(item.value!==undefined&&item.value!==null&&item.value!=='')row.appendChild(el('div','result-side',String(item.value)));if(query){row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label','Select '+String(item.title||item.value||query));const choose=()=>{input.value=query;submit(query)};row.onclick=choose;row.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose()}}}list.appendChild(row)});return list}"""


def install_automation_recommendation_route_precedence() -> Callable[[str], bool]:
    """Keep the capability-aware automation skill ahead of the universal AI fallback.

    The AI Evidence Planner is intentionally the outer fallback in Hybrid Assistant
    mode. Its matcher is resolved dynamically, so excluding this exact specialist
    intent lets the already-installed AutomationRecommendationService receive the
    request. The specialist deterministically inspects selected-device groups and
    capabilities, then optionally uses Ollama only to improve the grounded wording.
    """

    original = planner_module.is_ai_evidence_query
    if getattr(original, "_homebrain_automation_recommendation_precedence", False):
        return original

    def recommendation_safe_policy(query: str) -> bool:
        if AutomationRecommendationService.matches(query):
            return False
        return bool(original(query))

    recommendation_safe_policy._homebrain_automation_recommendation_precedence = True  # type: ignore[attr-defined]
    recommendation_safe_policy._homebrain_previous_policy = original  # type: ignore[attr-defined]
    planner_module.is_ai_evidence_query = recommendation_safe_policy
    return recommendation_safe_policy


def install_automation_recommendation_webui(module: Any) -> Callable[[str], str]:
    """Patch routing precedence, shortcuts, labels and rule-workflow action buttons."""

    install_automation_recommendation_route_precedence()
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

        item_start = rendered.find("function itemList(items){")
        item_end_marker = ";return list}"
        if item_start >= 0:
            item_end = rendered.find(item_end_marker, item_start)
            if item_end >= 0:
                item_end += len(item_end_marker)
                rendered = rendered[:item_start] + _CLICKABLE_ITEM_FUNCTION + rendered[item_end:]

        marker = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)"
        replacement = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));const workflowActions=ruleActionButtons(answer.display.actions);if(workflowActions)output.appendChild(workflowActions);if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)"
        if marker in rendered:
            rendered = rendered.replace(marker, replacement, 1)
        return rendered

    patched._homebrain_automation_recommendation_patch = True  # type: ignore[attr-defined]
    module.patch_page = patched
    return patched


__all__ = [
    "install_automation_recommendation_route_precedence",
    "install_automation_recommendation_webui",
]
