from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tau.tui.ansi import BOLD, DIM, RESET, pad, visible_width
from tau.tui.component import Component
from tau.tui.components.select_list import SelectItem, SelectList
from tau.tui.input import InputEvent, KeyEvent

T = TypeVar("T")

# ── Box drawing helper ────────────────────────────────────────────────────────


def _box(inner_lines: list[str], title: str, width: int) -> list[str]:
    """Wrap inner_lines in a Unicode border box of the given width."""
    inner_w = max(1, width - 4)  # "│ " + content + " │"

    if title:
        t = f" {title} "
        tv = visible_width(t)
        dashes = max(0, width - 2 - tv)
        left_d = dashes // 2
        right_d = dashes - left_d
        top = "╭" + "─" * left_d + BOLD + t + RESET + "─" * right_d + "╮"
    else:
        top = "╭" + "─" * (width - 2) + "╮"

    lines = [top]
    for line in inner_lines:
        lines.append("│ " + pad(line, inner_w) + " │")
    lines.append("╰" + "─" * (width - 2) + "╯")
    return lines


# ── PickerOverlay ─────────────────────────────────────────────────────────────


class PickerOverlay[T](Component):
    """A floating modal picker: box border + optional search bar + SelectList.

    Usage::

        handle_ref = []

        def on_commit(value):
            handle_ref[0].close()
            do_something(value)

        def on_cancel():
            handle_ref[0].close()

        picker = PickerOverlay(items, title="Select model", searchable=True,
                               on_commit=on_commit, on_cancel=on_cancel)
        handle = tui.show_overlay(picker, OverlayOptions(width="70%"))
        handle_ref.append(handle)
    """

    def __init__(
        self,
        items: list[SelectItem[T]],
        title: str = "",
        on_commit: Callable[[T | None], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        on_preview: Callable[[T | None], None] | None = None,
        searchable: bool = False,
        max_visible: int = 8,
        initial_index: int = 0,
    ) -> None:
        self._selector: SelectList[T] = SelectList(items, max_visible=max_visible)
        if items:
            self._selector._selected = min(initial_index, len(items) - 1)
        self._title = title
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._on_preview = on_preview
        self._searchable = searchable
        self._query = ""

    # ── Component ─────────────────────────────────────────────────────────────

    def render(self, width: int) -> list[str]:
        inner_w = max(1, width - 4)
        inner: list[str] = []
        if self._searchable:
            inner.append(f"  {DIM}Search:{RESET} {self._query}█")
        inner.extend(self._selector.render(inner_w))
        inner.append(f"  {DIM}↑↓ navigate · Enter select · Esc cancel{RESET}")
        return _box(inner, self._title, width)

    def handle_input(self, event: InputEvent) -> bool:
        if not isinstance(event, KeyEvent):
            return False

        match event.key:
            case "up":
                self._selector.move_up()
                self._fire_preview()
            case "down":
                self._selector.move_down()
                self._fire_preview()
            case "enter" | "tab":
                item = self._selector.selected_item
                if self._on_commit is not None:
                    self._on_commit(item.value if item is not None else None)
            case "escape":
                if self._on_cancel is not None:
                    self._on_cancel()
            case "backspace" if self._searchable:
                self._query = self._query[:-1]
                self._selector.set_query(self._query)
            case ch if self._searchable and len(ch) == 1 and ch.isprintable():
                self._query += ch
                self._selector.set_query(self._query)
            case _:
                return False

        return True

    def invalidate(self) -> None:
        self._selector.invalidate()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fire_preview(self) -> None:
        if self._on_preview is not None:
            item = self._selector.selected_item
            self._on_preview(item.value if item is not None else None)


# ── TextOverlay ───────────────────────────────────────────────────────────────


class TextOverlay(Component):
    """A floating read-only text display.

    Press Esc to close (calls on_close). Lines can be appended live via
    append_line() — useful for streaming status messages (e.g. OAuth flow).

    Pass non_capturing=True in OverlayOptions if this should not steal focus.
    """

    def __init__(
        self,
        lines: list[str],
        title: str = "",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._lines = list(lines)
        self._title = title
        self._on_close = on_close

    # ── Public ────────────────────────────────────────────────────────────────

    def append_line(self, line: str) -> None:
        self._lines.append(line)

    def set_lines(self, lines: list[str]) -> None:
        self._lines = list(lines)

    # ── Component ─────────────────────────────────────────────────────────────

    def render(self, width: int) -> list[str]:
        inner: list[str] = list(self._lines)
        if self._on_close is not None:
            inner.append(f"  {DIM}Esc to close{RESET}")
        return _box(inner, self._title, width)

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyEvent) and event.key == "escape":
            if self._on_close is not None:
                self._on_close()
            return True
        return True  # swallow all input while open (modal)

    def invalidate(self) -> None:
        pass
