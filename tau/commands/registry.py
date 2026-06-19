from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tau.commands.types import CommandInfo, ParsedCommand

if TYPE_CHECKING:
    from tau.runtime.service import Runtime


class CommandRegistry:
    """
    Holds all registered slash commands and dispatches parsed input.
    Attach a Runtime so handlers can call back into session lifecycle methods.
    """

    def __init__(self, runtime: Runtime | None = None) -> None:
        """Initialize the command registry with optional runtime context."""
        self.runtime = runtime
        self._commands: dict[str, CommandInfo] = {}
        from tau.builtins.commands import get_builtin_commands
        for cmd in get_builtin_commands():
            self.register(cmd)

    def register(self, command: CommandInfo) -> None:
        """Register a command with its name and aliases."""
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def unregister(self, name: str) -> None:
        """Remove a command and all its aliases."""
        cmd = self._commands.get(name)
        if cmd is None:
            return
        keys = [k for k, v in self._commands.items() if v is cmd]
        for k in keys:
            del self._commands[k]

    def get(self, name: str) -> CommandInfo | None:
        """Retrieve a command by name or alias."""
        return self._commands.get(name)

    def list(self) -> list[CommandInfo]:
        """Return all registered commands (de-duplicated by name)."""
        seen: set[str] = set()
        result: list[CommandInfo] = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return result

    async def dispatch(self, parsed: ParsedCommand) -> bool:
        """Invoke the matching command; return True if dispatched, False if not found."""
        cmd = self._commands.get(parsed.name)
        if cmd is None:
            return False

        missing = cmd.required_arg_names[len(parsed.args):]
        if missing:
            if self.runtime is not None:
                plural = "s" if len(missing) > 1 else ""
                self.runtime.notify(f"Missing required argument{plural}: {', '.join(missing)}")
            return True

        result = cmd.call(self, parsed.args)
        if asyncio.iscoroutine(result):
            await result
        return True
