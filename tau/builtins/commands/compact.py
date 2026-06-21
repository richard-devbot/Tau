from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.commands.registry import CommandRegistry


async def cmd_compact(reg: CommandRegistry, args: list[str]) -> None:
    """Manually compact the current session context."""
    if reg.runtime is None or reg.runtime.agent is None:
        return

    sm = reg.runtime.settings_manager
    if sm is not None and not sm.is_compaction_enabled():
        from tau.extensions.context import ExtensionContext

        ctx = ExtensionContext.from_runtime(reg.runtime)
        if ctx.ui is not None:
            ctx.ui.notify("Compaction is disabled. Enable it in /settings → Compaction.")
        return

    custom_instructions = " ".join(args).strip() or None
    did_compact = await reg.runtime.agent.compact(custom_instructions=custom_instructions)
    if not did_compact:
        from tau.extensions.context import ExtensionContext

        ctx = ExtensionContext.from_runtime(reg.runtime)
        if ctx.ui is not None:
            ctx.ui.notify("Nothing to compact — conversation is too short to summarize.")
