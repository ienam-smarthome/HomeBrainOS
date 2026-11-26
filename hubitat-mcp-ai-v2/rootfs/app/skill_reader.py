"""Local read-only tool that serves the bundled evidence skills on demand.

The upstream-first prompt profile keeps only the Hubitat server's own skill, its
safety guide and a short client contract in the system prompt. The client-authored
evidence references are loaded by the model when it decides a question needs them
(progressive disclosure). The tool takes a skill name from a fixed list and returns
the bundled file; it never inspects the user's question, runs nothing and writes
nothing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

TOOL_NAME = "homebrain_read_skill"
SKILL_DIR = Path(__file__).parent / "skills" / "hubitat"

# name -> (file, when to read it). The index text below is built from this table.
SKILLS: dict[str, tuple[str, str]] = {
    "causal-investigations": (
        "causal-investigations.md",
        "why/cause questions, 'what changed', or any answer that states a cause",
    ),
    "measurement-fidelity": (
        "measurement-fidelity.md",
        "numbers, counts, durations, battery/uptime/usage figures and comparisons",
    ),
    "answer-presentation": (
        "answer-presentation.md",
        "writing a final answer that lists many devices/rows or mixes sources",
    ),
    "rule-patterns": (
        "rule-patterns.md",
        "building or changing Rule Machine rules (also available via hub_get_tool_guide)",
    ),
}

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Read one bundled client skill (guidance text, not live hub data). "
            "Skills: " + "; ".join(f"{name} - {when}" for name, (_, when) in SKILLS.items())
            + ". Reading a skill runs nothing and changes nothing."
        ),
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": list(SKILLS)}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}


def skill_index() -> str:
    """One line per skill for the system prompt."""
    return "\n".join(f"- {name}: {when}" for name, (_, when) in SKILLS.items())


class SkillError(ValueError):
    pass


def read_skill(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict) or set(args) - {"name"} or "name" not in args:
        raise SkillError("Use only the name argument")
    name = args["name"]
    if not isinstance(name, str) or name not in SKILLS:
        raise SkillError("Unknown skill; choose one of: " + ", ".join(SKILLS))
    filename = SKILLS[name][0]
    return {"skill": name, "text": (SKILL_DIR / filename).read_text(encoding="utf-8")}
