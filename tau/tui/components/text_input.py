from __future__ import annotations

import re
import unicodedata as _ud
from typing import Callable

from tau.tui.ansi import CURSOR_MARKER, visible_width, RESET, DIM, BOLD
from tau.tui.component import Component
from tau.tui.input import InputEvent, KeyEvent, PasteEvent

# Matches any atomic input token at end-of-string (for backspace) or start-of-string (for delete-forward).
# Session-scoped (#N) and persistent (:{uuid}) variants for image/audio/video, plus paste markers.
_ATOMIC_TOKEN_END = re.compile(
    r"(?:"
    r"\[image #\d+\]|\[image:[^\]]+\]"
    r"|\[audio #\d+\]|\[audio:[^\]]+\]"
    r"|\[video #\d+\]|\[video:[^\]]+\]"
    r"|\[paste #\d+(?: \+\d+ lines| \d+ chars)\]"
    r")$"
)
_ATOMIC_TOKEN_START = re.compile(
    r"\[image #\d+\]|\[image:[^\]]+\]"
    r"|\[audio #\d+\]|\[audio:[^\]]+\]"
    r"|\[video #\d+\]|\[video:[^\]]+\]"
    r"|\[paste #\d+(?: \+\d+ lines| \d+ chars)\]"
)


class TextInput(Component):
    """
    Multiline-capable text input with cursor, history navigation, and common
    readline-style editing shortcuts.

    Keybindings
    ───────────
    Left / Right          Move cursor
    Home / ctrl+a         Move to line start
    End  / ctrl+e         Move to line end
    Backspace             Delete before cursor
    Delete / ctrl+d       Delete at cursor
    ctrl+k                Kill from cursor to end
    ctrl+u                Kill from start to cursor
    ctrl+w                Delete previous word
    Up / Down             Navigate history
    Enter                 Submit / steer mid-task when agent is busy
    alt+Enter             Queue as follow-up (fires on_followup)
    alt+Up                Dequeue queued messages (fires on_dequeue)
    \\ + Enter            Insert newline (multiline input)
    """

    def __init__(
        self,
        prefix: str = "> ",
        placeholder: str = "",
        on_submit: Callable[[str], None] | None = None,
        on_followup: Callable[[str], None] | None = None,
        on_dequeue: Callable[[], None] | None = None,
        on_paste: Callable[[], None] | None = None,
        on_paste_text: Callable[[str], None] | None = None,
        on_history_transform: Callable[[str], str] | None = None,
        padding_x: int = 0,
    ) -> None:
        self._prefix = prefix
        self._placeholder = placeholder
        self._on_submit = on_submit
        self._on_followup = on_followup
        self._on_dequeue = on_dequeue
        self.on_paste = on_paste
        self.on_paste_text = on_paste_text
        self.on_history_transform = on_history_transform
        self._padding_x = max(0, padding_x)

        self._text = ""
        self._cursor = 0
        self._line_scrolls: dict[int, int] = {}
        self._arg_hint: str = ""

        self._history: list[str] = []
        self._history_idx = -1
        self._history_draft = ""

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def text(self) -> str:
        return self._text

    @property
    def line_count(self) -> int:
        return self._text.count("\n") + 1

    def clear(self) -> None:
        self._text = ""
        self._cursor = 0
        self._line_scrolls = {}
        self._arg_hint = ""

    def set_text(self, text: str) -> None:
        self._text = text
        self._cursor = len(text)
        self._line_scrolls = {}

    def insert_at_cursor(self, text: str) -> None:
        self._insert(text)

    def focus(self) -> None:
        pass

    # -------------------------------------------------------------------------
    # Component
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        prefix_w = visible_width(self._prefix)
        padding = " " * self._padding_x
        available = max(1, width - prefix_w - self._padding_x * 2)
        indent = " " * prefix_w

        if not self._text:
            cursor_block = CURSOR_MARKER + "\x1b[7m \x1b[27m"
            placeholder = self._placeholder[:available] if self._placeholder else ""
            return [BOLD + self._prefix + padding + RESET + cursor_block + DIM + placeholder + padding + RESET]

        text_lines = self._text.split("\n")
        cursor_line_idx, cursor_col = self._cursor_line_col()
        result = []

        last_line_idx = len(text_lines) - 1
        for i, line_text in enumerate(text_lines):
            prefix = self._prefix if i == 0 else indent
            scroll = self._line_scrolls.get(i, 0)
            col_in_line = cursor_col if i == cursor_line_idx else -1
            rendered, scroll = _render_line(line_text, col_in_line, available, scroll)
            self._line_scrolls[i] = scroll
            if self._arg_hint and i == last_line_idx and i == cursor_line_idx and cursor_col == len(line_text):
                rendered += DIM + self._arg_hint + RESET
            result.append(BOLD + prefix + padding + RESET + rendered + padding)

        return result

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, PasteEvent):
            text = event.text.replace("\r", "")
            if self.on_paste_text:
                self.on_paste_text(text)
            else:
                self._insert(text)
            return True

        if not isinstance(event, KeyEvent):
            return False

        key = str(event)

        match key:
            case "enter":
                if self._text.endswith("\\"):
                    # Replace trailing backslash with a real newline
                    self._text = self._text[:-1] + "\n"
                    self._cursor = len(self._text)
                    self._line_scrolls = {}
                else:
                    self._submit()
            case "alt+enter":
                self._submit_followup()
            case "alt+up":
                if self._on_dequeue:
                    self._on_dequeue()
            case "ctrl+v":
                if self.on_paste:
                    self.on_paste()
                    return True
            case "backspace":
                self._backspace()
            case "delete" | "ctrl+d":
                self._delete_forward()
            case "left":
                self._move_left()
            case "right":
                self._move_right()
            case "home" | "ctrl+a":
                self._cursor = self._line_start()
            case "end" | "ctrl+e":
                self._cursor = self._line_end()
            case "ctrl+k":
                self._text = self._text[: self._cursor]
            case "ctrl+u":
                self._text = self._text[self._cursor :]
                self._cursor = 0
            case "ctrl+w":
                self._delete_word_back()
            case "up":
                self._history_prev()
            case "down":
                self._history_next()
            case _:
                if event.char and not event.ctrl and not event.alt:
                    self._insert(event.char)
                else:
                    return False

        return True

    # -------------------------------------------------------------------------
    # Cursor helpers
    # -------------------------------------------------------------------------

    def _cursor_line_col(self) -> tuple[int, int]:
        before = self._text[: self._cursor]
        line_idx = before.count("\n")
        last_nl = before.rfind("\n")
        return line_idx, self._cursor - (last_nl + 1)

    def _line_start(self) -> int:
        before = self._text[: self._cursor]
        return before.rfind("\n") + 1

    def _line_end(self) -> int:
        after = self._text[self._cursor :]
        nl = after.find("\n")
        return self._cursor + (nl if nl != -1 else len(after))

    # -------------------------------------------------------------------------
    # Editing
    # -------------------------------------------------------------------------

    def _insert(self, text: str) -> None:
        # Editing the buffer commits out of history/message-tree browsing, so the
        # '@' file picker and '/' command palette (both gated on _history_idx == -1)
        # work again instead of staying suppressed until the next submit.
        self._history_idx = -1
        self._text = self._text[: self._cursor] + text + self._text[self._cursor :]
        self._cursor += len(text)

    def _backspace(self) -> None:
        if self._cursor > 0:
            before = self._text[: self._cursor]
            m = re.search(_ATOMIC_TOKEN_END, before)
            if m:
                start = m.start()
                self._text = self._text[:start] + self._text[self._cursor :]
                self._cursor = start
            else:
                self._text = self._text[: self._cursor - 1] + self._text[self._cursor :]
                self._cursor -= 1
            self._line_scrolls = {}

    def _delete_forward(self) -> None:
        if self._cursor < len(self._text):
            after = self._text[self._cursor :]
            m = re.match(_ATOMIC_TOKEN_START, after)
            if m:
                self._text = self._text[: self._cursor] + after[m.end() :]
            else:
                self._text = self._text[: self._cursor] + self._text[self._cursor + 1 :]
            self._line_scrolls = {}

    def _move_left(self) -> None:
        if self._cursor > 0:
            before = self._text[: self._cursor]
            m = re.search(_ATOMIC_TOKEN_END, before)
            if m:
                self._cursor = m.start()
            else:
                self._cursor -= 1

    def _move_right(self) -> None:
        if self._cursor < len(self._text):
            after = self._text[self._cursor :]
            m = re.match(_ATOMIC_TOKEN_START, after)
            if m:
                self._cursor += m.end()
            else:
                self._cursor += 1

    def _delete_word_back(self) -> None:
        i = self._cursor
        # Skip trailing whitespace
        while i > 0 and self._text[i - 1] in (" ", "\n"):
            i -= 1
        # Treat an atomic marker immediately before the cursor as a whole word
        before = self._text[:i]
        m = re.search(_ATOMIC_TOKEN_END, before)
        if m:
            i = m.start()
        else:
            while i > 0 and self._text[i - 1] not in (" ", "\n"):
                i -= 1
        self._text = self._text[:i] + self._text[self._cursor :]
        self._cursor = i
        self._line_scrolls = {}

    # -------------------------------------------------------------------------
    # Submit / history
    # -------------------------------------------------------------------------

    def _submit(self) -> None:
        text = self._text.strip()
        if not text:
            return
        history_text = self.on_history_transform(text) if self.on_history_transform else text
        if history_text and (not self._history or self._history[-1] != history_text):
            self._history.append(history_text)
        self._history_idx = -1
        self._history_draft = ""
        self.clear()
        if self._on_submit:
            self._on_submit(text)

    def _submit_followup(self) -> None:
        text = self._text.strip()
        if not text:
            return
        history_text = self.on_history_transform(text) if self.on_history_transform else text
        if history_text and (not self._history or self._history[-1] != history_text):
            self._history.append(history_text)
        self._history_idx = -1
        self._history_draft = ""
        self.clear()
        if self._on_followup:
            self._on_followup(text)
        elif self._on_submit:
            # If no followup handler registered, fall back to normal submit
            self._on_submit(text)

    def _history_prev(self) -> None:
        if not self._history:
            return
        if self._history_idx == -1:
            self._history_draft = self._text
            self._history_idx = len(self._history) - 1
        elif self._history_idx > 0:
            self._history_idx -= 1
        self.set_text(self._history[self._history_idx])

    def _history_next(self) -> None:
        if self._history_idx == -1:
            return
        self._history_idx += 1
        if self._history_idx >= len(self._history):
            self._history_idx = -1
            self.set_text(self._history_draft)
        else:
            self.set_text(self._history[self._history_idx])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _char_width(ch: str) -> int:
    cp = ord(ch)
    if cp == 0 or (0x007F <= cp <= 0x009F):
        return 0
    if _ud.east_asian_width(ch) in ("W", "F"):
        return 2
    if _ud.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    return 1


def _render_line(text: str, cursor_col: int, available: int, scroll: int) -> tuple[str, int]:
    """
    Render one logical line. cursor_col=-1 means no cursor on this line.
    Returns (rendered_string, updated_scroll).
    """
    cursor_vis = visible_width(text[:cursor_col]) if cursor_col >= 0 else -1

    if cursor_col >= 0:
        if cursor_vis < scroll:
            scroll = cursor_vis
        elif cursor_vis >= scroll + available:
            scroll = cursor_vis - available + 1

    result = ""
    col = 0
    vis = 0
    i = 0

    while i < len(text) and col < available:
        ch = text[i]
        w = _char_width(ch)
        if vis >= scroll:
            if cursor_col >= 0 and vis == cursor_vis:
                # CURSOR_MARKER tells the Renderer to move the hardware cursor here
                result += CURSOR_MARKER + "\x1b[7m" + ch + "\x1b[27m"
            else:
                result += ch
            col += w
        vis += w
        i += 1

    if cursor_col >= 0 and cursor_col == len(text) and cursor_vis >= scroll and col < available:
        result += CURSOR_MARKER + "\x1b[7m \x1b[27m"

    return result, scroll
