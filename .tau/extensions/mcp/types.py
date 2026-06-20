"""
MCP Extension Type Definitions

Core types for MCP server configuration and runtime state.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    name: str
    path: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class MCPServerInfo:
    """Runtime information about a connected MCP server."""
    config: MCPServerConfig
    connected: bool = False
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    supports_sampling: bool = False
    supports_roots: bool = False
    supports_elicitation: bool = False
