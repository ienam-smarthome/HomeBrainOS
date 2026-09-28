from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"expected one replacement for {label}, got {count}")
    return updated


def patch_evidence_source_guard() -> None:
    path = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "evidence_source_guard.py"
    text = path.read_text(encoding="utf-8")

    source_block = r'''_PERFORMANCE_SOURCE_TERM = (
    r"(?:metrics?|performance\\s+(?:statistics?|stats?)|logs?|log\\s+entries|necessary\\s+data)"
)
_PERFORMANCE_SOURCE_ABSENCE = re.compile(
    rf"(?i)(?:"
    rf"\\b(?:current-turn\\s+)?evidence\\b[^.!?]{{0,80}}\\b(?:does|do|did)\\s+not\\s+"
    rf"(?:provide|include|contain|return|supply)\\b[^.!?]{{0,100}}\\b{_PERFORMANCE_SOURCE_TERM}\\b"
    rf"|\\bno\\b[^.!?]{{0,160}}\\b{_PERFORMANCE_SOURCE_TERM}\\b[^.!?]{{0,100}}"
    rf"\\b(?:was|were|is|are)?\\s*(?:returned|provided|supplied|available|retrieved|received|included|present)\\b"
    rf"|\\b{_PERFORMANCE_SOURCE_TERM}\\b[^.!?]{{0,120}}\\b(?:was|were|is|are|did)\\s+not\\s+"
    rf"(?:returned|provided|supplied|available|retrieved|received|included|present|checked|read|queried)\\b"
    rf")"
)

_SUBSTANTIVE_PERFORMANCE_CONTENT = re.compile(
    r"(?i)(?:\\b\\d[\\d,.]*\\s*(?:%|ms|mb|kb|°c)\\b|\\bcall count\\b|"
    r"\\bresource consumers?\\b|\\bperformance analysis\\b|"
    r"\\blogs?\\s+(?:show|shows|showed|indicate|indicates|indicated|record|records|recorded|contain|contains|contained)\\b|"
    r"\\breporting\\b[^.!?\\n]{0,80}\\bevery\\s+\\d+)"
)
'''
    text = replace_once(
        text,
        r"_PERFORMANCE_SOURCE_ABSENCE = re\.compile\(.*?\n\)\n\n_POSITIVE_LOG_ATTRIBUTION",
        source_block + "\n_POSITIVE_LOG_ATTRIBUTION",
        "performance source absence patterns",
    )

    guard_function = r'''def _guard_performance_source_absence(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct false claims that successful metrics/performance/log reads were absent.

    In a substantive performance answer, remove only the contradicted refusal sentence.
    Do not splice serializer repair prose into a valid device/log observation.  For a
    pure source-absence refusal, retain one compact deterministic correction so the
    final response cannot falsely claim that successful current-turn reads were missing.
    """

    sources = _successful_performance_sources(evidence)
    text = str(message or "")
    if not sources or not _PERFORMANCE_SOURCE_ABSENCE.search(text):
        return text, False

    pieces = _sentence_pieces(text)
    substantive = bool(
        _SUBSTANTIVE_PERFORMANCE_CONTENT.search(
            _PERFORMANCE_SOURCE_ABSENCE.sub("", text)
        )
    )
    changed = False
    rendered_correction = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _PERFORMANCE_SOURCE_ABSENCE.search(sentence):
            continue
        comparable = sentence.casefold()
        relevant = False
        if "hub metrics" in sources and ("metric" in comparable or "necessary data" in comparable):
            relevant = True
        if "performance statistics" in sources and ("performance" in comparable or "necessary data" in comparable):
            relevant = True
        if "logs" in sources and ("log" in comparable or "necessary data" in comparable):
            relevant = True
        if not relevant:
            continue

        if substantive:
            pieces[index] = ""
        elif not rendered_correction:
            rendered = sources[0] if len(sources) == 1 else ", ".join(sources[:-1]) + f" and {sources[-1]}"
            pieces[index] = (
                f"Current-turn evidence did include successful {rendered}; "
                "those results should be used for the requested performance analysis."
            )
            rendered_correction = True
        else:
            pieces[index] = ""
        changed = True

    corrected = "".join(pieces)
    if substantive and changed:
        corrected = re.sub(r"[ \t]+\n", "\n", corrected)
        corrected = re.sub(r"\n{3,}", "\n\n", corrected)
        corrected = corrected.rstrip()
    return corrected, changed

'''
    text = replace_once(
        text,
        r"def _guard_performance_source_absence\(.*?(?=\ndef guard_checked_source_absence_claim)",
        guard_function,
        "performance source absence guard",
    )
    path.write_text(text, encoding="utf-8")


def patch_performance_semantics() -> None:
    path = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "performance_semantic_grounding.py"
    text = path.read_text(encoding="utf-8")

    old = (
        '    r"(?i)\\b(?:hub\\s+lag|lag|stutter|micro[- ]stutters?|sluggish(?:ness)?|instability|"\n'
        '    r"event[- ]bus\\s+congestion|congestion|inefficien(?:cy|cies)|overload|"\n'
        '    r"(?:unnecessary\\s+)?load|busy(?:\\s+(?:rate|percentage))?|crash(?:es|ing)?)\\b"\n'
    )
    new = (
        '    r"(?i)\\b(?:hub\\s+lag|lag|stutter|micro[- ]stutters?|sluggish(?:ness)?|instability|"\n'
        '    r"event[- ]bus\\s+congestion|congestion|inefficien(?:cy|cies)|overload|responsiveness|"\n'
        '    r"(?:unnecessary\\s+)?load|busy(?:\\s+(?:rate|percentage))?|crash(?:es|ing)?)\\b"\n'
    )
    if old not in text:
        raise RuntimeError("performance outcome block not found")
    text = text.replace(old, new, 1)

    anchor = '''    if re.search(r"(?i)\\brecent logs\\b.*\\bprimary sources?\\b", comparable):
        return (
            "The recent logs show activity patterns worth investigating; they do not establish primary "
            "sources of performance inefficiency."
        )
'''
    addition = anchor + '''    if re.search(
        r"(?i)\\b(?:can|could|may|might)\\s+(?:impact|affect|degrade|reduce|hurt)\\b"
        r"[^.!?]{0,120}\\b(?:hub\\s+)?responsiveness\\b",
        comparable,
    ):
        return (
            "The measured latency is worth investigating as a possible contributor to responsiveness; "
            "the current evidence does not establish that it affects overall hub responsiveness."
        )
'''
    if anchor not in text:
        raise RuntimeError("conditional outcome anchor not found")
    text = text.replace(anchor, addition, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_evidence_source_guard()
    patch_performance_semantics()


if __name__ == "__main__":
    main()
