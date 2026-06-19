from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tau.tui.component import Component
from tau.tui.theme import SpinnerTheme

if TYPE_CHECKING:
    from tau.tui.tui import TUI


class Spinner(Component):
    """
    Animated spinner with an optional label.

    Appearance is fully controlled by SpinnerTheme — pass a custom theme to
    change frames, speed, and colours without touching this file.

    Usage::

        spinner = Spinner(tui, label="Thinking…")
        spinner.start()
        await agent.invoke(...)
        spinner.stop()
    """

    def __init__(
        self,
        tui: TUI,
        label: str = "",
        theme: SpinnerTheme | None = None,
    ) -> None:
        self._tui   = tui
        self._label = label
        self._theme = theme or SpinnerTheme()
        self._frame = 0
        self._active = False
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

        # Extension overrides — None means "use theme default"
        self._force_hidden: bool = False
        self._custom_frames: list[str] | None = None
        self._custom_interval_ms: int | None = None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._active

    def set_label(self, label: str) -> None:
        self._label = label

    def set_theme(self, theme: SpinnerTheme) -> None:
        self._theme = theme

    def set_force_hidden(self, hidden: bool) -> None:
        self._force_hidden = hidden
        self._tui.request_render()

    def set_custom_indicator(
        self,
        frames: list[str] | None = None,
        interval_ms: int | None = None,
    ) -> None:
        self._custom_frames = frames
        self._custom_interval_ms = interval_ms

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._frame  = 0
        self._task   = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        self._active = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._frame = 0
        self._tui.request_render()

    # -------------------------------------------------------------------------
    # Component
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        if not self._active or self._force_hidden:
            return []
        t      = self._theme
        frames = self._custom_frames if self._custom_frames is not None else (t.frames or ["…"])
        char   = frames[self._frame % len(frames)]
        frame  = t.frame_color(char)
        label  = f" {t.label_color(self._label)}" if self._label else ""
        return [(frame + label)[:width]]

    # -------------------------------------------------------------------------
    # Animation loop
    # -------------------------------------------------------------------------

    async def _run(self) -> None:
        interval_ms = self._custom_interval_ms if self._custom_interval_ms is not None else self._theme.interval_ms
        interval = max(0.05, interval_ms / 1000)
        frames = self._custom_frames if self._custom_frames is not None else (self._theme.frames or ["…"])
        try:
            while self._active:
                await asyncio.sleep(interval)
                self._frame = (self._frame + 1) % max(1, len(frames))
                # Skip the render request if one is already pending — during
                # streaming the token handler already schedules 60fps renders,
                # so the spinner doesn't need to add redundant wakeups.
                if not self._tui._render_requested:
                    self._tui.request_render()
        except asyncio.CancelledError:
            pass
