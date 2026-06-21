from __future__ import annotations

from tau.builtins.commands.clear import cmd_clear
from tau.builtins.commands.compact import cmd_compact
from tau.builtins.commands.reload import cmd_reload
from tau.builtins.commands.session import cmd_fork, cmd_new
from tau.commands.types import CommandInfo


def get_builtin_commands() -> list[CommandInfo]:
    """Get the list of builtin slash commands."""
    return [
        CommandInfo(
            name="new",
            description="Start a fresh session.",
            call=cmd_new,
        ),
        CommandInfo(
            name="fork",
            description="Branch the session tree at a given entry ID.",
            call=cmd_fork,
            argument_hint="<entry_id>",
            required_arg_names=["entry_id"],
        ),
        CommandInfo(
            name="reload",
            description="Reload extensions, themes, and prompt appends.",
            call=cmd_reload,
        ),
        CommandInfo(
            name="compact",
            description="Summarise and compact the current session context.",
            call=cmd_compact,
            argument_hint="<custom_instruction>",
        ),
        CommandInfo(
            name="clear",
            description="Clear the message list.",
            call=cmd_clear,
        ),
    ]
