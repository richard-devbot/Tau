from __future__ import annotations

from tau.tui.utils import BOLD, DIM, RESET

_TOOL_INDENT = "  "


def display_name(tool_name: str) -> str:
    """Convert snake_case tool name to Title Case display name."""
    return " ".join(w.capitalize() for w in tool_name.split("_"))


def call_line(tool_name: str, *values: str) -> list[str]:
    """Render a tool invocation as  ToolName(value)  for the TUI call display.

    Only non-empty values are included. Multiple values are comma-separated.
    Example: call_line("web_fetch", url) → ["  Web Fetch(https://...)"]
    """
    name = display_name(tool_name)
    args = ", ".join(v for v in values if v)
    return [f"{_TOOL_INDENT}{BOLD}{name}{RESET}{DIM}({args}){RESET}"]
