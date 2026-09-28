from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        ROOT / "hubitat-mcp-ai" / "config.yaml",
        'version: "0.16.60"',
        'version: "0.16.61"',
    )
    replace_once(
        ROOT / "README.md",
        "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.60 |",
        "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.61 |",
    )
    replace_once(
        ROOT / "hubitat-mcp-ai" / "README.md",
        "Current add-on version: **0.16.60**.",
        "Current add-on version: **0.16.61**.",
    )
    replace_once(
        ROOT / "hubitat-mcp-ai" / "CHANGELOG-INDEX.md",
        "## Current release\n\n- [0.16.60](CHANGELOG-0.16.60.md)",
        "## Current release\n\n- [0.16.61](CHANGELOG-0.16.61.md)\n- [0.16.60](CHANGELOG-0.16.60.md)",
    )

    changelog = ROOT / "hubitat-mcp-ai" / "CHANGELOG-0.16.61.md"
    if changelog.exists():
        raise RuntimeError("0.16.61 changelog already exists")
    changelog.write_text(
        """# Hubitat MCP AI 0.16.61

## Evidence-repair cleanup

- Performance source-absence detection now requires explicit absence predicates instead of treating generic `not ... logs/performance` wording as a missing-source claim.
- In substantive performance answers, a contradicted source-absence sentence is removed locally instead of injecting serializer repair prose into a valid device or log observation.
- The pure false-no-data fallback from 0.16.59 remains intact and emits one compact deterministic correction when successful current-turn performance sources were actually read.
- Legitimate negative causality wording such as `does not establish that the logs caused ...` is no longer misclassified as source absence.
- Conditional claims that measured latency `can/could/may/might impact ... responsiveness` are localized to investigative wording that explicitly says the impact is not established.
- No additional Hubitat calls are introduced.

## Live regression coverage

The regression suite reproduces the 0.16.60 Halo evidence-repair leak and the residual LG responsiveness wording while preserving the earlier false-no-data protection. The full release suite contains 1,483 tests.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
