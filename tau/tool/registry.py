"""ToolRegistry — single source of truth for all registered tools.

Tools are tagged with a source so callers can query, add, remove, or replace
an entire source group without affecting tools from other sources.

Built-in sources:
  "builtin"    — tools from tau.builtins.tools.TOOLS
  "extension"  — tools registered by loaded extensions
  "mcp"        — tools provided by MCP servers
  "runtime"    — tools passed via RuntimeConfig.tools at session start

Usage::

    registry = ToolRegistry()
    registry.register(MyTool(), source="builtin")
    registry.replace_source("extension", new_extension_tools)
    registry.sync_to_engine(engine)
    all_tools = registry.list()
    web_tool   = registry.get("web_search")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tau.tool.types import Tool

if TYPE_CHECKING:
    from tau.engine.service import Engine


@dataclass
class _Entry:
    tool: Tool
    source: str


class ToolRegistry:
    """Tracks all tools with their source and keeps the live engine in sync."""

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        # Ordered dict preserves registration order within each source.
        self._entries: dict[str, _Entry] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, tool: Tool, source: str = "builtin") -> None:
        """Add or replace a tool. Last registration wins on name collision."""
        self._entries[tool.name] = _Entry(tool=tool, source=source)

    def unregister(self, name: str) -> bool:
        """Remove a tool by name. Returns True if it existed."""
        return self._entries.pop(name, None) is not None

    def replace_source(self, source: str, tools: list[Tool]) -> None:
        """Atomically replace all tools from *source* with *tools*.

        Tools from other sources are untouched. Tools removed from the source
        are dropped; new ones are added; existing ones are updated in place.
        """
        old_names = {n for n, e in self._entries.items() if e.source == source}
        new_names = {t.name for t in tools}

        for name in old_names - new_names:
            del self._entries[name]

        for tool in tools:
            self._entries[tool.name] = _Entry(tool=tool, source=source)

    # ── Query ─────────────────────────────────────────────────────────────────

    def get(self, name: str) -> Tool | None:
        """Return the tool with *name*, or None if not registered."""
        entry = self._entries.get(name)
        return entry.tool if entry is not None else None

    def list(self, source: str | None = None) -> list[Tool]:
        """Return all registered tools, optionally filtered by source."""
        if source is None:
            return [e.tool for e in self._entries.values()]
        return [e.tool for e in self._entries.values() if e.source == source]

    def names(self, source: str | None = None) -> set[str]:
        """Return the set of registered tool names, optionally filtered by source."""
        if source is None:
            return set(self._entries)
        return {n for n, e in self._entries.items() if e.source == source}

    def sources(self) -> set[str]:
        """Return all source labels that have at least one registered tool."""
        return {e.source for e in self._entries.values()}

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered by name."""
        return name in self._entries

    # ── Engine sync ───────────────────────────────────────────────────────────

    def sync_to_engine(self, engine: Engine, layout: object | None = None) -> None:
        """Apply the current registry state to a live engine instance.

        Replaces the engine's tool list and lookup dict directly — the engine
        no longer exposes add/remove methods; the registry is the only mutation
        path.
        """
        tools = self.list()
        engine.tools = tools
        engine._tools = {t.name: t for t in tools}
        if layout is not None:
            messages = getattr(layout, "messages", None)
            if messages is not None and hasattr(messages, "set_tool_lookup"):
                messages.set_tool_lookup(self.get)
