from __future__ import annotations

import subprocess
from pathlib import Path


def project_name() -> str:
    """Best-effort project name: git repo root dir name, else cwd dir name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().name
