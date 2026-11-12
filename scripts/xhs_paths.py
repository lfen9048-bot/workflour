"""Shared machine-local paths for the Xiaohongshu deployment and workflow."""
import os
from pathlib import Path


def deployment_path():
    return Path(os.environ.get('XHS_DEPLOYMENT_MANIFEST',
                os.environ.get('WORKFLOUR_XHS_DEPLOYMENT',
                               Path.home() / '.workflour/xhs/deployment.json'))).expanduser()
