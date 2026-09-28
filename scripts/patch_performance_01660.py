from pathlib import Path
import re

path = Path('hubitat-mcp-ai/rootfs/app/performance_semantic_grounding.py')
text = path.read_text()


def sub_once(pattern: str, replacement: str) -> None:
    global text
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    assert count == 1, pattern


sub_once(
    r'_DIRECTIVE = re\.compile\(.*?\n\)\n_CONFIG_TOPIC = re\.compile\(.*?\n\)\n(?=_RULE_EVENT_PRESCRIPTION)',
    '''_DIRECTIVE = re.compile(
    r"(?i)\\b(?:edit|modify|change|add|include|set|adjust|increase|increasing|decrease|decreasing|"
    r"raise|lower|reduce|reduced|reducing|need(?:s|ed)?|lengthen|shorten|ensure|use|using|"
    r"switch|switching|configure|review|inspect|investigate|check|verify|audit|consider|"
    r"disable|disabled|disabling|consolidate|consolidating|slow(?:ing)?\\s+down|fix|fixing)\\b"
)
_CONFIG_TOPIC = re.compile(
    r"(?i)\\b(?:trigger(?:ing)?|thresholds?|debounce|duration|hysteresis|blind time|"
    r"occupancy timeout|poll(?:ing)?(?:\\s+intervals?)?|status polling|auto[- ]refresh|push model|"
    r"reporting intervals?|reporting frequency|reporting thresholds?|config(?:uration)?\\s+push(?:es)?|"
    r"gap between trigger actions|larger gap|cadence|async(?:hronous(?:ly)?)?|"
    r"synchronous(?:ly)?|timeouts?|retries?|reconnect(?:ion|ions|s|ing)?|non[- ]blocking)\\b"
)
'''
)

sub_once(
    r'_MECHANISM = re\.compile\(.*?\n\)\n_ASSERTIVE_MECHANISM_LINK = re\.compile\(.*?\n\)\n_CONDITIONAL_MARKER',
    '''_MECHANISM = re.compile(
    r"(?i)\\b(?:network timeouts?|slow api responses?|api latency|cloud polling|"
    r"frequent polling|polling|config(?:uration)?\\s+push(?:es)?|pushing configurations?|"
    r"retries?|reconnect(?:ion|ions|s|ing)?|blocking network calls?|"
    r"block(?:ing)? hub execution threads?|execution threads?|blocking calls?|blocking risk|"
    r"block(?:ing)? other (?:hub )?(?:activities|automations)|"
    r"pause(?:s|d|ing)? other hub activities?|synchronous http requests?|frequent reporting)\\b"
)
_ASSERTIVE_MECHANISM_LINK = re.compile(
    r"(?i)\\b(?:often|typically|commonly|generally)?\\s*indicat(?:e|es|ed|ing)\\b|"
    r"\\b(?:strongly\\s+)?suggest(?:s|ed|ing)?\\b|"
    r"\\b(?:likely|probably)\\s+(?:due\\s+to|caused\\s+by)\\b|"
    r"\\b(?:is|are|was|were)\\s+(?:typically\\s+)?blocking\\s+calls?\\b|"
    r"\\b(?:is|are|was|were)\\s+(?:a\\s+)?(?:common|primary|main|major|direct)\\s+cause\\b|"
    r"\\bwhich\\s+can\\s+(?:block|cause|lead|result)\\b|"
    r"\\bcan\\s+pause\\s+other\\s+hub\\s+activities\\b|"
    r"\\bcan\\s+(?:block|cause|lead\\s+to|result\\s+in)\\b"
)
_CONDITIONAL_MARKER'''
)

sub_once(
    r'_PERFORMANCE_OUTCOME = re\.compile\(.*?\n\)\n_STRONG_OUTCOME_LINK = re\.compile\(.*?\n\)\n_LIKELY_CANDIDATE_OUTCOME',
    '''_PERFORMANCE_OUTCOME = re.compile(
    r"(?i)\\b(?:hub\\s+lag|lag|stutter|micro[- ]stutters?|sluggish(?:ness)?|instability|"
    r"event[- ]bus\\s+congestion|congestion|inefficien(?:cy|cies)|overload|"
    r"(?:unnecessary\\s+)?load|busy(?:\\s+(?:rate|percentage))?|crash(?:es|ing)?)\\b"
)
_STRONG_OUTCOME_LINK = re.compile(
    r"(?i)\\b(?:primary|main|major|direct)\\s+(?:sources?|causes?|drivers?)\\s+(?:of|for)\\b|"
    r"\\b(?:is|are|was|were)\\s+(?:the\\s+)?(?:primary|main|major|direct)\\s+"
    r"(?:sources?|causes?|drivers?)\\b|"
    r"\\b(?:cause|causes|caused|causing|lead\\s+to|leads\\s+to|leading\\s+to|"
    r"result\\s+in|results\\s+in|contribut(?:e|es|ed|ing)\\s+to|creat(?:e|es|ed|ing))\\b"
)
_LIKELY_CANDIDATE_OUTCOME'''
)

old = '''        prefix = raw_comparable[: raw_link.start()].rstrip(" ,;:-")
        if re.search(
'''
new = '''        prefix = raw_comparable[: raw_link.start()].rstrip(" ,;:-")
        prefix = re.sub(r"(?i)\\bwhich\\s*$", "", prefix).rstrip(" ,;:-")
        if re.search(
'''
assert old in text
text = text.replace(old, new, 1)

old = '''    if _LIKELY_CANDIDATE_OUTCOME.search(comparable):
        return (
            "These are the highest measured consumers to investigate if hub lag or instability occurs; "
            "the current performance statistics do not establish that they will cause those outcomes."
        )
'''
new = '''    if _LIKELY_CANDIDATE_OUTCOME.search(comparable):
        return (
            "These are the highest measured consumers to investigate if hub lag or instability occurs; "
            "the current performance statistics do not establish that they will cause those outcomes."
        )
    if re.search(r"(?i)\\brecent logs\\b.*\\bprimary sources?\\b", comparable):
        return (
            "The recent logs show activity patterns worth investigating; they do not establish primary "
            "sources of performance inefficiency."
        )
'''
assert old in text
text = text.replace(old, new, 1)

marker = '\n\ndef _rewrite_action_line(line: str) -> str:\n'
assert marker in text
helpers = '''

def _normalize_table_header(cell: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"[*_`]", "", cell).casefold()).strip()


def _table_action_column(cells: list[str]) -> int | None:
    for index, cell in enumerate(cells):
        normalized = _normalize_table_header(cell)
        if normalized in {
            "action",
            "actions",
            "recommendation",
            "recommendations",
            "recommended action",
            "recommended actions",
            "improvement",
            "improvements",
        }:
            return index
    return None


def _rewrite_action_cell(text: str) -> str:
    body = str(text or "")
    if body.lstrip().startswith("Inspect the cited"):
        return _dedupe_inspection_guidance(body)
    if _unsafe_recommendation(body):
        return _configuration_guidance(body)
    return _localize_analysis_text(body)
'''
text = text.replace(marker, helpers + marker, 1)

sub_once(
    r'def _rewrite_action_line\(line: str\) -> str:\n.*?\n\ndef ground_performance_semantics',
    '''def _rewrite_action_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return line
    if _TABLE_SEPARATOR.match(line):
        return line
    if stripped.startswith("|") and stripped.endswith("|"):
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if len(cells) >= 2 and cells[0].casefold() not in {"component", ":---", "---"}:
            cells[1] = _rewrite_action_cell(cells[1])
            return "| " + " | ".join(cells) + " |"
        return line

    bullet = _BULLET_PREFIX.match(line)
    if bullet:
        prefix, body = bullet.groups()
        return prefix + _rewrite_action_cell(body)

    if line.lstrip().startswith("Inspect the cited"):
        return _dedupe_inspection_guidance(line)
    if _unsafe_recommendation(line):
        return _configuration_guidance(line)
    return _localize_analysis_text(line)


def ground_performance_semantics'''
)

sub_once(
    r'def ground_performance_semantics\(message: str\) -> str:\n.*?\n\n__all__',
    '''def ground_performance_semantics(message: str) -> str:
    """Ground analysis clauses and action recommendations without erasing measured facts."""

    original = str(message or "")
    if not original:
        return original

    lines: list[str] = []
    in_action_section = False
    action_level: int | None = None
    table_action_index: int | None = None
    trailing_newline = original.endswith("\\n")

    for line in original.splitlines():
        action_heading = _ACTION_SECTION_HEADING.match(line)
        any_heading = _ANY_HEADING.match(line)
        if action_heading:
            in_action_section = True
            action_level = len(action_heading.group(1))
            table_action_index = None
            lines.append(line)
            continue
        if in_action_section and any_heading and action_level is not None:
            if len(any_heading.group(1)) <= action_level:
                in_action_section = False
                action_level = None
                table_action_index = None

        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            if _TABLE_SEPARATOR.match(line):
                lines.append(line)
                continue
            detected_index = _table_action_column(cells)
            if detected_index is not None:
                table_action_index = detected_index
                lines.append(line)
                continue
            if table_action_index is not None and table_action_index < len(cells):
                cells[table_action_index] = _rewrite_action_cell(cells[table_action_index])
                line = "| " + " | ".join(cells) + " |"
            elif in_action_section:
                line = _rewrite_action_line(line)
            elif len(cells) >= 2:
                cells[1] = _localize_analysis_text(cells[1])
                line = "| " + " | ".join(cells) + " |"
            lines.append(line)
            continue

        table_action_index = None
        if in_action_section:
            line = _rewrite_action_line(line)
        else:
            line = _localize_analysis_text(line)
        lines.append(line)

    corrected = "\\n".join(lines)
    if trailing_newline:
        corrected += "\\n"
    return corrected


__all__'''
)

path.write_text(text)
