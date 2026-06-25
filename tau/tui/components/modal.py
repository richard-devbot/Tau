from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.tui.theme import LayoutTheme


class ListModal:
    """Generic list selector modal.

    Renders:
      title
      subtitle (optional)
      ─────────────────────
      → item-name ✓
        item-name
      ─────────────────────
      ↑/↓: move  enter: select  esc: cancel

    ``on_preview`` fires on every cursor move (used for live theme preview).
    ``current`` marks which item has the ✓ checkmark.
    """

    HELP = "  ↑/↓: move  enter: select  esc: cancel"

    def __init__(
        self,
        items: list[str],
        current: str,
        title: str,
        subtitle: str = "",
        on_preview: Callable[[str], None] | None = None,
        theme: LayoutTheme | None = None,
    ) -> None:
        self._items = list(items)
        self._current = current
        self._title = title
        self._subtitle = subtitle
        self._preview = on_preview
        self._selected = 0

        if theme is None:
            from tau.tui.theme import LayoutTheme as _LT

            theme = _LT()
        self._theme = theme

        # Start cursor on the current item
        for i, it in enumerate(self._items):
            if it == current:
                self._selected = i
                break

    # ── Navigation ────────────────────────────────────────────────────────────

    def move_up(self) -> None:
        if self._items:
            self._selected = (self._selected - 1) % len(self._items)
            if self._preview:
                self._preview(self._items[self._selected])

    def move_down(self) -> None:
        if self._items:
            self._selected = (self._selected + 1) % len(self._items)
            if self._preview:
                self._preview(self._items[self._selected])

    def selected_value(self) -> str | None:
        if not self._items:
            return None
        return self._items[self._selected]

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, width: int) -> list[str]:
        t = self._theme
        divider = t.border("─" * width)
        lines: list[str] = []

        # Title block
        lines.append("  " + t.emphasis(self._title))
        if self._subtitle:
            lines.append("  " + t.muted(self._subtitle))

        lines.append(divider)

        # List
        if not self._items:
            lines.append("  " + t.muted("(no items)"))
        else:
            for i, item in enumerate(self._items):
                is_sel = i == self._selected
                is_current = item == self._current
                check = f" {t.success('✓')}" if is_current else ""
                if is_sel:
                    lines.append(f"  {t.emphasis(f'→ {item}')}{check}")
                else:
                    lines.append(f"    {item}{check}")

        lines.append(divider)

        # Help
        lines.append("  " + t.muted(self.HELP.strip()))

        return lines
