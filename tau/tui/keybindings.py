from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.tui.input import KeyEvent

# Named action → list of key combo strings that trigger it
KeyMap = dict[str, list[str]]

_DEFAULTS: KeyMap = {
    # Selection / list navigation
    "tui.select.up": ["up", "ctrl+p"],
    "tui.select.down": ["down", "ctrl+n"],
    "tui.select.page_up": ["page_up"],
    "tui.select.page_down": ["page_down"],
    "tui.select.top": ["home"],
    "tui.select.bottom": ["end"],
    "tui.select.confirm": ["enter", "tab"],
    "tui.select.dismiss": ["escape"],
    # Text input
    "tui.input.submit": ["enter"],
    "tui.input.newline": ["shift+enter"],
    "tui.input.clear": ["ctrl+u"],
    "tui.input.word_back": ["ctrl+w"],
    # Message queuing
    "app.message.followup": ["alt+enter"],  # queue as follow-up (waits for agent to finish)
    "app.message.dequeue": ["alt+up"],  # restore queued messages into editor
    # App-level
    "tui.app.quit": ["ctrl+c", "ctrl+d"],
    "tui.app.abort": ["ctrl+c"],
    # Scroll (message list)
    "tui.scroll.up": ["page_up"],
    "tui.scroll.down": ["page_down"],
    "tui.scroll.top": ["home"],
    "tui.scroll.bottom": ["end"],
}


class KeybindingsManager:
    """
    Central registry mapping named actions to key combo strings.
    User overrides are merged on top of defaults at construction time.
    """

    def __init__(self, overrides: KeyMap | None = None) -> None:
        self._map: KeyMap = {k: list(v) for k, v in _DEFAULTS.items()}
        if overrides:
            for action, keys in overrides.items():
                self._map[action] = list(keys)

    def matches(self, event: KeyEvent, action: str) -> bool:
        """Return True if `event` triggers the named action.

        Uses KeyEvent.matches so user-supplied combos are modifier-order- and
        alias-independent ('shift+ctrl+x' == 'ctrl+shift+x' == 'control+shift+x').
        """
        combos = self._map.get(action, [])
        return event.matches(*combos)

    def keys_for(self, action: str) -> list[str]:
        """Return the key combo strings registered for `action`."""
        return list(self._map.get(action, []))

    def bind(self, action: str, keys: list[str]) -> None:
        """Replace all bindings for an action."""
        self._map[action] = list(keys)

    def add_binding(self, action: str, key: str) -> None:
        """Append an extra key combo for an action without removing existing ones."""
        self._map.setdefault(action, [])
        if key not in self._map[action]:
            self._map[action].append(key)


_instance: KeybindingsManager | None = None


def get_keybindings() -> KeybindingsManager:
    """Return the global KeybindingsManager singleton (created lazily)."""
    global _instance
    if _instance is None:
        _instance = KeybindingsManager()
    return _instance


def configure_keybindings(overrides: KeyMap) -> None:
    """Apply user overrides to the global singleton (call once at startup)."""
    global _instance
    _instance = KeybindingsManager(overrides)
