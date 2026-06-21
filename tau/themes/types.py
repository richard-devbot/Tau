from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.tui.theme import LayoutTheme


@dataclass
class ThemeLoadError:
    path: str
    error: str


@dataclass
class LoadThemesResult:
    themes: dict[str, LayoutTheme] = field(default_factory=dict)
    errors: list[ThemeLoadError] = field(default_factory=list)
