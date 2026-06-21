from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.commands.registry import CommandRegistry


async def cmd_clear(reg: CommandRegistry, _args: list[str]) -> None:
    """Clear the message list."""
    if reg.runtime is None:
        return
    from tau.extensions.context import ExtensionContext

    ctx = ExtensionContext.from_runtime(reg.runtime)
    if ctx.ui is not None:
        ctx.ui.clear_messages()
