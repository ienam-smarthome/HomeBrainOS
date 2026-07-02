from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addon" / "homebrainos"
REQUIRED = [
    ADDON / "config.yaml",
    ADDON / "Dockerfile",
    ADDON / "run.sh",
]

errors = []
for path in REQUIRED:
    if not path.exists():
        errors.append(f"Missing required file: {path.relative_to(ROOT)}")

config = ADDON / "config.yaml"
if config.exists():
    try:
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        for key in ["name", "version", "slug", "description"]:
            if key not in data:
                errors.append(f"config.yaml missing key: {key}")
    except Exception as exc:
        errors.append(f"config.yaml is not valid YAML: {exc}")

if errors:
    print("HomeBrain OS validation failed:")
    for err in errors:
        print(f"- {err}")
    sys.exit(1)

print("HomeBrain OS add-on validation passed.")
