from pathlib import Path


APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
BANNED_SUFFIXES = (
    "_final",
    "_safe",
    "_verified",
    "_fixed",
    "_v2",
    "_new",
    "_release",
)


def test_app_modules_do_not_use_patch_suffixes():
    offenders = sorted(
        path.name
        for path in APP_DIR.glob("*.py")
        if path.stem.lower().endswith(BANNED_SUFFIXES)
    )
    assert not offenders, (
        "Merge fixes into the canonical module as required by CONTRIBUTING.md; "
        f"banned suffixes found: {offenders}"
    )


def test_app_modules_have_no_case_insensitive_duplicates():
    grouped: dict[str, list[str]] = {}
    for path in APP_DIR.glob("*.py"):
        grouped.setdefault(path.name.casefold(), []).append(path.name)
    duplicates = {
        key: names for key, names in grouped.items() if len(names) > 1
    }
    assert not duplicates, (
        "Case-insensitive duplicate module names are not portable: "
        f"{duplicates}"
    )
