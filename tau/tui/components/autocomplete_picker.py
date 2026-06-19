from __future__ import annotations

from typing import TYPE_CHECKING

from tau.tui.ansi import RESET, BOLD, BRIGHT_BLACK, BRIGHT_WHITE
from tau.tui.component import Component
from tau.tui.fuzzy import fuzzy_filter
from tau.tui.input import InputEvent, KeyEvent

if TYPE_CHECKING:
    from tau.tui.autocomplete import AutocompleteItem

_DEFAULT_VISIBLE_ROWS = 5


class AutocompletePicker(Component):
    """
    Fuzzy-filtered inline dropdown for extension autocomplete providers.

    Shown above the input (like the command palette) when an extension trigger
    character is detected in the editor text.  Navigation is handled here;
    commit (Tab/Enter) and dismiss (Escape) are handled by Layout.
    """

    def __init__(self, max_visible: int = _DEFAULT_VISIBLE_ROWS) -> None:
        self._all_items: list[AutocompleteItem] = []
        self._items: list[AutocompleteItem] = []
        self._selected: int = 0
        self._query: str = ""
        self._active: bool = False
        self._max_visible = max_visible

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._active and bool(self._items)

    @property
    def selected(self) -> AutocompleteItem | None:
        return self._items[self._selected] if self._items else None

    @property
    def line_count(self) -> int:
        return min(self._max_visible, len(self._items))

    def set_items(self, items: list[AutocompleteItem]) -> None:
        self._all_items = list(items)
        self._active = True
        self._apply_filter(self._query)

    def set_query(self, query: str) -> None:
        if query == self._query:
            return
        self._query = query
        self._apply_filter(query)

    def clear(self) -> None:
        self._all_items = []
        self._items = []
        self._selected = 0
        self._query = ""
        self._active = False

    def move_up(self) -> None:
        if self._items:
            self._selected = (self._selected - 1) % len(self._items)

    def move_down(self) -> None:
        if self._items:
            self._selected = (self._selected + 1) % len(self._items)

    # -------------------------------------------------------------------------
    # Component
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        if not self.active:
            return []

        count   = len(self._items)
        visible = min(self._max_visible, count)
        start   = max(0, min(self._selected - visible + 1, count - visible))

        label_w = max(8, min(
            max(len(item.label) for item in self._items[start : start + visible]),
            24,
        ))
        desc_w = max(0, width - label_w - 4)

        lines: list[str] = []

        if start > 0:
            lines.append(BRIGHT_BLACK + f"  ↑ {start} more" + RESET)

        for i in range(start, start + visible):
            item   = self._items[i]
            is_sel = i == self._selected
            label  = item.label[:label_w].ljust(label_w)
            desc   = item.description[:desc_w] if desc_w > 0 else ""

            if is_sel:
                row = "  " + BOLD + BRIGHT_WHITE + label + RESET + "  " + BRIGHT_BLACK + desc + RESET
            else:
                row = "  " + BRIGHT_BLACK + label + "  " + desc + RESET

            lines.append(row)

        remaining = count - (start + visible)
        if remaining > 0:
            lines.append(BRIGHT_BLACK + f"  ↓ {remaining} more" + RESET)

        return lines

    def handle_input(self, event: InputEvent) -> bool:
        if not isinstance(event, KeyEvent):
            return False
        key = str(event)
        if key in ("up", "ctrl+p"):
            self.move_up()
            return True
        if key in ("down", "ctrl+n"):
            self.move_down()
            return True
        return False

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _apply_filter(self, query: str) -> None:
        q = query.strip()
        if not q:
            self._items = list(self._all_items)
        else:
            self._items = fuzzy_filter(
                self._all_items,
                q,
                lambda item: item.label + " " + item.description,
            )
        self._selected = min(self._selected, len(self._items) - 1) if self._items else 0
