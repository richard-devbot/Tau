"""
MCP Event Hooks

Register lifecycle event handlers for MCP integration with Tau.
"""

import logging
from commands import _register_server_tools

logger = logging.getLogger(__name__)


def register_mcp_hooks(tau, server_manager) -> None:
    """Register MCP event hooks with Tau.
    
    Args:
        tau: Tau extension API.
        server_manager: MCPServerManager instance.
    """
    
    @tau.on("session_start")
    async def on_session_start(event, ctx):
        """Load MCP servers and tools when session starts."""
        logger.info("MCP session_start hook triggered")
        
        # Auto-connect to configured servers if they exist
        for server_name, server_info in server_manager.servers.items():
            if server_info.config.enabled:
                logger.info(f"Auto-connecting to MCP server: {server_name}")
                success = await server_manager.connect_server(
                    server_name,
                    server_info.config.path,
                    server_info.config.args,
                )
                
                if success:
                    # Register tools from this server
                    await _register_server_tools(tau, server_manager, server_name)
    
    @tau.on("session_shutdown")
    async def on_session_shutdown(event, ctx):
        """Clean up MCP connections when session ends."""
        logger.info("MCP session_shutdown hook triggered")
        
        # Disconnect all servers
        for server_name in list(server_manager.servers.keys()):
            await server_manager.disconnect_server(server_name)
    
    @tau.on("turn_end")
    async def on_turn_end(event, ctx):
        """Handle MCP sampling requests after LLM response."""
        # This hook can be used to implement server-initiated sampling
        # where MCP servers request completions through the client
        logger.debug("MCP turn_end hook triggered")
    
    @tau.on("tool_call")
    async def on_tool_call(event, ctx):
        """Intercept tool calls to handle MCP-specific logic."""
        # Check if this is an MCP tool call
        if event.tool_name.startswith("mcp_"):
            logger.info(f"MCP tool call intercepted: {event.tool_name}")
    
    @tau.on("tool_result")
    async def on_tool_result(event, ctx):
        """Handle MCP tool results."""
        if event.tool_name.startswith("mcp_"):
            logger.info(f"MCP tool result: {event.tool_name}")
            
            # Could add special handling for MCP results here
            # e.g., logging, caching, etc.
    
    @tau.on("before_compaction")
    async def before_compaction(event, ctx):
        """Handle MCP state during compaction."""
        # Could preserve MCP server state during session compaction
        logger.debug("MCP before_compaction hook triggered")


def get_mcp_status_info() -> str:
    """Get formatted MCP server status information.
    
    Returns:
        Formatted string with server status.
    """
    return "MCP Extension Ready"
