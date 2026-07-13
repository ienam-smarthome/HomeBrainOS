import ast
import re
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


def yaml_version(path: str) -> str:
    match = re.search(r"(?m)^version:\s*['\"]?([^'\"\s]+)", Path(path).read_text(encoding='utf-8'))
    if not match:
        raise ValueError(f'No version found in {path}')
    return match.group(1)


def python_string_assignment(path: str, name: str) -> str:
    tree = ast.parse(Path(path).read_text(encoding='utf-8'), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError(f'No string assignment for {name} found in {path}')


version_sources = {
    'homebrainos/config.yaml': yaml_version('homebrainos/config.yaml'),
    'addon/homebrainos/config.yaml': yaml_version('addon/homebrainos/config.yaml'),
    'homebrainos/rootfs/app/main.py': python_string_assignment('homebrainos/rootfs/app/main.py', 'APP_VERSION'),
    'addon/homebrainos/rootfs/app/main.py': python_string_assignment('addon/homebrainos/rootfs/app/main.py', 'APP_VERSION'),
}
if len(set(version_sources.values())) != 1:
    print('Version sources differ:')
    for path, version in version_sources.items():
        print(f' - {path}: {version}')
    sys.exit(1)

for path in ('homebrainos/rootfs/app/natural_intelligence.py', 'addon/homebrainos/rootfs/app/natural_intelligence.py'):
    source = Path(path).read_text(encoding='utf-8')
    if re.search(r'(?m)^VERSION\s*=', source) or 'app_module.APP_VERSION =' in source:
        print(f'{path} defines or overwrites the authoritative application version')
        sys.exit(1)

print('HomeBrain OS repository layout OK')
