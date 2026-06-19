"""Built-in coding-agent tools."""

from tau.builtins.tools.read import ReadTool
from tau.builtins.tools.write import WriteTool
from tau.builtins.tools.edit import EditTool
from tau.builtins.tools.terminal import TerminalTool
from tau.builtins.tools.glob import GlobTool
from tau.builtins.tools.grep import GrepTool
from tau.builtins.tools.ls import LsTool

TOOLS = [
    ReadTool(),
    WriteTool(),
    EditTool(),
    TerminalTool(),
    GlobTool(),
    GrepTool(),
    LsTool(),
]


def create_read_tool() -> ReadTool:
    """Return a fresh ReadTool instance for delegation in extension renderers."""
    return ReadTool()


def create_write_tool() -> WriteTool:
    """Return a fresh WriteTool instance for delegation in extension renderers."""
    return WriteTool()


def create_edit_tool() -> EditTool:
    """Return a fresh EditTool instance for delegation in extension renderers."""
    return EditTool()


def create_terminal_tool() -> TerminalTool:
    """Return a fresh TerminalTool instance for delegation in extension renderers."""
    return TerminalTool()


def create_glob_tool() -> GlobTool:
    """Return a fresh GlobTool instance for delegation in extension renderers."""
    return GlobTool()


def create_grep_tool() -> GrepTool:
    """Return a fresh GrepTool instance for delegation in extension renderers."""
    return GrepTool()


def create_ls_tool() -> LsTool:
    """Return a fresh LsTool instance for delegation in extension renderers."""
    return LsTool()


__all__ = [
    "ReadTool",
    "WriteTool",
    "EditTool",
    "TerminalTool",
    "GlobTool",
    "GrepTool",
    "LsTool",
    "TOOLS",
    "create_read_tool",
    "create_write_tool",
    "create_edit_tool",
    "create_terminal_tool",
    "create_glob_tool",
    "create_grep_tool",
    "create_ls_tool",
]
