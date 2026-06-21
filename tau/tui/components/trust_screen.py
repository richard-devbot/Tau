from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from tau.tui.ansi import BOLD, BRIGHT_BLACK, BRIGHT_WHITE, CYAN, RESET
from tau.tui.component import Component
from tau.tui.input import InputEvent, KeyEvent

if TYPE_CHECKING:
    from tau.trust.manager import TrustOption


class TrustScreen(Component):
    """Full-screen trust prompt shown before the normal TUI layout.

    Replaces the TUI root until the user makes a trust decision.
    Navigation: up/down arrows, Enter to confirm, Esc to cancel.
    """

    def __init__(
        self,
        cwd: str,
        options: list[TrustOption],
        on_commit: Callable[[TrustOption | None], None],
    ) -> None:
        self._cwd = cwd
        self._options = options
        self._selected = 0
        self._on_commit = on_commit

    # -------------------------------------------------------------------------
    # Component
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        indent = "  "

        lines.append("")
        lines.append("")

        lines.append(indent + BOLD + BRIGHT_WHITE + "Trust project folder?" + RESET)
        lines.append("")

        cwd_display = self._cwd
        if len(cwd_display) > width - len(indent) - 2:
            cwd_display = "…" + cwd_display[-(width - len(indent) - 3) :]
        lines.append(indent + CYAN + cwd_display + RESET)
        lines.append("")

        lines.append(
            indent + BRIGHT_BLACK + "This allows tau to load .py settings and resources," + RESET
        )
        lines.append(
            indent
            + BRIGHT_BLACK
            + "install missing project packages, and run project extensions."
            + RESET
        )
        lines.append("")
        lines.append("")

        for i, opt in enumerate(self._options):
            is_sel = i == self._selected
            prefix = "› " if is_sel else "  "
            label = opt.label
            row = indent + prefix + label
            row = BOLD + BRIGHT_WHITE + row + RESET if is_sel else BRIGHT_BLACK + row + RESET
            lines.append(row)

        lines.append("")
        lines.append("")

        lines.append(indent + BRIGHT_BLACK + "↑↓ navigate  ·  Enter select  ·  Esc cancel" + RESET)

        return lines

    def handle_input(self, event: InputEvent) -> bool:
        if not isinstance(event, KeyEvent):
            return False

        if event.key == "up":
            self._selected = (self._selected - 1) % len(self._options)
            return True

        if event.key == "down":
            self._selected = (self._selected + 1) % len(self._options)
            return True

        if event.key in ("enter", "return"):
            self._on_commit(self._options[self._selected])
            return True

        if event.key == "escape":
            self._on_commit(None)
            return True

        return False

    def invalidate(self) -> None:
        pass
