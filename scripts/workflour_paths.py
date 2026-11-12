"""Host-local record paths; no account or runtime state is copied between hosts."""
import os
from pathlib import Path


def vault_path():
    configured = os.environ.get('WORKFLOUR_OBSIDIAN_VAULT')
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise ValueError('WORKFLOUR_OBSIDIAN_VAULT must be an absolute path')
        return path
    legacy = Path('/Users/a1/Documents/Obsidian/多Agent协作开发工作流')
    if Path.home() == Path('/Users/a1') and legacy.is_dir():
        return legacy
    return Path.home() / 'Documents/Obsidian/Workflour'
