# Public API — import from here instead of individual submodules.
#
#   Theme types:   from tau.tui import LayoutTheme, SpinnerTheme, MessageTheme
#   Keybindings:   from tau.tui import configure_keybindings, get_keybindings
#   Components:    from tau.tui import SelectList, SelectItem, Box
#
#   Themes:        from tau.themes.registry import theme_registry

from tau.tui.theme import (
    ColorFn,
    LayoutTheme,
    SpinnerTheme,
    MarkdownTheme,
    MessageTheme,
    InputTheme,
    SelectListTheme,
    color,
    rgb,
    rgb_bold,
    rgb_italic,
)
from tau.tui.keybindings import (
    KeyMap,
    KeybindingsManager,
    get_keybindings,
    configure_keybindings,
)
from tau.tui.components.select_list import SelectList, SelectItem
from tau.tui.components.box import Box

__all__ = [
    # Theme types
    "ColorFn",
    "LayoutTheme",
    "SpinnerTheme",
    "MarkdownTheme",
    "MessageTheme",
    "InputTheme",
    "SelectListTheme",
    # Keybindings
    "KeyMap",
    "KeybindingsManager",
    "get_keybindings",
    "configure_keybindings",
    # Color-function builders
    "color",
    "rgb",
    "rgb_bold",
    "rgb_italic",
    # Components
    "SelectList",
    "SelectItem",
    "Box",
]
