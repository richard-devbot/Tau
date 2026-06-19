from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.commands.registry import CommandRegistry


async def cmd_new(reg: CommandRegistry, _args: list[str]) -> None:
    """Start a new session."""
    if reg.runtime is not None:
        await reg.runtime.new_session()


async def cmd_fork(reg: CommandRegistry, args: list[str]) -> None:
    """Fork the session at a given entry ID."""
    if reg.runtime is None:
        return
    await reg.runtime.fork_session(args[0])
