# HomeBrainOS 0.18.132 — causal focus and useful app metadata

- `hub_list_apps`/`hub_list_rules` V2 results now project a small, bounded current app identity catalogue from typed ID/name pairs. No raw MCP summaries, source code, HTML, passwords or arbitrary settings enter the canonical evidence case. An app label identifies the current app, not which rule triggered historically.
- The investigative summary ranks possible conflicting OFF → ON/`setLevel` sequences by proximity to the requested incident's temporal centre, rather than choosing the first such sequence. The 00:41/00:49 overnight pair can now take precedence over an earlier 18:37 pair without device-specific scripted rules.
- Successful reads with no *new usable* timestamped evidence or typed identity cannot justify additional AI planning rounds: V2 exits with an explicit `no_new_usable_evidence` status rather than repeat a low-information prompt until timeout. Other reads with useful data retain normal planning.
- New measured issuer-to-app name coverage metric. All identity metadata is shown with provenance and bounded verification.
- Production V1, model write tools and device/rule modifications remain untouched. Live regression evidence is still necessary before any V2 production cutover.
