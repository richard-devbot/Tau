from __future__ import annotations

from collections.abc import Callable

from tau.tui.ansi import BRIGHT_BLACK, RESET
from tau.tui.component import Component


class DynamicBorder(Component):
    """Full-width horizontal rule that adapts to the terminal width."""

    def __init__(self, color: Callable[[str], str] | None = None) -> None:
        self._color = color or (lambda s: BRIGHT_BLACK + s + RESET)

    def render(self, width: int) -> list[str]:
        return [self._color("─" * max(1, width))]

    def invalidate(self) -> None:
        pass
