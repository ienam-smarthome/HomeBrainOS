# HomeBrainOS V2 alpha.82 — light-theme legibility correction

**14 November 2026 — V2 only.** The installed alpha.81 desktop screenshots showed dark legacy surfaces remaining in Hub Diagnostics and AI Evaluation while the new light theme inherited near-black text. This made the diagnostics numbers, panel headings, explanatory labels and evaluation consent form difficult to read. The Ask privacy/helper text also mixed two variable systems.

## Changes

- Reconcile legacy `--bg`, `--panel`, `--txt`, `--muted`, `--blue`, `--green` and `--edge` with alpha.81 `--hb-*` tokens inside `prefers-color-scheme: light` only. In dark mode the existing established colours remain unchanged.
- Restore clean light surfaces and dark text to the **Diagnostics metric cards and their numerical values**, timeline card heading/legend/controls/notes and AI Evaluation cards/consent/upload/worksheet. Ensure interactive button text and disabled states are readable.
- Preserve the original **dark SVG/canvas plot surfaces and native-coloured lines**, including zoom and axis behaviour. Graph tooltips remain light text on dark backgrounds; adjacent information panels become light.
- Avoid changes to V2 reasoning, MCP gateway/tools, confirmation, model routing, source evidence, diagnostics sampling/algorithms or graph rendering. **V1 (`hubitat-mcp-ai/`) is unchanged.**

## Accessibility verification

The disconnected Chromium fixture tests measure the **actual computed foreground/background CSS** in both light and dark modes, desktop and 390px, for Ask helper text, dashboard metrics, Diagnostics headings/values/legend/readouts/buttons, and AI Evaluation labels and form text. Normal text must achieve at least **4.5:1** WCAG contrast; the CI will fail if a sampled element falls below this threshold. The test also creates clearly labelled fictional screenshots for each panel and colour theme. SVG graph-axis text is intentionally drawn on original dark chart surfaces and is not replaced with dark-theme tokens.

The selected light palette has planned contrast ratios: main text `#182640` on white **15.11:1**; secondary text `#52617a` on white **6.27:1**; secondary text on light slate `#edf2f9` **5.57:1**; graph popout links `#165da9` on `#e7effa` **5.71:1**. The real browser check is authoritative over these calculated design values.

All fixture data is fictional; no Hubitat, HA, external voice service or installed model was called. CI is a rendering and structural gate, not independent installed usability confirmation.

## Installed follow-up

After installing alpha.82, review light and dark at the Ask, Hub Diagnostics and AI Evaluation tabs in the actual browser, plus one graph popout and the 390px/mobile layout. Prefer natural text size and verify all consent/help text remains legible. If the browser is forcing a theme, its `prefers-color-scheme` setting determines which palette is used.
