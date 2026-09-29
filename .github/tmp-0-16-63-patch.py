from pathlib import Path

root = Path('.')

# 1. Database-size compatibility applies to both metrics and performance stats.
compat_path = root / 'hubitat-mcp-ai/rootfs/app/performance_result_compat.py'
compat = compat_path.read_text()
if '_PERFORMANCE_TOOL = "hub_get_performance_stats"' not in compat:
    raise SystemExit('performance compat tool anchor missing')
compat = compat.replace(
    '_PERFORMANCE_TOOL = "hub_get_performance_stats"',
    '_PERFORMANCE_TOOLS = {"hub_get_metrics", "hub_get_performance_stats"}',
    1,
)
old_gate = '    if name != _PERFORMANCE_TOOL and sub_tool != _PERFORMANCE_TOOL:\n        return result\n'
new_gate = '    if name not in _PERFORMANCE_TOOLS and sub_tool not in _PERFORMANCE_TOOLS:\n        return result\n'
if old_gate not in compat:
    raise SystemExit('performance compat gate anchor missing')
compat_path.write_text(compat.replace(old_gate, new_gate, 1))

# 2. Semantic grounding: preserve ordered list structure, cover overhead and state-size inference.
semantic_path = root / 'hubitat-mcp-ai/rootfs/app/performance_semantic_grounding.py'
semantic = semantic_path.read_text()

bullet_anchor = '_BULLET_PREFIX = re.compile(r"^(\\s*[*+-]\\s+(?:\\*\\*[^*]+\\*\\*(?::\\s*|\\s+))?)(.*)$")\n'
ordered_row = '_ORDERED_PREFIX = re.compile(r"^(\\s*\\d+[.)]\\s+(?:\\*\\*[^*]+\\*\\*(?::\\s*|\\s+))?)(.*)$")\n'
if bullet_anchor not in semantic:
    raise SystemExit('bullet prefix anchor missing')
semantic = semantic.replace(bullet_anchor, bullet_anchor + ordered_row, 1)

old_config = (
    '    r"occupancy timeout|poll(?:ing)?(?:\\s+intervals?)?|status polling|auto[- ]refresh|push model|"\n'
    '    r"reporting intervals?|reporting frequency|reporting thresholds?|config(?:uration)?\\s+push(?:es)?|"\n'
)
new_config = (
    '    r"occupancy timeout|poll(?:ing)?(?:\\s+intervals?)?|status polling|auto[- ]refresh|push model|"\n'
    '    r"state sizes?|cach(?:e|ed|ing)|history (?:stored|retention)|"\n'
    '    r"reporting intervals?|reporting frequency|reporting thresholds?|config(?:uration)?\\s+push(?:es)?|"\n'
)
if old_config not in semantic:
    raise SystemExit('config topic anchor missing')
semantic = semantic.replace(old_config, new_config, 1)

old_outcome = (
    '    r"event[- ]bus\\s+congestion|congestion|inefficien(?:cy|cies)|overload|responsiveness|"\n'
    '    r"(?:unnecessary\\s+)?load|busy(?:\\s+(?:rate|percentage))?|crash(?:es|ing)?)\\b"\n'
)
new_outcome = (
    '    r"event[- ]bus\\s+congestion|congestion|inefficien(?:cy|cies)|overload|responsiveness|"\n'
    '    r"(?:unnecessary\\s+)?load|(?:material\\s+|unnecessary\\s+)?(?:hub\\s+)?overhead|"\n'
    '    r"busy(?:\\s+(?:rate|percentage))?|crash(?:es|ing)?)\\b"\n'
)
if old_outcome not in semantic:
    raise SystemExit('performance outcome anchor missing')
semantic = semantic.replace(old_outcome, new_outcome, 1)

guidance_anchor = "def _configuration_guidance(text: str) -> str:\n    folded = text.casefold().replace('\\\"', \"\").replace(\"“\", \"\").replace(\"”\", \"\")\n"
# Match actual source form instead of relying only on escaping above.
if guidance_anchor not in semantic:
    guidance_anchor = 'def _configuration_guidance(text: str) -> str:\n    folded = text.casefold().replace(\'"\', "").replace("“", "").replace("”", "")\n'
if guidance_anchor not in semantic:
    raise SystemExit('configuration guidance anchor missing')
guidance_insert = '''def _configuration_guidance(text: str) -> str:
    folded = text.casefold().replace('"', "").replace("“", "").replace("”", "")
    if any(
        token in folded
        for token in ("state size", "cached data", "cache", "history stored", "history retention")
    ):
        return (
            "Inspect the cited app implementation/configuration first. The measured state size can justify "
            "inspection, but this turn did not establish what data is retained, whether cache/history retention "
            "is configurable, or its effect on hub memory."
        )
'''
semantic = semantic.replace(guidance_anchor, guidance_insert, 1)

analysis_anchor = 'def _localize_analysis_text(text: str) -> str:\n'
if analysis_anchor not in semantic:
    raise SystemExit('analysis anchor missing')
helpers = '''def _localize_state_storage_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    if not re.search(r"(?i)\\bstate sizes?\\b", comparable):
        return sentence
    if not re.search(r"(?i)\\b(?:suggest|suggests|indicate|indicates|imply|implies)\\b", comparable):
        return sentence
    if not re.search(r"(?i)\\b(?:memory|cache|cached|history|stor(?:e|ed|ing)|data)\\b", comparable):
        return sentence
    return (
        "The measured state size is worth inspecting; the current performance statistics do not establish "
        "what data is stored, whether cache/history retention is configurable, or its effect on hub memory."
    )


def _localize_overhead_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    if not re.search(
        r"(?i)\\b(?:can|could|may|might)?\\s*(?:create|cause|lead\\s+to|result\\s+in)\\b"
        r"[^.!?\\n]{0,140}\\b(?:material\\s+|unnecessary\\s+)?(?:hub\\s+)?overhead\\b",
        comparable,
    ):
        return sentence
    avg = re.search(r"(?i)\\b(\\d[\\d,.]*\\s*ms)\\b", comparable)
    calls = re.search(r"(?i)\\b((?:over\\s+)?\\d[\\d,.]*\\s+(?:calls?|executions?))\\b", comparable)
    facts: list[str] = []
    if avg:
        facts.append(f"Average execution time is {avg.group(1)}.")
    if calls:
        facts.append(f"Measured activity is {calls.group(1)}.")
    facts.append(
        "The measured activity is worth reviewing; the current statistics do not establish that it creates "
        "material hub overhead."
    )
    return " ".join(facts)


'''
semantic = semantic.replace(analysis_anchor, helpers + analysis_anchor, 1)

old_pipeline = '''        localized = _localize_mechanism_sentence(sentence)
        localized = _localize_outcome_sentence(localized)
        if _unsafe_recommendation(localized):
'''
new_pipeline = '''        localized = _localize_state_storage_sentence(sentence)
        localized = _localize_overhead_sentence(localized)
        localized = _localize_mechanism_sentence(localized)
        localized = _localize_outcome_sentence(localized)
        if _unsafe_recommendation(localized):
'''
if old_pipeline not in semantic:
    raise SystemExit('analysis pipeline anchor missing')
semantic = semantic.replace(old_pipeline, new_pipeline, 1)

ordered_anchor = '''    bullet = _BULLET_PREFIX.match(line)
    if bullet:
        prefix, body = bullet.groups()
        return prefix + _rewrite_action_cell(body)

    if line.lstrip().startswith("Inspect the cited"):
'''
ordered_replacement = '''    bullet = _BULLET_PREFIX.match(line)
    if bullet:
        prefix, body = bullet.groups()
        return prefix + _rewrite_action_cell(body)

    ordered = _ORDERED_PREFIX.match(line)
    if ordered:
        prefix, body = ordered.groups()
        return prefix + _rewrite_action_cell(body)

    if line.lstrip().startswith("Inspect the cited"):
'''
if ordered_anchor not in semantic:
    raise SystemExit('ordered-list insertion anchor missing')
semantic = semantic.replace(ordered_anchor, ordered_replacement, 1)
semantic_path.write_text(semantic)

# 3. Prompt policy: richer evidence for broad performance recommendations, without causal promotion.
prompt_path = root / 'hubitat-mcp-ai/rootfs/app/agent_prompt_policy.py'
prompt = prompt_path.read_text()
prompt_anchor = (
    '        "separate \'secondary observations\' heading rather than presenting it as a "\n'
    '        "root cause.\\n"\n'
)
if prompt_anchor not in prompt:
    raise SystemExit('performance prompt anchor missing')
prompt_replacement = (
    '        "separate \'secondary observations\' heading rather than presenting it as a "\n'
    '        "root cause. For a BROAD performance request that also asks for recommendations, "\n'
    '        "metrics plus app/device performance statistics are necessary but not sufficient: "\n'
    '        "after ranking the measured outliers, normally read a bounded recent log window "\n'
    '        "(up to 100 rows) to identify current errors or warnings involving those same "\n'
    '        "components. Do not extrapolate counts or cadence beyond the returned log window. "\n'
    '        "If a recommendation depends on scheduled cadence, polling jobs, or job volume, "\n'
    '        "obtain current-turn scheduler/job evidence before stating the cadence or suggesting "\n'
    '        "consolidation. If calling a device stale or inactive materially affects a recommendation, "\n'
    '        "obtain current-turn last-activity/history evidence first. Logs can reveal current failure "\n'
    '        "patterns, but they still do not prove the root cause of longer-window performance totals. "\n'
    '        "When metrics provide databaseSizeMB, report the explicit numeric database size in MB; "\n'
    '        "do not call the database small, lean, large, or bloated unless current-turn evidence "\n'
    '        "also provides a defined threshold for that qualitative label. Structure broad performance "\n'
    '        "answers so measured findings, recent observed patterns, hypotheses, and grounded next "\n'
    '        "actions remain distinguishable.\\n"\n'
)
prompt_path.write_text(prompt.replace(prompt_anchor, prompt_replacement, 1))

# 4. Focused regressions.
(root / 'tests/test_performance_grounding_0_16_63.py').write_text('''from performance_semantic_grounding import ground_performance_semantics


def test_ordered_recommendation_preserves_number_and_title_when_grounded():
    draft = """### Recommended Improvements
1. **Audit LG latency:** Check polling intervals and increase them.
2) **Trim state:** Check app settings to reduce cached data or history stored within the app.
"""
    corrected = ground_performance_semantics(draft)
    assert "1. **Audit LG latency:** Inspect the cited integration/device configuration first." in corrected
    assert "2) **Trim state:** Inspect the cited app implementation/configuration first." in corrected


def test_event_volume_does_not_claim_material_overhead_without_evidence():
    draft = (
        "While its average execution time is low (4.59ms), this volume of events can create "
        "unnecessary hub overhead."
    )
    corrected = ground_performance_semantics(draft)
    assert "Average execution time is 4.59ms." in corrected
    assert "do not establish that it creates material hub overhead" in corrected
    assert "can create unnecessary hub overhead" not in corrected


def test_state_size_storage_inference_is_localized():
    draft = (
        "The large state sizes in Google Calendar, Octopus Energy, and Life360 suggest they are "
        "storing significant amounts of data in the hub's memory."
    )
    corrected = ground_performance_semantics(draft)
    assert "measured state size is worth inspecting" in corrected
    assert "do not establish what data is stored" in corrected


def test_state_cache_recommendation_requires_configuration_evidence():
    draft = (
        "### Recommended Improvements\n"
        "3. **Optimize App State:** Check the app settings to see if you can reduce the amount "
        "of cached data or history stored within the app itself.\n"
    )
    corrected = ground_performance_semantics(draft)
    assert "3. **Optimize App State:** Inspect the cited app implementation/configuration first." in corrected
    assert "whether cache/history retention is configurable" in corrected
''')

(root / 'tests/test_performance_result_compat_0_16_63.py').write_text('''from mcp_client import MCPToolResult
from performance_result_compat import normalize_performance_result


def _result(data):
    return MCPToolResult(name="hub_read_diagnostics", arguments={}, raw=None, text="", data=data, is_error=False)


def test_metrics_gateway_relabels_legacy_database_size_without_scaling():
    result = _result({"current": {"databaseSizeKB": "148", "freeMemoryKB": "1048576"}})
    normalized = normalize_performance_result(
        "hub_read_diagnostics", {"tool": "hub_get_metrics"}, result
    )
    assert normalized.data["current"]["databaseSizeMB"] == "148"
    assert normalized.data["current"]["databaseSizeRaw"]["value"] == "148"
    assert "databaseSizeKB" not in normalized.data["current"]


def test_direct_metrics_tool_is_supported_too():
    result = _result({"current": {"databaseSizeKB": 166}})
    normalized = normalize_performance_result("hub_get_metrics", {}, result)
    assert normalized.data["current"]["databaseSizeMB"] == 166
''')

(root / 'tests/test_performance_prompt_policy_0_16_63.py').write_text('''from agent_prompt_policy import build_system_prompt


def test_broad_performance_prompt_requires_bounded_diagnostic_breadth():
    prompt = build_system_prompt("Device manifest omitted or unavailable.")
    assert "normally read a bounded recent log window" in prompt
    assert "up to 100 rows" in prompt
    assert "scheduler/job evidence" in prompt
    assert "last-activity/history evidence" in prompt
    assert "databaseSizeMB" in prompt
    assert "explicit numeric database size in MB" in prompt
    assert "measured findings, recent observed patterns, hypotheses, and grounded next actions" in prompt
''')

# 5. Release alignment.
config_path = root / 'hubitat-mcp-ai/config.yaml'
config = config_path.read_text()
if 'version: "0.16.62"' not in config:
    raise SystemExit('config version anchor missing')
config_path.write_text(config.replace('version: "0.16.62"', 'version: "0.16.63"', 1))

root_readme_path = root / 'README.md'
root_readme = root_readme_path.read_text()
component = '| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.62 | Maintained |'
if component not in root_readme:
    raise SystemExit('root README component anchor missing')
root_readme_path.write_text(root_readme.replace(component, component.replace('0.16.62', '0.16.63'), 1))

addon_readme_path = root / 'hubitat-mcp-ai/README.md'
addon_readme = addon_readme_path.read_text()
if 'Current add-on version: **0.16.62**.' not in addon_readme:
    raise SystemExit('add-on README version anchor missing')
addon_readme = addon_readme.replace('Current add-on version: **0.16.62**.', 'Current add-on version: **0.16.63**.', 1)
architecture_anchor = '## Architecture\n\n'
if architecture_anchor not in addon_readme:
    raise SystemExit('architecture anchor missing')
architecture_note = (
    '0.16.63 broadens evidence for broad performance reviews without weakening causal grounding. '
    'After metrics and ranked app/device performance statistics, the model is instructed to inspect '
    'a bounded recent log window for current failure patterns, and to obtain scheduler or last-activity '
    'evidence only when cadence or staleness materially affects a recommendation. Ordered recommendation '
    'labels are preserved when unsafe tuning is localized; state-size storage/cache interpretations and '
    'unproven hub-overhead claims are grounded. The legacy database-size compatibility normalization now '
    'also covers hub_get_metrics, so the explicit MB value can reach synthesis. No deterministic root-cause '
    'claims are added.\n\n'
)
addon_readme_path.write_text(addon_readme.replace(architecture_anchor, architecture_anchor + architecture_note, 1))

(root / 'hubitat-mcp-ai/CHANGELOG-0.16.63.md').write_text('''# Hubitat MCP AI 0.16.63

## Broader performance evidence, same grounding discipline

- Broad performance-and-recommendation requests now instruct the model to read a bounded recent log window after metrics and ranked performance statistics, so live failure patterns can be surfaced without promoting correlation into root cause.
- Scheduler/job evidence is required before cadence/job-volume recommendations, and last-activity/history evidence is required before staleness materially drives a recommendation.
- Database-size compatibility now covers both `hub_get_metrics` and `hub_get_performance_stats`; numeric legacy `databaseSizeKB` values are exposed as `databaseSizeMB` without scaling, with raw provenance retained.
- Broad performance answers are instructed to report the explicit database value/unit and avoid qualitative size labels without an evidence-backed threshold.
- Ordered recommendation numbers/titles survive safety localization.
- Unproven event-volume -> hub-overhead claims and state-size -> cache/history/memory interpretations are localized while measured figures are retained where available.
- Cache/history/state-retention tuning is inspection-first unless current-turn configuration or code supports a concrete change.

## Comparison target

This release deliberately pursues the diagnostic breadth seen in richer external analyses while retaining HomeBrain's evidence policy: recent errors/warnings may motivate investigation, but stale activity, timeouts, heap pressure, log latency, and exact tuning changes are not promoted to proven causes without current-turn linking evidence.
''')

index_path = root / 'hubitat-mcp-ai/CHANGELOG-INDEX.md'
index = index_path.read_text()
entry = '- [0.16.63](CHANGELOG-0.16.63.md)\n'
if entry not in index:
    anchor = '## Current release\n\n'
    if anchor not in index:
        raise SystemExit('changelog index anchor missing')
    index_path.write_text(index.replace(anchor, anchor + entry, 1))
