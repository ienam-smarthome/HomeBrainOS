import os
import re
from pathlib import Path
import subprocess
import sys

required = [
    'repository.yaml',
    'hubitat-mcp-ai/config.yaml',
    'hubitat-mcp-ai/Dockerfile',
    'hubitat-mcp-ai/run.sh',
    'hubitat-mcp-ai/rootfs/app/app.py',
    'hubitat-mcp-ai/rootfs/app/mcp_agent_orchestrator.py',
    'hubitat-mcp-ai/rootfs/app/mcp_client.py',
    'hubitat-mcp-ai/rootfs/app/webui.py',
    'hubitat-mcp-ai/rootfs/app/requirements.txt',
    'hubitat-mcp-ai/LICENSE-UPSTREAM',
    'hubitat-mcp-ai/UPSTREAM.md',
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

def yaml_version(path: str) -> str:
    match = re.search(r"(?m)^version:\s*['\"]?([^'\"\s]+)", Path(path).read_text(encoding='utf-8'))
    if not match:
        raise ValueError(f'No version found in {path}')
    return match.group(1)


mcp_ai_version = yaml_version('hubitat-mcp-ai/config.yaml')
changelog = Path(f'hubitat-mcp-ai/CHANGELOG-{mcp_ai_version}.md')
if not changelog.exists():
    print(f'Missing Hubitat MCP AI release notes: {changelog}')
    sys.exit(1)

base_sha = os.environ.get('HUBITAT_MCP_AI_BASE_SHA', '').strip()
if base_sha:
    changed = subprocess.run(
        ['git', 'diff', '--name-only', f'{base_sha}...HEAD'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    runtime_changed = any(
        path.startswith('hubitat-mcp-ai/rootfs/app/')
        or path in {
            'hubitat-mcp-ai/Dockerfile',
            'hubitat-mcp-ai/run.sh',
            'hubitat-mcp-ai/rootfs/app/requirements.txt',
        }
        for path in changed
    )
    if runtime_changed:
        base_config = subprocess.run(
            ['git', 'show', f'{base_sha}:hubitat-mcp-ai/config.yaml'],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        match = re.search(r"(?m)^version:\s*['\"]?([^'\"\s]+)", base_config)
        base_version = match.group(1) if match else ''
        if not base_version or base_version == mcp_ai_version:
            print(
                'Hubitat MCP AI runtime changed without a new add-on version: '
                f'base={base_version or "unknown"}, current={mcp_ai_version}'
            )
            sys.exit(1)

print('Hubitat MCP AI repository layout OK')
