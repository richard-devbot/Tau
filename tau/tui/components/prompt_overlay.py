from __future__ import annotations

from typing import Callable

from tau.tui.ansi import BOLD, DIM, RESET, pad, visible_width
from tau.tui.component import Component
from tau.tui.input import InputEvent, KeyEvent


def _box(inner_lines: list[str], title: str, width: int) -> list[str]:
    inner_w = max(1, width - 4)
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


class PromptOverlay(Component):
    """A floating single-line text input overlay.

    Usage::

        handle_ref = []

        def on_commit(value):
            handle_ref[0].close()
            save_key(value)

        def on_cancel():
            handle_ref[0].close()

        prompt = PromptOverlay("Enter API key", on_commit=on_commit,
                               on_cancel=on_cancel, secret=True)
        handle = tui.show_overlay(prompt, OverlayOptions(width="50%"))
        handle_ref.append(handle)
    """

    def __init__(
        self,
        label: str,
        on_commit: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        secret: bool = False,
    ) -> None:
        self._label = label
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._secret = secret
        self._value = ""

    # ── Component ─────────────────────────────────────────────────────────────

    def render(self, width: int) -> list[str]:
        display = "*" * len(self._value) if self._secret else self._value
        inner = [
            f"  {BOLD}{self._label}{RESET}",
            f"  {DIM}Enter to confirm · Esc to cancel{RESET}",
            f"  {display}█",
        ]
        return _box(inner, "", width)

    def handle_input(self, event: InputEvent) -> bool:
        if not isinstance(event, KeyEvent):
            return False

        match event.key:
            case "enter":
                val = self._value
                if self._on_commit is not None:
                    self._on_commit(val)
            case "escape":
                if self._on_cancel is not None:
                    self._on_cancel()
            case "backspace":
                self._value = self._value[:-1]
            case ch if len(ch) == 1 and ch.isprintable():
                self._value += ch
            case _:
                return False

        return True

    def invalidate(self) -> None:
        pass


class EditorOverlay(Component):
    """A floating multi-line text editor overlay.

    ``Ctrl+S`` or ``Ctrl+Enter`` saves; ``Escape`` cancels.
    Arrow keys and Backspace work normally; Enter inserts a newline.
    """

    VISIBLE_ROWS = 12

    def __init__(
        self,
        title: str,
        prefill: str = "",
        on_commit: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        self._title = title
        self._lines: list[str] = prefill.splitlines() or [""]
        self._cursor_row = len(self._lines) - 1
        self._cursor_col = len(self._lines[-1])
        self._scroll_top = 0
        self._on_commit = on_commit
        self._on_cancel = on_cancel

    # ── Cursor helpers ────────────────────────────────────────────────────────

    def _current_line(self) -> str:
        return self._lines[self._cursor_row]

    def _clamp_scroll(self) -> None:
        if self._cursor_row < self._scroll_top:
            self._scroll_top = self._cursor_row
        elif self._cursor_row >= self._scroll_top + self.VISIBLE_ROWS:
            self._scroll_top = self._cursor_row - self.VISIBLE_ROWS + 1

    # ── Component ─────────────────────────────────────────────────────────────

    def render(self, width: int) -> list[str]:
        inner_w = max(1, width - 4)
        self._clamp_scroll()

        visible = self._lines[self._scroll_top: self._scroll_top + self.VISIBLE_ROWS]
        rows: list[str] = []
        for ri, line in enumerate(visible):
            abs_row = self._scroll_top + ri
            if abs_row == self._cursor_row:
                before = line[: self._cursor_col]
                after = line[self._cursor_col:]
                content = before + "█" + after
            else:
                content = line
            rows.append("│ " + pad(content[:inner_w], inner_w) + " │")

        # scroll indicator
        total = len(self._lines)
        if total > self.VISIBLE_ROWS:
            pct = int(self._scroll_top / max(1, total - self.VISIBLE_ROWS) * 100)
            rows.append("│" + DIM + f" ↕ {pct}%".rjust(width - 2) + RESET + "│")
        else:
            rows.append("│" + " " * (width - 2) + "│")

        hint = f"  {DIM}Ctrl+S to save · Esc to cancel{RESET}"
        rows.append("│ " + pad(hint, inner_w) + " │")

        return _box(rows, self._title, width)

    def handle_input(self, event: InputEvent) -> bool:
        if not isinstance(event, KeyEvent):
            return False

        k = event.key
        if k in ("ctrl+s", "ctrl+enter"):
            text = "\n".join(self._lines)
            if self._on_commit is not None:
                self._on_commit(text)
            return True
        if k == "escape":
            if self._on_cancel is not None:
                self._on_cancel()
            return True
        if k == "enter":
            line = self._lines[self._cursor_row]
            before, after = line[: self._cursor_col], line[self._cursor_col:]
            self._lines[self._cursor_row] = before
            self._lines.insert(self._cursor_row + 1, after)
            self._cursor_row += 1
            self._cursor_col = 0
            return True
        if k == "backspace":
            if self._cursor_col > 0:
                line = self._lines[self._cursor_row]
                self._lines[self._cursor_row] = line[: self._cursor_col - 1] + line[self._cursor_col:]
                self._cursor_col -= 1
            elif self._cursor_row > 0:
                prev = self._lines[self._cursor_row - 1]
                merged = prev + self._lines.pop(self._cursor_row)
                self._cursor_row -= 1
                self._cursor_col = len(prev)
                self._lines[self._cursor_row] = merged
            return True
        if k == "up":
            if self._cursor_row > 0:
                self._cursor_row -= 1
                self._cursor_col = min(self._cursor_col, len(self._current_line()))
            return True
        if k == "down":
            if self._cursor_row < len(self._lines) - 1:
                self._cursor_row += 1
                self._cursor_col = min(self._cursor_col, len(self._current_line()))
            return True
        if k == "left":
            if self._cursor_col > 0:
                self._cursor_col -= 1
            elif self._cursor_row > 0:
                self._cursor_row -= 1
                self._cursor_col = len(self._current_line())
            return True
        if k == "right":
            line = self._current_line()
            if self._cursor_col < len(line):
                self._cursor_col += 1
            elif self._cursor_row < len(self._lines) - 1:
                self._cursor_row += 1
                self._cursor_col = 0
            return True
        if k == "home":
            self._cursor_col = 0
            return True
        if k == "end":
            self._cursor_col = len(self._current_line())
            return True
        if len(k) == 1 and k.isprintable():
            line = self._lines[self._cursor_row]
            self._lines[self._cursor_row] = line[: self._cursor_col] + k + line[self._cursor_col:]
            self._cursor_col += 1
            return True
        return False

    def invalidate(self) -> None:
        pass
