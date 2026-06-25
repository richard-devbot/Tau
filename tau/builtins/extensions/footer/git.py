"""Git branch badge component."""

from __future__ import annotations

from .utils import read_branch, shorten_home


class GitBadge:
    """Renders ``~/path (branch)`` for the footer Row left slot."""

    def __init__(self) -> None:
        self._text = ""

    def update(self, cwd: str) -> None:
        branch = read_branch(cwd)
        display = shorten_home(cwd)
        self._text = f"{display} ({branch})" if branch else display

    def render(self, width: int) -> list[str]:  # noqa: ARG002
        from tau.tui.utils import DIM, RESET

        return [DIM + self._text + RESET]

    def handle_input(self, event: object) -> bool:  # noqa: ARG002
        return False

    def invalidate(self) -> None:
        pass
