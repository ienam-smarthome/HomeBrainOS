"""Bounded, conservative Groovy method-scope evidence for model investigations.

Completeness of a retrieved file is not completeness of source *excerpts*.
We identify candidates with explicit typed/def Groovy signatures and balanced
braces, produce full method excerpts when budget permits, and label all
truncations and uncertain lexical syntax. This is source indexing only,
not semantic proof that a saved setting changes an existing timer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_METHOD_DECL = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|static|final|synchronized)"
    r"[ \t]+)*(?:def|void|boolean|Boolean|String|int|long|Integer|"
    r"Long|Map|List|BigDecimal|Object|Double|Float)[ \t]+"
    r"([A-Za-z_][A-Za-z_0-9]*)[ \t]*\(",
)
_MAX_METHODS = 500
_MAX_SCOPE_CHARS = 13000


@dataclass(frozen=True)
class _Candidate:
    name: str
    first: int
    last: int
    brace_closed: bool
    lexical_uncertainty: bool


def _mask_non_code(source: str) -> str:
    """Replace comments and quoted strings while preserving offsets/newlines.

    This handles common Groovy strings and C-style comments. Groovy slashy
    strings are complex; they are explicitly flagged as lexical uncertainty
    rather than certifying a method boundary.
    """
    result = list(source)
    n = len(source)
    i = 0
    state = "code"
    quote = ""
    while i < n:
        ch = source[i]
        look = source[i:i+3]
        if state == "code":
            if source.startswith("//", i):
                state = "line"; result[i:i+2] = "  "; i += 2; continue
            if source.startswith("/*", i):
                state = "block"; result[i:i+2] = "  "; i += 2; continue
            if look in ("'''", '"""'):
                quote = look; state = "triple"
                result[i:i+3] = "   "; i += 3; continue
            if ch in ("'", '"'):
                quote = ch; state = "string"
                result[i] = " "; i += 1; continue
            i += 1; continue
        if state == "line":
            if ch == "\n":
                state = "code"
            else:
                result[i] = " "
            i += 1; continue
        if state == "block":
            if source.startswith("*/", i):
                result[i:i+2] = "  "; i += 2; state = "code"; continue
            if ch != "\n":
                result[i] = " "
            i += 1; continue
        if state == "triple":
            if source.startswith(quote, i):
                result[i:i+3] = "   "; i += 3; state = "code"; continue
            if ch != "\n":
                result[i] = " "
            i += 1; continue
        # string (single/double)
        if ch == "\\" and i + 1 < n:
            result[i:i+2] = "  "; i += 2; continue
        if ch == quote:
            result[i] = " "; i += 1; state = "code"; continue
        if ch != "\n":
            result[i] = " "
        i += 1
    return "".join(result)


def _line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _definitions(source: str, mask: str) -> list[_Candidate]:
    out: list[_Candidate] = []
    for match in _METHOD_DECL.finditer(mask):
        if len(out) >= _MAX_METHODS:
            break
        # Only open a method if its body begins within a bounded signature
        # window. An abstract/interface declaration isn't a body.
        brace = mask.find("{", match.end(), min(len(mask), match.end() + 600))
        semi = mask.find(";", match.end(), min(len(mask), match.end() + 600))
        if brace < 0 or (semi >= 0 and semi < brace):
            continue
        depth = 0
        stop = -1
        for index in range(brace, len(mask)):
            if mask[index] == "{":
                depth += 1
            elif mask[index] == "}":
                depth -= 1
                if depth == 0:
                    stop = index+1
                    break
        end = stop if stop >= 0 else len(source)
        # Groovy slashy/dollar-slashy literals can contain braces that this
        # conservative lexer does not understand. Do not certify boundaries
        # in the presence of those constructs.
        body = source[match.start():end]
        uncertain = "$/" in body or bool(
            re.search(r"(?m)(?:=|return|\(|,)\s*/(?![/*])", body)
        )
        out.append(_Candidate(
            name=match.group(1),
            first=match.start(), last=end,
            brace_closed=stop >= 0, lexical_uncertainty=uncertain,
        ))
    return out


def _lines_excerpt(source: str, first: int, last: int) -> str:
    begin = _line_of(source, first)
    prefix = source[:first].rfind("\n") + 1
    # Excerpt begins at line boundary; a following method starts on its
    # own line. Its final closing-brace line is included in the output.
    text = source[prefix:last]
    return "\n".join(
        f"{begin + index}: {line}"
        for index, line in enumerate(text.splitlines())
    )


def build_method_scope_evidence(
    source: str, symbols: tuple[str, ...], *,
    budget: int = _MAX_SCOPE_CHARS,
) -> tuple[list[str], list[str]]:
    """Return bounded provenance notes and full/truncated method excerpts.

    An excerpt is labelled whole-body only when balanced, lexically safe and
    shown in its entirety. Unmatched names and unshown methods do not imply
    absent behaviours, even if the complete source file was retrieved.
    """
    if not source or budget <= 0:
        return [], []
    mask = _mask_non_code(source)
    definitions = _definitions(source, mask)
    notes: list[str] = []
    excerpts: list[str] = []
    selected: set[tuple[int, int]] = set()
    spent = 0
    for requested in symbols:
        bare = requested.removesuffix("()").split(".")[-1]
        escaped = re.escape(requested.removesuffix("()"))
        occurrences = list(re.finditer(escaped, mask, flags=re.I))
        direct = [m for m in definitions if m.name.casefold() == bare.casefold()]
        containing = [
            m for m in definitions
            if any(m.first <= hit.start() < m.last for hit in occurrences)
        ]
        choices = []
        for candidate in direct + containing:
            if (candidate.first, candidate.last) not in {
                (m.first,m.last) for m in choices
            }:
                choices.append(candidate)
        notes.append(
            f"- {requested}: {len(occurrences)} code-text occurrence(s); "
            + (f"{len(choices)} candidate method scope(s)." if choices else
               "no recognized enclosing method; field-level or unmatched reference.")
        )
        for method in choices[:2]:
            key = method.first, method.last
            if key in selected:
                continue
            selected.add(key)
            excerpt = _lines_excerpt(source, method.first, method.last)
            line_start = _line_of(source, method.first)
            line_end = _line_of(source, method.last-1)
            structural = method.brace_closed and not method.lexical_uncertainty
            label = (
                "balanced candidate body" if structural else
                "boundary uncertain (unclosed body or unsupported string syntax)"
            )
            if spent + len(excerpt) <= budget:
                notes.append(
                    f"  - {method.name} lines {line_start}-{line_end}: "
                    f"{label}; full method body included in excerpt."
                )
                excerpts.append(excerpt)
                spent += len(excerpt)
            else:
                notes.append(
                    f"  - {method.name} lines {line_start}-{line_end}: "
                    f"{label}; complete method body NOT shown (excerpt budget)."
                )
        if len(choices) > 2:
            notes.append(
                f"  - {len(choices)-2} additional candidate scope(s) not "
                "shown; examine separately before excluding alternative paths."
            )
    if not definitions:
        notes.append(
            "- No supported method-definition syntax recognized; this does "
            "not prove that the implementation contains no methods."
        )
    notes.append(
        "- Method scope is lexical indexing, not a Groovy compiler or a "
        "complete call graph. Full-source retrieval does not prove all "
        "state mutation/reinitialization paths were examined."
    )
    return notes, excerpts


__all__ = ["build_method_scope_evidence"]
