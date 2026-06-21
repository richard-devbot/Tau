from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class InlineSelector[T]:
    """
    Generic wrapper for an inline SelectList modal.

    Handles the open/nav/commit/cancel lifecycle that was previously
    duplicated for every selector in Layout (model, theme, effort, resume, tree).

    ``searchable=True`` enables typed filtering — Layout feeds keystrokes
    through ``append_search`` / ``backspace_search`` and the selector
    updates its query automatically.

    ``on_preview`` is called on every nav step (used by the theme picker
    for live preview before commit).
    """

    kind: str  # "model" | "theme" | "effort" | "resume" | "tree"
    selector: Any  # SelectList[T] — kept as Any to avoid circular import
    on_commit: Callable[[T], None]
    on_cancel: Callable[[], None]
    searchable: bool = False
    on_preview: Callable[[T], None] | None = None
    search: str = field(default="", init=False)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def nav(self, direction: int) -> None:
        self.selector.move_up() if direction < 0 else self.selector.move_down()
        if self.on_preview is not None:
            item = self.selector.selected_item
            if item is not None and item.value is not None:
                self.on_preview(item.value)

    def selected_value(self) -> T | None:
        item = self.selector.selected_item
        return item.value if item is not None else None

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def append_search(self, ch: str) -> None:
        self.search += ch
        self.selector.set_query(self.search)

    def backspace_search(self) -> None:
        self.search = self.search[:-1]
        self.selector.set_query(self.search)

    # -------------------------------------------------------------------------
    # Render
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        # Tree selector renders its own search line internally; skip for other searchable selectors
        if self.searchable and self.search and self.kind != "tree":
            from tau.tui.ansi import DIM, RESET

            lines.append(f"  {DIM}Search:{RESET} {self.search}█")
        lines.extend(self.selector.render(width))
        return lines
