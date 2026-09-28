from pathlib import Path

path = Path('hubitat-mcp-ai/rootfs/app/performance_semantic_grounding.py')
text = path.read_text()

old = '''        for token in (
            "polling interval",
            "reporting interval",
            "polling frequency",
            "reporting frequency",
            "reporting threshold",
            "config push",
            "configuration push",
        )
'''
new = '''        for token in (
            "polling",
            "poll interval",
            "polling interval",
            "status polling",
            "auto-refresh",
            "push model",
            "reporting interval",
            "polling frequency",
            "reporting frequency",
            "reporting threshold",
            "config push",
            "configuration push",
        )
'''
assert old in text
text = text.replace(old, new, 1)

old = '''def _localize_outcome_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    if not _PERFORMANCE_OUTCOME.search(comparable):
        return sentence
'''
new = '''def _localize_outcome_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    folded = comparable.casefold()
    if "implementation cause of that measured load is not established" in folded:
        return sentence
    if not _PERFORMANCE_OUTCOME.search(comparable):
        return sentence
'''
assert old in text
text = text.replace(old, new, 1)

old = '''        if raw_relation and raw_relation.start() > 0:
            prefix = sentence[: raw_relation.start()].rstrip(" ,;:-")
            if prefix:
                return (
                    prefix
                    + "; this is a measured performance concern, but the current statistics do not establish "
                    + "that it causes hub lag, stutter, congestion, or instability."
                )
'''
new = '''        if raw_relation and raw_relation.start() > 0:
            measured_busy = re.search(
                r"\\*{0,2}\\d[\\d,.]*\\s*%\\s+busy(?:\\s+(?:rate|percentage))?\\*{0,2}",
                sentence,
                re.IGNORECASE,
            )
            if measured_busy:
                return (
                    measured_busy.group(0)
                    + "; this is a measured result, but the current statistics do not establish "
                    + "that the cited activity causes that busy rate."
                )
            prefix = sentence[: raw_relation.start()].rstrip(" ,;:-")
            if prefix:
                return (
                    prefix
                    + "; this is a measured performance concern, but the current statistics do not establish "
                    + "that it causes hub lag, stutter, congestion, or instability."
                )
'''
assert old in text
text = text.replace(old, new, 1)

path.write_text(text)
