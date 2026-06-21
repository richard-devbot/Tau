"""Shared helpers for the status extension."""

from __future__ import annotations


def read_branch(cwd: object) -> str:
    """Return the current git branch name for the given directory, or ''."""
    import os
    from pathlib import Path

    try:
        path = Path(str(cwd))
        for candidate in [path, *path.parents]:
            git = candidate / ".git"
            if git.is_dir():
                head = git / "HEAD"
            elif git.is_file():
                content = git.read_text(encoding="utf-8").strip()
                if not content.startswith("gitdir: "):
                    continue
                gitdir = os.path.normpath(os.path.join(str(candidate), content[8:].strip()))
                head = Path(gitdir) / "HEAD"
            else:
                continue
            if not head.is_file():
                continue
            text = head.read_text(encoding="utf-8").strip()
            if text.startswith("ref: refs/heads/"):
                return text[len("ref: refs/heads/") :]
            return text[:7]
        return ""
    except OSError:
        return ""


def shorten_home(path: str) -> str:
    """Replace the home directory prefix with ``~``."""
    import os

    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path
