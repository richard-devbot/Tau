from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TuiReadyEvent:
    """Fired once by the TUI after hooks are subscribed and the layout is fully set up.

    This is the earliest point at which extension handlers can safely access
    ``ctx.ui`` — earlier events (e.g. ``session_start`` with reason ``Startup``)
    fire before the layout exists.
    """

    type: Literal["tui_ready"] = field(default="tui_ready", init=False)


@dataclass
class TuiStartEvent:
    """Fired immediately before the TUI event loop begins (after tui_ready).

    Use for any setup that should run once the layout is ready but before
    the user can interact — e.g. restoring UI state, showing a welcome message.
    """

    type: Literal["tui_start"] = field(default="tui_start", init=False)


@dataclass
class TuiExitEvent:
    """Fired in the finally block when the TUI is shutting down.

    Guaranteed to fire even if the loop exits due to an error.
    Use for cleanup that needs ctx.ui (session_shutdown fires later without UI).
    """

    type: Literal["tui_exit"] = field(default="tui_exit", init=False)


@dataclass
class ModelSelectEvent:
    """Fired when the active model changes, either by user command or automatic cycling."""

    type: Literal["model_select"] = field(default="model_select", init=False)
    model: Any = None
    previous_model: Any | None = None
    source: Literal["set", "cycle", "restore"] = "set"


@dataclass
class ThinkingLevelSelectEvent:
    """Fired when the extended-thinking budget level changes."""

    type: Literal["thinking_level_select"] = field(default="thinking_level_select", init=False)
    level: Any = None
    previous_level: Any = None


@dataclass
class QueueUpdateEvent:
    """Fired when a follow-up or steering message enters the queue."""

    type: Literal["queue_update"] = field(default="queue_update", init=False)
    queue: Literal["steering", "followup"] = "steering"
    message: Any = None
    messages: list[Any] = field(default_factory=list)
