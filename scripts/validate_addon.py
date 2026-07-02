from pathlib import Path
import sys

required = [
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

print('HomeBrain OS repository layout OK')
