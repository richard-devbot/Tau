from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from tau.runtime.service import Runtime
    from tau.tui.components.layout import Layout
    from tau.tui.tui import TUI


@dataclass
class CommandContext:
    """Minimal context injected into every TUI command handler.

    This is the single seam between App (orchestrator) and the command
    modules (feature logic). Commands receive this instead of holding a
    reference to the full App, so they can be called from keyboard
    shortcuts, extension APIs, or tests without instantiating App.
    """
    runtime: "Runtime"
    layout: "Layout"
    tui: "TUI"
    on_palette_refresh: Callable[[], None] | None = field(default=None)

    def notify(self, text: str) -> None:
        """Post a system status note to the chat stream."""
        from tau.message.types import CustomMessage, LinesContent
        lines = text.splitlines() + [""]
        contents = [LinesContent(lines=lines)]
        msg = CustomMessage(
            custom_type="system",
            timestamp=time.time(),
            contents=contents,
        )
        self.layout.add_message(msg)
        self.tui.request_render()
