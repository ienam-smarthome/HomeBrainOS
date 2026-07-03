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

duplicate_pairs = [
    ('homebrainos/config.yaml', 'addon/homebrainos/config.yaml'),
    ('homebrainos/Dockerfile', 'addon/homebrainos/Dockerfile'),
    ('homebrainos/run.sh', 'addon/homebrainos/run.sh'),
    ('homebrainos/rootfs/app/main.py', 'addon/homebrainos/rootfs/app/main.py'),
    ('homebrainos/rootfs/app/requirements.txt', 'addon/homebrainos/rootfs/app/requirements.txt'),
    ('homebrainos/rootfs/app/static/index.html', 'addon/homebrainos/rootfs/app/static/index.html'),
]

for canonical, legacy in duplicate_pairs:
    if Path(canonical).read_text(encoding='utf-8') != Path(legacy).read_text(encoding='utf-8'):
        print(f'{canonical} differs from {legacy}')
        sys.exit(1)

print('HomeBrain OS repository layout OK')
