"""
MCP (Model Context Protocol) Extension for Tau

This extension enables Tau to integrate with MCP servers, providing:
- Tools: Execute functions from MCP servers
- Resources: Access structured data from MCP servers
- Prompts: Use templated workflows from MCP servers
- Sampling: Allow MCP servers to request LLM completions
- Roots: Define filesystem boundaries for file access
- Elicitation: Support user input requests from MCP servers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# pylint: disable=import-error
from server_manager import MCPServerManager  # type: ignore
from commands import register_mcp_commands  # type: ignore
from hooks import register_mcp_hooks  # type: ignore

__version__ = "0.1.0"
__author__ = "MCP Extenison"
__description__ = "Model Context Protocol integration for Tau agent"

# Global server manager instance
_server_manager: MCPServerManager | None = None


def register(tau) -> None:  # type: ignore
    """Register MCP extension with Tau.
    
    Registers:
    - MCP server management tools
    - Commands for server lifecycle and interaction
    - Event hooks for integration
    - Dynamic tool registration from connected servers
    """
    global _server_manager
    
    # Initialize the MCP server manager
    _server_manager = MCPServerManager(tau)
    
    # Register MCP management commands
    register_mcp_commands(tau, _server_manager)
    
    # Register event hooks for lifecycle management
    register_mcp_hooks(tau, _server_manager)
    
    # Append documentation to system prompt
    tau.append_prompt(_get_system_prompt_addition())


def _get_system_prompt_addition() -> str:
    """Get system prompt addition explaining MCP capabilities."""
    return """
## MCP (Model Context Protocol) Integration

You have access to MCP servers that extend your capabilities with:

- **Tools**: Execute functions from MCP servers via /mcp connect
- **Resources**: Access data from MCP servers (read-only context)
- **Prompts**: Use templated workflows from MCP servers
- **Sampling**: MCP servers can request your help with completions
- **Roots**: Safe filesystem boundaries for file access

### Commands:
- `/mcp connect <server_path>` - Connect to an MCP server
- `/mcp list` - List connected servers
- `/mcp resources` - Browse available resources
- `/mcp prompts` - List available prompt templates
- `/mcp disconnect [server]` - Disconnect from a server
- `/mcp config` - View current MCP configuration

All MCP tools require explicit execution. Resources are read-only and safe.
"""
