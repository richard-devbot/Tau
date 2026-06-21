from __future__ import annotations

from collections.abc import Callable

from tau.tui.input import InputEvent, KeyEvent


class TextPrompt:
    """
    Inline single-line text prompt shown below the editor.

    Previously lived as 5 raw state vars + open/close/handle_input/render
    spread across Layout.  Layout now holds one instance and delegates:

        prompt.open(label, on_commit, on_cancel, secret=False)
        prompt.handle_input(event) -> bool   # True = consumed (modal)
        prompt.render(width) -> list[str]
        prompt.active                        # True while visible
    """

    def __init__(self) -> None:
        self._label: str = ""
        self._value: str = ""
        self._secret: bool = False
        self._on_commit: Callable[[str], None] | None = None
        self._on_cancel: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return self._on_commit is not None

    def open(
        self,
        label: str,
        on_commit: Callable[[str], None],
        on_cancel: Callable[[], None],
        *,
        secret: bool = False,
    ) -> None:
        self._label = label
        self._value = ""
        self._secret = secret
        self._on_commit = on_commit
        self._on_cancel = on_cancel

    def handle_input(self, event: InputEvent) -> bool:
        """Handle a key event. Always returns True — prompt is modal."""
        if not self.active:
            return False
        if not isinstance(event, KeyEvent):
            return True
        match event.key:
            case "enter":
                cb, val = self._on_commit, self._value
                self._close()
                if cb is not None:
                    cb(val)
            case "escape":
                cb = self._on_cancel
                self._close()
                if cb is not None:
                    cb()
            case "backspace":
                self._value = self._value[:-1]
            case ch if len(ch) == 1 and ch.isprintable():
                self._value += ch
        return True

    def render(self, width: int) -> list[str]:  # noqa: ARG002
        from tau.tui.ansi import BOLD, DIM, RESET

        display = ("*" * len(self._value)) if self._secret else self._value
        return [
            f"  {BOLD}{self._label}{RESET}  {DIM}(Enter to confirm · Esc to cancel){RESET}",
            f"  {display}█",
        ]

    def _close(self) -> None:
        self._label = ""
        self._value = ""
        self._secret = False
        self._on_commit = None
        self._on_cancel = None
