"""Slash-command registry for the coding agent."""

from tau.commands.registry import CommandRegistry
from tau.commands.types import CommandInfo, ParsedCommand

__all__ = [
    "CommandInfo",
    "ParsedCommand",
    "CommandRegistry",
]
