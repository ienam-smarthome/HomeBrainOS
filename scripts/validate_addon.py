from pathlib import Path
import sys

required = [
    'repository.yaml',
    'homebrainos/config.yaml',
    'homebrainos/Dockerfile',
    'homebrainos/run.sh',
    'homebrainos/rootfs/app/main.py',
    'addon/homebrainos/config.yaml',
    'addon/homebrainos/Dockerfile',
    'addon/homebrainos/run.sh',
    'addon/homebrainos/rootfs/app/main.py',
    'backend/integrations/hubitat_maker.py',
    'backend/services/normalizer.py',
    'frontend/index.html',
    '.github/workflows/validate.yml',
]

missing = [p for p in required if not Path(p).exists()]
if missing:
    print('Missing required files:')
    for p in missing:
        print(f' - {p}')
    sys.exit(1)

addon_version = Path('homebrainos/config.yaml').read_text()
legacy_version = Path('addon/homebrainos/config.yaml').read_text()
if addon_version != legacy_version:
    print('Top-level HA add-on config differs from addon/homebrainos/config.yaml')
    sys.exit(1)

print('HomeBrain OS repository layout OK')
