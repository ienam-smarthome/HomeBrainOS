from __future__ import annotations

from webui_homebrain import render_homebrain_page


HOME_BRAIN_MOBILE_PATCH = r"""
.connection-tile{display:none}
.model-value{font-size:22px;overflow-wrap:normal;word-break:normal;letter-spacing:-.02em}
#summaryCard .metric{min-height:82px}
@media(max-width:820px){
  #summaryCard{grid-template-columns:repeat(2,minmax(0,1fr))}
  .shortcut-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .model-value{font-size:20px}
}
@media(max-width:380px){
  .model-value{font-size:18px}
  #summaryCard .metric{padding:9px}
}
"""


def render_page(title: str, version: str) -> str:
    """Render the compact HomeBrain-style interface for Hubitat MCP AI."""
    page = render_homebrain_page(title, version)
    page = page.replace(
        '<div class="metric"><div class="big" id="mcpState">',
        '<div class="metric connection-tile"><div class="big" id="mcpState">',
    )
    page = page.replace(
        '<div class="metric"><div class="big" id="ollamaState">',
        '<div class="metric connection-tile"><div class="big" id="ollamaState">',
    )
    page = page.replace(
        'class="big" id="model"',
        'class="big model-value" id="model"',
    )
    return page.replace("</style>", HOME_BRAIN_MOBILE_PATCH + "</style>", 1)
